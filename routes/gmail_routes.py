"""
Gmail Blueprint: OAuth Connect/Callback, Email Operations & Instant AI Inbox Actions.
"""
from flask import Blueprint, request, redirect, url_for, flash, jsonify, session
from auth.middleware import login_required, permission_required, get_current_user
from gmail.auth import create_oauth_flow, save_gmail_credentials, disconnect_gmail_account
from gmail import messages as gmail_msg, threads as gmail_thr, actions as gmail_act
from ai.prompts import build_system_prompt
from ai.router import route_ai_request
from database.database import query_db, log_activity

gmail_bp = Blueprint('gmail', __name__, url_prefix='/gmail')

@gmail_bp.route('/connect')
@login_required
@permission_required('manage_settings')
def connect():
    """Initiate Google OAuth 2.0 Flow."""
    try:
        flow = create_oauth_flow()
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        session['oauth_state'] = state
        if hasattr(flow, 'code_verifier') and flow.code_verifier:
            session['code_verifier'] = flow.code_verifier
        return redirect(auth_url)
    except Exception as e:
        flash(f"OAuth initialization error: {str(e)}. Please verify your Google Client ID and Secret in Settings.", "danger")
        return redirect(url_for('settings.index'))

@gmail_bp.route('/oauth2callback')
def oauth2callback():
    """Handle OAuth 2.0 Authorization Callback from Google."""
    code = request.args.get('code')
    state = request.args.get('state')

    if not code:
        flash("Authorization failed or was cancelled by user.", "danger")
        return redirect(url_for('settings.index'))

    try:
        stored_state = session.get('oauth_state')
        flow = create_oauth_flow(state=state or stored_state)
        
        # Restore PKCE code verifier if present
        code_verifier = session.pop('code_verifier', None)
        if code_verifier:
            flow.code_verifier = code_verifier

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get connected user profile email
        from googleapiclient.discovery import build
        userinfo_service = build('oauth2', 'v2', credentials=credentials)
        user_info = userinfo_service.userinfo().get().execute()

        save_gmail_credentials(credentials, user_info)
        flash(f"Successfully connected Gmail account: {user_info.get('email')}!", "success")
        return redirect(url_for('settings.index'))
    except Exception as e:
        flash(f"Failed to complete OAuth token exchange: {str(e)}", "danger")
        return redirect(url_for('settings.index'))

@gmail_bp.route('/disconnect/<int:account_id>', methods=['POST'])
@login_required
@permission_required('manage_settings')
def disconnect(account_id: int):
    """Disconnect Gmail Account."""
    disconnect_gmail_account(account_id)
    flash("Gmail account has been disconnected.", "info")
    return redirect(url_for('settings.index'))

# ==================== Gmail REST APIs ====================

@gmail_bp.route('/api/messages', methods=['GET'])
@login_required
@permission_required('view_emails')
def api_list_messages():
    """Search and retrieve Gmail messages."""
    query = request.args.get('q', 'label:INBOX')
    max_results = int(request.args.get('max_results', 20))
    res = gmail_msg.search_messages(query=query, max_results=max_results)
    return jsonify(res)

@gmail_bp.route('/api/messages/<message_id>', methods=['GET'])
@login_required
@permission_required('view_emails')
def api_get_message(message_id: str):
    """Retrieve full message details."""
    res = gmail_msg.get_message(message_id)
    return jsonify(res)

@gmail_bp.route('/api/threads/<thread_id>', methods=['GET'])
@login_required
@permission_required('view_emails')
def api_get_thread(thread_id: str):
    """Retrieve full thread conversation."""
    res = gmail_thr.get_thread(thread_id)
    return jsonify(res)

