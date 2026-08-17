"""
Automation Blueprint: Visual Workflow Builder, Management, and Execution Logs.
"""
import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from auth.middleware import login_required, permission_required, get_current_user
from database.database import query_db, insert_db, execute_db, log_activity
from automation.engine import approve_pending_automation_run
from automation.worker import run_automation_worker_cycle

automation_bp = Blueprint('automation', __name__, url_prefix='/automations')

@automation_bp.route('/')
@login_required
@permission_required('manage_automations')
def index():
    """List of all automations and execution statistics."""
    user = get_current_user()
    automations = query_db("""
        SELECT a.*, 
               (SELECT COUNT(*) FROM automation_runs r WHERE r.automation_id = a.id) as total_runs,
               (SELECT COUNT(*) FROM automation_runs r WHERE r.automation_id = a.id AND r.status = 'COMPLETED') as successful_runs
        FROM automations a
        ORDER BY a.updated_at DESC
    """)
    recent_runs = query_db("""
        SELECT r.*, a.name as automation_name 
        FROM automation_runs r
        JOIN automations a ON r.automation_id = a.id
        ORDER BY r.id DESC LIMIT 20
    """)
    return render_template('automation/index.html', user=user, automations=automations, recent_runs=recent_runs)

@automation_bp.route('/builder')
@automation_bp.route('/builder/<int:automation_id>')
@login_required
@permission_required('manage_automations')
def builder(automation_id: int = None):
    """Visual Material Automation Builder."""
    user = get_current_user()
    automation = None
    triggers = []
    conditions = []
    actions = []

    if automation_id:
        automation = query_db("SELECT * FROM automations WHERE id = ?", (automation_id,), one=True)
        if automation:
            triggers = query_db("SELECT * FROM automation_triggers WHERE automation_id = ?", (automation_id,))
            conditions = query_db("SELECT * FROM automation_conditions WHERE automation_id = ?", (automation_id,))
            actions = query_db("SELECT * FROM automation_actions WHERE automation_id = ? ORDER BY sequence_order ASC", (automation_id,))

    return render_template(
        'automation/builder.html',
        user=user,
        automation=automation,
        triggers=triggers,
        conditions=conditions,
        actions=actions
    )

# ==================== Automation REST APIs ====================

