"""
Chat Blueprint: Multi-turn Chat Management, Endpoints, and Exports.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, Response
from auth.middleware import login_required, permission_required, get_current_user
from database.database import query_db, insert_db, execute_db, log_activity
from chat.service import handle_user_chat_message, execute_confirmed_chat_action

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('/')
@login_required
@permission_required('use_ai_chat')
def index():
    """Main AI Chatbot UI."""
    user = get_current_user()
    providers = query_db("SELECT id, name, display_name, default_model FROM ai_providers WHERE is_active = 1")
    return render_template('chat/index.html', user=user, providers=providers)

@chat_bp.route('/api/sessions', methods=['GET', 'POST'])
@login_required
def api_sessions():
    """List or create chat sessions."""
    user_id = session.get('user_id')
    
    if request.method == 'GET':
        sessions = query_db(
            """SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id) as message_count
               FROM chat_sessions s
               LEFT JOIN chat_messages m ON s.id = m.session_id
               WHERE s.user_id = ?
               GROUP BY s.id
               ORDER BY s.updated_at DESC""",
            (user_id,)
        )
        return jsonify({'sessions': sessions})

    elif request.method == 'POST':
        data = request.get_json() or {}
        title = data.get('title', 'New Email Assistant Chat').strip()
        provider_id = data.get('provider_id')
        model_name = data.get('model_name')

        new_session_id = insert_db(
            """INSERT INTO chat_sessions (title, user_id, provider_id, model_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, user_id, provider_id, model_name, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        return jsonify({'success': True, 'session_id': new_session_id, 'title': title}), 201

@chat_bp.route('/api/sessions/<int:session_id>', methods=['PATCH', 'DELETE'])
@login_required
def api_session_detail(session_id: int):
    """Rename or delete a chat session."""
    user_id = session.get('user_id')
    
    if request.method == 'PATCH':
        data = request.get_json() or {}
        new_title = data.get('title', '').strip()
        if not new_title:
            return jsonify({'error': 'Title cannot be empty'}), 400
        
        execute_db(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (new_title, datetime.utcnow().isoformat(), session_id, user_id)
        )
        return jsonify({'success': True, 'title': new_title})

    elif request.method == 'DELETE':
        execute_db("DELETE FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        return jsonify({'success': True})

@chat_bp.route('/api/sessions/<int:session_id>/messages', methods=['GET'])
@login_required
def api_session_messages(session_id: int):
    """Retrieve message history for a specific chat session."""
    user_id = session.get('user_id')
    # Verify ownership
    sess = query_db("SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id), one=True)
    if not sess:
        return jsonify({'error': 'Session not found'}), 404

    messages = query_db(
        """SELECT id, role, content, model, provider, tokens, risk_tier, pending_action_json, created_at
           FROM chat_messages 
           WHERE session_id = ? 
           ORDER BY id ASC""",
        (session_id,)
    )
    return jsonify({'messages': messages})

@chat_bp.route('/api/send', methods=['POST'])
@login_required
@permission_required('use_ai_chat')
def api_send():
    """Send user message and receive AI response with automated tool handling."""
    user_id = session.get('user_id')
    data = request.get_json() or {}
    
    session_id = data.get('session_id')
    message_text = data.get('message', '').strip()
    provider_id = data.get('provider_id')
    model_name = data.get('model_name')

    if not message_text:
        return jsonify({'error': 'Message content cannot be empty'}), 400

    # Auto-create session if not provided
    if not session_id:
        title_snippet = message_text[:30] + "..." if len(message_text) > 30 else message_text
        session_id = insert_db(
            """INSERT INTO chat_sessions (title, user_id, provider_id, model_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title_snippet, user_id, provider_id, model_name, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
    else:
        execute_db("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), session_id))

    resp = handle_user_chat_message(
        session_id=session_id,
        user_id=user_id,
        user_message_text=message_text,
        preferred_provider_id=provider_id,
        preferred_model=model_name
    )

    resp['session_id'] = session_id
    return jsonify(resp)

@chat_bp.route('/api/confirm-action', methods=['POST'])
@login_required
@permission_required('use_ai_chat')
def api_confirm_action():
    """Confirm or cancel a pending high-risk tool action."""
    user_id = session.get('user_id')
    data = request.get_json() or {}
    message_id = data.get('message_id')
    approved = data.get('approved', False)

    if not message_id:
        return jsonify({'error': 'Message ID is required'}), 400

    res = execute_confirmed_chat_action(message_id=message_id, approved=approved, user_id=user_id)
    return jsonify(res)

@chat_bp.route('/api/export/<int:session_id>')
@login_required
def export_chat(session_id: int):
    """Export conversation transcript as Markdown."""
    user_id = session.get('user_id')
    sess = query_db("SELECT title FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id), one=True)
    if not sess:
        return "Chat not found", 404

    messages = query_db(
        "SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )

    md_content = f"# Chat Export: {sess['title']}\n\n"
    for m in messages:
        role_label = "**User**" if m['role'] == 'user' else "**AI Assistant**"
        md_content += f"### {role_label} ({m['created_at']})\n\n{m['content']}\n\n---\n\n"

    return Response(
        md_content,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment;filename=chat_{session_id}.md"}
    )
