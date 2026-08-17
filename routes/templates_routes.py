"""
Email Templates Blueprint: Template Manager, Variable Interpolator, and Preview.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from auth.middleware import login_required, get_current_user
from database.database import query_db, insert_db, execute_db, log_activity
from gmail import messages as gmail_msg

templates_bp = Blueprint('templates_mgr', __name__, url_prefix='/templates')

def render_template_string(template_str: str, context: dict) -> str:
    """Safely replace {{variable}} placeholders in template strings."""
    result = template_str or ''
    for k, v in context.items():
        result = result.replace(f"{{{{{k}}}}}", str(v))
    return result

@templates_bp.route('/')
@login_required
def index():
    """Email Templates Catalog."""
    user = get_current_user()
    templates = query_db("SELECT * FROM email_templates ORDER BY category ASC, id DESC")
    return render_template('templates_mgr/index.html', user=user, templates=templates)

@templates_bp.route('/api/save', methods=['POST'])
@login_required
def api_save():
    """Save or update template."""
    data = request.get_json() or {}
    t_id = data.get('id')
    name = data.get('name', 'Untitled Template').strip()
    category = data.get('category', 'general')
    subject = data.get('subject', '')
    body_html = data.get('body_html', '')
    body_text = data.get('body_text', '')
    variables = data.get('variables', 'recipient_name, sender_name, company, subject, ai_response')

    if not name or not body_html:
        return jsonify({'error': 'Template name and HTML body are required'}), 400

    if t_id:
        execute_db(
            """UPDATE email_templates 
               SET name = ?, category = ?, subject = ?, body_html = ?, body_text = ?, variables = ?, updated_at = ?
               WHERE id = ?""",
            (name, category, subject, body_html, body_text, variables, datetime.utcnow().isoformat(), t_id)
        )
    else:
        t_id = insert_db(
            """INSERT INTO email_templates (name, category, subject, body_html, body_text, variables)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, category, subject, body_html, body_text, variables)
        )
    log_activity('SETTINGS', f"Saved Email Template: {name}", actor=session.get('username', 'admin'))
    return jsonify({'success': True, 'id': t_id})

@templates_bp.route('/api/<int:t_id>', methods=['DELETE'])
@login_required
def api_delete(t_id: int):
    execute_db("DELETE FROM email_templates WHERE id = ?", (t_id,))
    return jsonify({'success': True})

@templates_bp.route('/api/preview', methods=['POST'])
@login_required
def api_preview():
    """Render preview with sample variables."""
    data = request.get_json() or {}
    subject = data.get('subject', '')
    body_html = data.get('body_html', '')
    
    context = {
        'recipient_name': 'Alex Johnson',
        'sender_name': 'Sarah Smith',
        'company': 'Acme Enterprise Solutions',
        'subject': 'Service Agreement Inquiry',
        'ai_response': 'We have reviewed your proposed timeline and are delighted to confirm our availability for the kickoff next Tuesday at 10:00 AM EST.',
        'date': datetime.utcnow().strftime('%B %d, %Y')
    }
    
    rendered_subject = render_template_string(subject, context)
    rendered_html = render_template_string(body_html, context)

    return jsonify({
        'success': True,
        'subject': rendered_subject,
        'html': rendered_html
    })