@automation_bp.route('/api/save', methods=['POST'])
@login_required
@permission_required('manage_automations')
def api_save():
    """Save (Create or Update) an automation with all triggers, conditions, and actions."""
    data = request.get_json() or {}
    auto_id = data.get('id')
    name = data.get('name', 'Untitled Automation').strip()
    description = data.get('description', '').strip()
    status = data.get('status', 'ACTIVE')
    trigger_type = data.get('trigger_type', 'new_email')
    confidence_threshold = int(data.get('confidence_threshold', 85))
    approval_mode = data.get('approval_mode', 'draft_only')

    triggers = data.get('triggers', [])
    conditions = data.get('conditions', [])
    actions = data.get('actions', [])

    if auto_id:
        # Update existing
        execute_db(
            """UPDATE automations 
               SET name = ?, description = ?, status = ?, trigger_type = ?, 
                   confidence_threshold = ?, approval_mode = ?, updated_at = ?
               WHERE id = ?""",
            (name, description, status, trigger_type, confidence_threshold, approval_mode, datetime.utcnow().isoformat(), auto_id)
        )
        # Clear child relations
        execute_db("DELETE FROM automation_triggers WHERE automation_id = ?", (auto_id,))
        execute_db("DELETE FROM automation_conditions WHERE automation_id = ?", (auto_id,))
        execute_db("DELETE FROM automation_actions WHERE automation_id = ?", (auto_id,))
    else:
        # Create new
        auto_id = insert_db(
            """INSERT INTO automations 
               (name, description, status, trigger_type, confidence_threshold, approval_mode)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, description, status, trigger_type, confidence_threshold, approval_mode)
        )

    # Insert triggers
    for t in triggers:
        t_type = t.get('trigger_type', trigger_type)
        t_cfg = json.dumps(t.get('config', {}))
        insert_db("INSERT INTO automation_triggers (automation_id, trigger_type, config_json) VALUES (?, ?, ?)",
                  (auto_id, t_type, t_cfg))

    # Insert conditions
    for c in conditions:
        field = c.get('field', 'sender')
        op = c.get('operator', 'contains')
        val = c.get('value', '')
        is_ai = 1 if field.startswith('ai_') else 0
        insert_db("INSERT INTO automation_conditions (automation_id, field, operator, value, is_ai_condition) VALUES (?, ?, ?, ?, ?)",
                  (auto_id, field, op, val, is_ai))

    # Insert actions
    for idx, a in enumerate(actions):
        a_type = a.get('action_type', 'generate_draft')
        a_cfg = json.dumps(a.get('config', {}))
        insert_db("INSERT INTO automation_actions (automation_id, action_type, config_json, sequence_order) VALUES (?, ?, ?, ?)",
                  (auto_id, a_type, a_cfg, idx + 1))

    log_activity('AUTOMATION', f"Saved Automation '{name}'", actor=session.get('username', 'admin'), details={'id': auto_id})
    return jsonify({'success': True, 'automation_id': auto_id})

@automation_bp.route('/api/<int:auto_id>/toggle', methods=['POST'])
@login_required
@permission_required('manage_automations')
def api_toggle(auto_id: int):
    """Toggle automation status between ACTIVE and PAUSED."""
    auto = query_db("SELECT status, name FROM automations WHERE id = ?", (auto_id,), one=True)
    if not auto:
        return jsonify({'error': 'Automation not found'}), 404

    new_status = 'PAUSED' if auto['status'] == 'ACTIVE' else 'ACTIVE'
    execute_db("UPDATE automations SET status = ?, updated_at = ? WHERE id = ?", (new_status, datetime.utcnow().isoformat(), auto_id))
    log_activity('AUTOMATION', f"Toggled Automation '{auto['name']}' to {new_status}", actor=session.get('username', 'admin'))
    return jsonify({'success': True, 'new_status': new_status})

@automation_bp.route('/api/<int:auto_id>', methods=['DELETE'])
@login_required
@permission_required('manage_automations')
def api_delete(auto_id: int):
    """Delete automation."""
    execute_db("DELETE FROM automations WHERE id = ?", (auto_id,))
    log_activity('AUTOMATION', f"Deleted Automation #{auto_id}", actor=session.get('username', 'admin'))
    return jsonify({'success': True})

@automation_bp.route('/api/runs/<int:run_id>/approve', methods=['POST'])
@login_required
@permission_required('send_emails')
def api_approve_run(run_id: int):
    """One-click admin approval for pending Level 2 automation run."""
    user_id = session.get('user_id')
    res = approve_pending_automation_run(run_id, user_id)
    return jsonify(res)

@automation_bp.route('/api/test-cycle', methods=['POST'])
@login_required
@permission_required('execute_automations')
def api_test_cycle():
    """Trigger a manual automation evaluation cycle."""
    res = run_automation_worker_cycle(max_emails=10)
    return jsonify(res)

@automation_bp.route('/api/ai-generate-workflow', methods=['POST'])
@login_required
@permission_required('manage_automations')
def api_ai_generate_workflow():
    """Use AI or smart heuristics to translate a plain-English problem into a structured workflow."""
    data = request.get_json() or {}
    user_prompt = data.get('prompt', '').strip()
    if not user_prompt:
        return jsonify({'success': False, 'error': 'Please describe what you want to automate.'}), 400

    system_prompt = """You are an expert email automation workflow designer.
Given a user's problem or automation requirement in natural language, output a valid JSON object describing the automation configuration.

JSON Schema format strictly required:
{
  "name": "Short, clear title",
  "description": "Explanation of workflow",
  "trigger_type": "new_email" | "unread_email" | "sender_match" | "keyword_match" | "has_attachment",
  "conditions": [
    {
      "field": "sender" | "subject" | "body" | "ai_category" | "has_attachment",
      "operator": "contains" | "not_contains" | "equals" | "matches_regex",
      "value": "string"
    }
  ],
  "actions": [
    {
      "action_type": "generate_draft" | "send_reply" | "add_label" | "archive" | "forward",
      "config": {
        "instruction": "string (for draft/reply)",
        "label": "string (for add_label)",
        "to": "string (for forward)"
      }
    }
  ],
  "approval_mode": "draft_only" | "approval_required" | "trusted_auto",
  "confidence_threshold": 85
}

Return ONLY the raw JSON object, without markdown formatting or code fences."""

    from ai.router import route_ai_request
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Create workflow for: {user_prompt}"}
    ]

    res = route_ai_request(messages=messages, temperature=0.2)
    if not res.get('success'):
        fallback = _heuristic_workflow_generator(user_prompt)
        return jsonify({'success': True, 'workflow': fallback, 'is_fallback': True})

    content = res.get('content', '').strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        workflow = json.loads(content)
        return jsonify({'success': True, 'workflow': workflow})
    except Exception:
        fallback = _heuristic_workflow_generator(user_prompt)
        return jsonify({'success': True, 'workflow': fallback, 'is_fallback': True})

def _heuristic_workflow_generator(prompt: str) -> dict:
    """Smart heuristic fallback parser when LLM is offline."""
    p = prompt.lower()
    if 'refund' in p or 'dispute' in p:
        return {
            'name': 'Refund & Dispute Shield',
            'description': 'Handles refund inquiries and drafts a polite response for admin review',
            'trigger_type': 'keyword_match',
            'conditions': [{'field': 'body', 'operator': 'contains', 'value': 'refund'}],
            'actions': [{'action_type': 'generate_draft', 'config': {'instruction': 'Acknowledge refund request politely and explain 3-5 business day review policy.'}}],
            'approval_mode': 'approval_required',
            'confidence_threshold': 90
        }
    elif 'price' in p or 'pricing' in p or 'quote' in p or 'cost' in p or 'rate' in p:
        return {
            'name': 'Pricing & Quote Inquiries',
            'description': 'Drafts reply for customers asking about pricing and rates',
            'trigger_type': 'new_email',
            'conditions': [{'field': 'body', 'operator': 'contains', 'value': 'pricing'}],
            'actions': [{'action_type': 'generate_draft', 'config': {'instruction': 'Thank the customer for their interest, provide pricing details, and offer a demo call.'}}],
            'approval_mode': 'draft_only',
            'confidence_threshold': 85
        }
    elif 'newsletter' in p or 'unsubscribe' in p or 'marketing' in p or 'promo' in p:
        return {
            'name': 'Auto-Archive Newsletters',
            'description': 'Archives marketing emails and tags them Newsletters',
            'trigger_type': 'new_email',
            'conditions': [{'field': 'body', 'operator': 'contains', 'value': 'unsubscribe'}],
            'actions': [
                {'action_type': 'add_label', 'config': {'label': 'Newsletters'}},
                {'action_type': 'archive', 'config': {}}
            ],
            'approval_mode': 'trusted_auto',
            'confidence_threshold': 80
        }
    elif 'vip' in p or 'urgent' in p or 'important' in p:
        return {
            'name': 'VIP & Urgent Inquiries',
            'description': 'Labels urgent emails VIP and prepares an expedited draft',
            'trigger_type': 'new_email',
            'conditions': [{'field': 'subject', 'operator': 'contains', 'value': 'urgent'}],
            'actions': [
                {'action_type': 'add_label', 'config': {'label': 'VIP'}},
                {'action_type': 'generate_draft', 'config': {'instruction': 'Acknowledge priority status and state that our team is actively addressing their request.'}}
            ],
            'approval_mode': 'draft_only',
            'confidence_threshold': 90
        }
    else:
        return {
            'name': f"Auto-Workflow: {prompt[:32]}",
            'description': prompt,
            'trigger_type': 'new_email',
            'conditions': [{'field': 'body', 'operator': 'contains', 'value': prompt[:20]}],
            'actions': [{'action_type': 'generate_draft', 'config': {'instruction': f"Address customer email regarding: {prompt}"}}],
            'approval_mode': 'draft_only',
            'confidence_threshold': 85
        }