@gmail_bp.route('/api/send', methods=['POST'])
@login_required
@permission_required('send_emails')
def api_send_email():
    """Send an email."""
    data = request.get_json() or {}
    to = data.get('to')
    subject = data.get('subject')
    body_text = data.get('body_text', '')
    body_html = data.get('body_html', '')
    thread_id = data.get('thread_id')

    if not to or not subject:
        return jsonify({'error': 'Recipient and subject are required'}), 400

    res = gmail_msg.send_message(to=to, subject=subject, body_text=body_text, body_html=body_html, thread_id=thread_id)
    return jsonify(res)

@gmail_bp.route('/api/drafts', methods=['GET', 'POST'])
@login_required
@permission_required('manage_drafts')
def api_drafts():
    """List or create drafts."""
    if request.method == 'GET':
        return jsonify(gmail_msg.list_drafts())
    elif request.method == 'POST':
        data = request.get_json() or {}
        res = gmail_msg.create_draft(
            to=data.get('to', ''),
            subject=data.get('subject', ''),
            body_text=data.get('body_text', ''),
            body_html=data.get('body_html', ''),
            thread_id=data.get('thread_id')
        )
        return jsonify(res)

@gmail_bp.route('/api/actions/modify-labels', methods=['POST'])
@login_required
@permission_required('modify_labels')
def api_modify_labels():
    """Add or remove labels."""
    data = request.get_json() or {}
    msg_id = data.get('message_id')
    add_labels = data.get('add_labels')
    remove_labels = data.get('remove_labels')
    res = gmail_act.modify_labels(msg_id, add_labels=add_labels, remove_labels=remove_labels)
    return jsonify(res)

@gmail_bp.route('/api/actions/trash', methods=['POST'])
@login_required
@permission_required('modify_labels')
def api_trash():
    """Trash a message."""
    data = request.get_json() or {}
    msg_id = data.get('message_id')
    res = gmail_act.trash_message(msg_id)
    return jsonify(res)

# ==================== Instant Inbox AI Actions ====================

@gmail_bp.route('/api/ai-summarize', methods=['POST'])
@login_required
@permission_required('use_ai_chat')
def api_ai_summarize():
    """Instantly summarize an email or thread."""
    data = request.get_json() or {}
    msg_id = data.get('message_id')
    msg = gmail_msg.get_message(msg_id)
    if not msg.get('success'):
        return jsonify(msg), 400

    email_info = msg['message']
    prompt = f"""Summarize this email in 2-3 bullet points, highlighting key requests, dates, or action items:
From: {email_info.get('from')}
Subject: {email_info.get('subject')}
Body:
{email_info.get('body_text')}"""

    res = route_ai_request([{"role": "user", "content": prompt}])
    return jsonify({'success': res.get('success', False), 'summary': res.get('content', '')})

@gmail_bp.route('/api/ai-draft-reply', methods=['POST'])
@login_required
@permission_required('manage_drafts')
def api_ai_draft_reply():
    """Instantly generate an AI reply draft for a message."""
    data = request.get_json() or {}
    msg_id = data.get('message_id')
    instruction = data.get('instruction', 'Draft a professional and courteous reply acknowledging this email.')
    
    msg = gmail_msg.get_message(msg_id)
    if not msg.get('success'):
        return jsonify(msg), 400

    email_info = msg['message']
    system_prompt = build_system_prompt()
    user_prompt = f"""Email:
From: {email_info.get('from')}
Subject: {email_info.get('subject')}
Content:
{email_info.get('body_text')}

Instruction: {instruction}
Compose only the reply text."""

    res = route_ai_request([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    if res.get('success'):
        reply_content = res.get('content', '').strip()
        subject = f"Re: {email_info.get('subject')}"
        # Save as draft
        draft_res = gmail_msg.create_draft(
            to=email_info.get('from'),
            subject=subject,
            body_text=reply_content,
            thread_id=email_info.get('threadId')
        )
        return jsonify({
            'success': True,
            'reply_text': reply_content,
            'draft_id': draft_res.get('draft_id'),
            'to': email_info.get('from'),
            'subject': subject
        })

    return jsonify({'success': False, 'error': res.get('error', 'AI generation failed')})
