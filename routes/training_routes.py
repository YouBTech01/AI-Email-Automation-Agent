"""
AI Training Blueprint: Behavioral Instructions, Few-shot Examples, and Knowledge Base.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from auth.middleware import login_required, permission_required, get_current_user
from database.database import query_db, insert_db, execute_db, log_activity

training_bp = Blueprint('training', __name__, url_prefix='/training')

@training_bp.route('/')
@login_required
@permission_required('manage_ai_training')
def index():
    """AI Behavioral Training & Knowledge Base Manager."""
    user = get_current_user()
    rules = query_db("SELECT * FROM ai_training_rules ORDER BY priority ASC, id DESC")
    examples = query_db("SELECT * FROM ai_training_examples ORDER BY id DESC")
    knowledge = query_db("SELECT * FROM ai_knowledge ORDER BY category ASC, id DESC")
    return render_template('training/index.html', user=user, rules=rules, examples=examples, knowledge=knowledge)

# ==================== Rules API ====================
@training_bp.route('/api/rules', methods=['POST'])
@login_required
@permission_required('manage_ai_training')
def api_save_rule():
    """Create or update behavioral rule."""
    data = request.get_json() or {}
    r_id = data.get('id')
    r_type = data.get('rule_type', 'instruction')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    priority = int(data.get('priority', 1))
    is_active = 1 if data.get('is_active', True) else 0

    if not title or not content:
        return jsonify({'error': 'Title and content are required'}), 400

    if r_id:
        execute_db(
            "UPDATE ai_training_rules SET rule_type = ?, title = ?, content = ?, priority = ?, is_active = ?, updated_at = ? WHERE id = ?",
            (r_type, title, content, priority, is_active, datetime.utcnow().isoformat(), r_id)
        )
    else:
        r_id = insert_db(
            "INSERT INTO ai_training_rules (rule_type, title, content, priority, is_active) VALUES (?, ?, ?, ?, ?)",
            (r_type, title, content, priority, is_active)
        )
    log_activity('AI', f"Saved Behavioral Rule: {title}", actor=session.get('username', 'admin'))
    return jsonify({'success': True, 'id': r_id})

@training_bp.route('/api/rules/<int:rule_id>', methods=['DELETE'])
@login_required
@permission_required('manage_ai_training')
def api_delete_rule(rule_id: int):
    execute_db("DELETE FROM ai_training_rules WHERE id = ?", (rule_id,))
    return jsonify({'success': True})

# ==================== Examples API ====================
@training_bp.route('/api/examples', methods=['POST'])
@login_required
@permission_required('manage_ai_training')
def api_save_example():
    """Save few-shot training example."""
    data = request.get_json() or {}
    e_id = data.get('id')
    cat = data.get('category', 'customer_support')
    user_in = data.get('user_input', '').strip()
    ideal = data.get('ideal_response', '').strip()
    notes = data.get('notes', '').strip()

    if not user_in or not ideal:
        return jsonify({'error': 'User input and ideal response are required'}), 400

    if e_id:
        execute_db(
            "UPDATE ai_training_examples SET category = ?, user_input = ?, ideal_response = ?, notes = ?, updated_at = ? WHERE id = ?",
            (cat, user_in, ideal, notes, datetime.utcnow().isoformat(), e_id)
        )
    else:
        e_id = insert_db(
            "INSERT INTO ai_training_examples (category, user_input, ideal_response, notes) VALUES (?, ?, ?, ?)",
            (cat, user_in, ideal, notes)
        )
    return jsonify({'success': True, 'id': e_id})

@training_bp.route('/api/examples/<int:example_id>', methods=['DELETE'])
@login_required
@permission_required('manage_ai_training')
def api_delete_example(example_id: int):
    execute_db("DELETE FROM ai_training_examples WHERE id = ?", (example_id,))
    return jsonify({'success': True})

# ==================== Knowledge Base API ====================
@training_bp.route('/api/knowledge', methods=['POST'])
@login_required
@permission_required('manage_ai_training')
def api_save_knowledge():
    """Save knowledge base entry."""
    data = request.get_json() or {}
    k_id = data.get('id')
    cat = data.get('category', 'faq')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    tags = data.get('tags', '').strip()

    if not title or not content:
        return jsonify({'error': 'Title and content are required'}), 400

    if k_id:
        execute_db(
            "UPDATE ai_knowledge SET category = ?, title = ?, content = ?, tags = ?, updated_at = ? WHERE id = ?",
            (cat, title, content, tags, datetime.utcnow().isoformat(), k_id)
        )
    else:
        k_id = insert_db(
            "INSERT INTO ai_knowledge (category, title, content, tags) VALUES (?, ?, ?, ?)",
            (cat, title, content, tags)
        )
    return jsonify({'success': True, 'id': k_id})

@training_bp.route('/api/knowledge/<int:k_id>', methods=['DELETE'])
@login_required
@permission_required('manage_ai_training')
def api_delete_knowledge(k_id: int):
    execute_db("DELETE FROM ai_knowledge WHERE id = ?", (k_id,))
    return jsonify({'success': True})
