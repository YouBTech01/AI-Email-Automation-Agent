"""
Gmail Label Modifications, Archive, Trash, and Organization Actions.
"""
from typing import List, Dict, Any, Optional
from gmail.client import get_gmail_service, parse_gmail_error
from database.database import log_activity

def modify_labels(message_id: str, add_labels: Optional[List[str]] = None, 
                  remove_labels: Optional[List[str]] = None, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Add or remove labels from a Gmail message."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}

    body = {
        'addLabelIds': add_labels or [],
        'removeLabelIds': remove_labels or []
    }

    try:
        updated = service.users().messages().modify(userId='me', id=message_id, body=body).execute()
        log_activity('GMAIL', 'Labels Modified', actor='ai-agent', details={
            'messageId': message_id, 'added': add_labels, 'removed': remove_labels
        })
        return {'success': True, 'labels': updated.get('labelIds', [])}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message']}

def archive_message(message_id: str, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Archive a message by removing it from the INBOX."""
    return modify_labels(message_id, remove_labels=['INBOX'], account_id=account_id)

def mark_as_read(message_id: str, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Mark a message as read by removing UNREAD label."""
    return modify_labels(message_id, remove_labels=['UNREAD'], account_id=account_id)

def mark_as_unread(message_id: str, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Mark a message as unread by adding UNREAD label."""
    return modify_labels(message_id, add_labels=['UNREAD'], account_id=account_id)

def trash_message(message_id: str, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Move a message to the Gmail Trash (HIGH RISK ACTION)."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}

    try:
        service.users().messages().trash(userId='me', id=message_id).execute()
        log_activity('GMAIL', 'Message Trashed', actor='ai-agent', details={'messageId': message_id})
        return {'success': True}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message']}

def untrash_message(message_id: str, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Restore a message from Trash."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}

    try:
        service.users().messages().untrash(userId='me', id=message_id).execute()
        log_activity('GMAIL', 'Message Restored from Trash', actor='ai-agent', details={'messageId': message_id})
        return {'success': True}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message']}

def list_labels(account_id: Optional[int] = None) -> Dict[str, Any]:
    """Fetch all user and system labels from Gmail."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.', 'labels': []}

    try:
        resp = service.users().labels().list(userId='me').execute()
        return {'success': True, 'labels': resp.get('labels', [])}
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'labels': []}
