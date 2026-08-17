"""
Automation Execution Engine, State Machine, and Duplicate Protection Guard.
"""
import json
from datetime import datetime
from typing import Dict, Any, List
from database.database import query_db, insert_db, execute_db, log_activity
from automation.triggers import evaluate_trigger
from automation.conditions import evaluate_conditions, analyze_email_with_ai
from automation.actions import execute_automation_action
from gmail import messages as gmail_msg

def is_message_already_processed(message_id: str, automation_id: int) -> bool:
    """Duplicate Guard: Check if this message was already processed by this automation."""
    existing = query_db(
        "SELECT id FROM automation_processed_messages WHERE message_id = ? AND automation_id = ?",
        (message_id, automation_id),
        one=True
    )
    return bool(existing)

def record_processed_message(message_id: str, thread_id: str, automation_id: int):
    """Duplicate Guard: Record message as processed to prevent duplicate runs/replies."""
    try:
        insert_db(
            "INSERT OR IGNORE INTO automation_processed_messages (message_id, thread_id, automation_id) VALUES (?, ?, ?)",
            (message_id, thread_id, automation_id)
        )
    except Exception as e:
        print(f"Duplicate guard record error: {e}")

def run_automations_on_email(email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluate and execute all active automations against an incoming email."""
    msg_id = email_data.get('id')
    thread_id = email_data.get('threadId', '')
    if not msg_id:
        return []

    active_automations = query_db("SELECT * FROM automations WHERE status = 'ACTIVE'")
    results = []

    ai_analysis = None  # Lazy-loaded on demand if condition requires it

    for auto in active_automations:
        auto_id = auto['id']

        # 1. Mandatory Duplicate Protection Check
        if is_message_already_processed(msg_id, auto_id):
            continue

        # 2. Evaluate Trigger
        triggers = query_db("SELECT * FROM automation_triggers WHERE automation_id = ?", (auto_id,))
        trigger_matched = False
        for trig in triggers:
            trig_config = json.loads(trig['config_json']) if isinstance(trig['config_json'], str) else (trig['config_json'] or {})
            if evaluate_trigger(trig['trigger_type'], trig_config, email_data):
                trigger_matched = True
                break

        if not triggers and auto['trigger_type']:
            if evaluate_trigger(auto['trigger_type'], {}, email_data):
                trigger_matched = True

        if not trigger_matched:
            continue

        # 3. Evaluate Conditions
        conditions = query_db("SELECT * FROM automation_conditions WHERE automation_id = ?", (auto_id,))
        has_ai_condition = any(c.get('is_ai_condition') or c.get('field', '').startswith('ai_') for c in conditions)

        if has_ai_condition and not ai_analysis:
            ai_analysis = analyze_email_with_ai(email_data)

        if not evaluate_conditions(conditions, email_data, ai_analysis):
            continue

        # If no AI analysis yet but needed for confidence score
        if not ai_analysis:
            ai_analysis = analyze_email_with_ai(email_data)

        # 4. Record Run: RUNNING
        input_snippet = {
            'from': email_data.get('from'),
            'subject': email_data.get('subject'),
            'date': email_data.get('date'),
            'message_id': msg_id
        }
        run_id = insert_db(
            """INSERT INTO automation_runs 
               (automation_id, trigger_event, status, input_data_json, confidence_score, decision_reason, started_at)
               VALUES (?, ?, 'RUNNING', ?, ?, ?, ?)""",
            (auto_id, auto['trigger_type'], json.dumps(input_snippet), ai_analysis.get('confidence', 0), 
             ai_analysis.get('reasoning', ''), datetime.utcnow().isoformat())
        )

        # 5. Execute Actions
        actions = query_db("SELECT * FROM automation_actions WHERE automation_id = ? ORDER BY sequence_order ASC", (auto_id,))
        action_results = []
        overall_status = 'COMPLETED'
        error_details = ''

        for act in actions:
            try:
                res = execute_automation_action(act, auto, email_data, ai_analysis)
                action_results.append(res)
                if not res.get('success'):
                    overall_status = 'FAILED'
                    error_details = res.get('error', 'Action failed')
            except Exception as e:
                overall_status = 'FAILED'
                error_details = str(e)
                action_results.append({'success': False, 'error': str(e)})

        # 6. Finalize Run & Duplicate Guard
        execute_db(
            """UPDATE automation_runs 
               SET status = ?, result_data_json = ?, error_details = ?, completed_at = ? 
               WHERE id = ?""",
            (overall_status, json.dumps(action_results), error_details, datetime.utcnow().isoformat(), run_id)
        )

        execute_db(
            "UPDATE automations SET execution_count = execution_count + 1, last_run_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), auto_id)
        )

        # Mark processed in duplicate guard
        record_processed_message(msg_id, thread_id, auto_id)

        log_activity('AUTOMATION', f"Executed Automation '{auto['name']}'", actor='automation-engine', details={
            'automation_id': auto_id, 'status': overall_status, 'confidence': ai_analysis.get('confidence')
        }, status='SUCCESS' if overall_status == 'COMPLETED' else 'FAILED')

        results.append({
            'automation_id': auto_id,
            'name': auto['name'],
            'status': overall_status,
            'run_id': run_id,
            'action_results': action_results
        })

    return results

def approve_pending_automation_run(run_id: int, user_id: int) -> Dict[str, Any]:
    """Admin Approval for Level 2 Pending Automations."""
    run = query_db("SELECT * FROM automation_runs WHERE id = ?", (run_id,), one=True)
    if not run:
        return {'success': False, 'error': 'Automation run not found.'}

    action_results = json.loads(run['result_data_json'] or '[]')
    input_data = json.loads(run['input_data_json'] or '{}')

    for res in action_results:
        if res.get('action_taken') == 'pending_approval' and res.get('reply_content'):
            msg_id = input_data.get('message_id')
            orig_msg = gmail_msg.get_message(msg_id)
            if orig_msg.get('success'):
                m = orig_msg['message']
                send_res = gmail_msg.send_message(
                    to=m['from'],
                    subject=f"Re: {m['subject']}",
                    body_text=res['reply_content'],
                    thread_id=m['threadId']
                )
                if send_res.get('success'):
                    res['action_taken'] = 'reply_sent_approved'
                    res['message_id'] = send_res.get('message_id')
                    execute_db(
                        "UPDATE automation_runs SET status = 'COMPLETED', result_data_json = ?, completed_at = ? WHERE id = ?",
                        (json.dumps(action_results), datetime.utcnow().isoformat(), run_id)
                    )
                    log_activity('AUTOMATION', 'Pending Automation Approved & Sent', actor=f"user_{user_id}", details={'run_id': run_id})
                    return {'success': True, 'message': 'Approved and email sent successfully.'}
                return send_res

    return {'success': False, 'error': 'No pending approval item in this run.'}
