"""
Gmail Message Operations: Search, Read, Parse MIME, Send, Reply, Drafts.
"""
import base64
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional, Tuple
from gmail.client import get_gmail_service, parse_gmail_error
from database.database import log_activity

def search_messages(query: str = '', max_results: int = 20, 
                    include_spam_trash: bool = False, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Search messages in Gmail matching query."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected or authorized.', 'messages': []}

    try:
        req = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=min(max_results, 100),
            includeSpamTrash=include_spam_trash
        )
        response = req.execute()
        messages_meta = response.get('messages', [])
        
        results = []
        for meta in messages_meta:
            msg_details = get_message(meta['id'], format='metadata', account_id=account_id)
            if msg_details.get('success'):
                results.append(msg_details['message'])

        return {
            'success': True,
            'messages': results,
            'resultSizeEstimate': response.get('resultSizeEstimate', len(results)),
            'nextPageToken': response.get('nextPageToken')
        }
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message'], 'messages': []}

def get_message(message_id: str, format: str = 'full', account_id: Optional[int] = None) -> Dict[str, Any]:
    """Retrieve and parse a specific Gmail message by ID."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}

    try:
        raw_msg = service.users().messages().get(userId='me', id=message_id, format=format).execute()
        parsed = _parse_message_payload(raw_msg)
        return {'success': True, 'message': parsed}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message']}

def _parse_message_payload(msg_data: dict) -> dict:
    """Extract headers, plain body, HTML body, labels, and attachment metadata."""
    headers_list = msg_data.get('payload', {}).get('headers', [])
    headers = {h['name'].lower(): h['value'] for h in headers_list}

    subject = headers.get('subject', '(No Subject)')
    sender = headers.get('from', '')
    recipient = headers.get('to', '')
    cc = headers.get('cc', '')
    bcc = headers.get('bcc', '')
    date_str = headers.get('date', '')
    message_id_header = headers.get('message-id', '')
    in_reply_to = headers.get('in-reply-to', '')
    references = headers.get('references', '')

    body_text = ''
    body_html = ''
    attachments = []

    payload = msg_data.get('payload', {})
    body_text, body_html, attachments = _extract_parts(payload)

    snippet = msg_data.get('snippet', '')
    labels = msg_data.get('labelIds', [])

    return {
        'id': msg_data.get('id'),
        'threadId': msg_data.get('threadId'),
        'subject': subject,
        'from': sender,
        'to': recipient,
        'cc': cc,
        'bcc': bcc,
        'date': date_str,
        'snippet': snippet,
        'body_text': body_text.strip(),
        'body_html': body_html.strip(),
        'has_html': bool(body_html),
        'attachments': attachments,
        'labels': labels,
        'is_unread': 'UNREAD' in labels,
        'is_important': 'IMPORTANT' in labels or 'STARRED' in labels,
        'message_id_header': message_id_header,
        'in_reply_to': in_reply_to,
        'references': references
    }

def _extract_parts(part: dict) -> Tuple[str, str, List[dict]]:
    """Recursively extract plain text, HTML, and attachment items from MIME parts."""
    text_content = ''
    html_content = ''
    attachments = []

    mime_type = part.get('mimeType', '')
    filename = part.get('filename', '')
    body = part.get('body', {})

    if filename:
        attachments.append({
            'filename': filename,
            'mimeType': mime_type,
            'size': body.get('size', 0),
            'attachmentId': body.get('attachmentId')
        })

    if 'data' in body:
        decoded_bytes = base64.urlsafe_b64decode(body['data'].encode('ASCII'))
        try:
            content = decoded_bytes.decode('utf-8', errors='replace')
        except Exception:
            content = str(decoded_bytes)
        
        if mime_type == 'text/plain':
            text_content += content + '\n'
        elif mime_type == 'text/html':
            html_content += content + '\n'

    for subpart in part.get('parts', []):
        sub_text, sub_html, sub_att = _extract_parts(subpart)
        text_content += sub_text
        html_content += sub_html
        attachments.extend(sub_att)

    return text_content, html_content, attachments

def send_message(to: str, subject: str, body_html: str = '', body_text: str = '',
                 cc: str = '', bcc: str = '', in_reply_to: str = '', references: str = '',
                 thread_id: Optional[str] = None, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Send an email message via Gmail API."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}

    try:
        msg = MIMEMultipart('alternative')
        msg['To'] = to
        msg['Subject'] = subject
        if cc:
            msg['Cc'] = cc
        if bcc:
            msg['Bcc'] = bcc
        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to
        if references:
            msg['References'] = references

        if body_text:
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))
        elif not body_text:
            msg.attach(MIMEText('', 'plain', 'utf-8'))

        raw_data = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        body_payload: Dict[str, Any] = {'raw': raw_data}
        if thread_id:
            body_payload['threadId'] = thread_id

        sent_msg = service.users().messages().send(userId='me', body=body_payload).execute()
        
        log_activity('GMAIL', 'Email Sent', actor='ai-agent', details={
            'to': to, 'subject': subject, 'threadId': thread_id or sent_msg.get('threadId'),
            'messageId': sent_msg.get('id')
        })

        return {'success': True, 'message_id': sent_msg.get('id'), 'thread_id': sent_msg.get('threadId')}
    except Exception as e:
        err = parse_gmail_error(e)
        log_activity('GMAIL', 'Email Send Failed', actor='ai-agent', details={'error': err['message']}, status='FAILED')
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message']}

def create_draft(to: str, subject: str, body_html: str = '', body_text: str = '',
                 thread_id: Optional[str] = None, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Create a new Gmail draft."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}

    try:
        msg = MIMEMultipart('alternative')
        msg['To'] = to
        msg['Subject'] = subject
        if body_text:
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))
        elif not body_text:
            msg.attach(MIMEText('', 'plain', 'utf-8'))

        raw_data = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        draft_body: Dict[str, Any] = {'message': {'raw': raw_data}}
        if thread_id:
            draft_body['message']['threadId'] = thread_id

        created_draft = service.users().drafts().create(userId='me', body=draft_body).execute()
        
        log_activity('GMAIL', 'Draft Created', actor='ai-agent', details={
            'to': to, 'subject': subject, 'draftId': created_draft.get('id')
        })

        return {'success': True, 'draft_id': created_draft.get('id'), 'message_id': created_draft.get('message', {}).get('id')}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message']}

def update_draft(draft_id: str, to: str, subject: str, body_html: str = '', body_text: str = '',
                 account_id: Optional[int] = None) -> Dict[str, Any]:
    """Update an existing Gmail draft."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}

    try:
        msg = MIMEMultipart('alternative')
        msg['To'] = to
        msg['Subject'] = subject
        if body_text:
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))
        elif not body_text:
            msg.attach(MIMEText('', 'plain', 'utf-8'))

        raw_data = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        draft_body = {'id': draft_id, 'message': {'raw': raw_data}}

        updated = service.users().drafts().update(userId='me', id=draft_id, body=draft_body).execute()
        log_activity('GMAIL', 'Draft Updated', actor='ai-agent', details={'draftId': draft_id})
        return {'success': True, 'draft_id': updated.get('id')}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message']}

def list_drafts(max_results: int = 20, account_id: Optional[int] = None) -> Dict[str, Any]:
    """List drafts in Gmail."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.', 'drafts': []}

    try:
        resp = service.users().drafts().list(userId='me', maxResults=max_results).execute()
        drafts_list = resp.get('drafts', [])
        results = []
        for item in drafts_list:
            d_id = item['id']
            msg_data = item.get('message', {})
            parsed = _parse_message_payload(msg_data)
            parsed['draft_id'] = d_id
            results.append(parsed)
        return {'success': True, 'drafts': results}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'drafts': []}

def delete_draft(draft_id: str, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Delete a draft."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}
    try:
        service.users().drafts().delete(userId='me', id=draft_id).execute()
        log_activity('GMAIL', 'Draft Deleted', actor='ai-agent', details={'draftId': draft_id})
        return {'success': True}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly']}
