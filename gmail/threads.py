"""
Gmail Thread Operations and Conversation Reconstruction.
"""
from typing import Dict, Any, Optional
from gmail.client import get_gmail_service, parse_gmail_error
from gmail.messages import _parse_message_payload

def get_thread(thread_id: str, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Retrieve full email conversation thread with all ordered messages."""
    service = get_gmail_service(account_id)
    if not service:
        return {'success': False, 'error': 'Gmail account not connected.'}

    try:
        raw_thread = service.users().threads().get(userId='me', id=thread_id, format='full').execute()
        raw_messages = raw_thread.get('messages', [])
        
        parsed_messages = []
        participants = set()

        for msg in raw_messages:
            parsed = _parse_message_payload(msg)
            parsed_messages.append(parsed)
            if parsed.get('from'):
                participants.add(parsed['from'])
            if parsed.get('to'):
                participants.add(parsed['to'])

        subject = parsed_messages[0]['subject'] if parsed_messages else '(No Subject)'

        return {
            'success': True,
            'thread_id': thread_id,
            'subject': subject,
            'message_count': len(parsed_messages),
            'participants': list(participants),
            'messages': parsed_messages
        }
    except Exception as e:
        err = parse_gmail_error(e)
        return {'success': False, 'error': err['user_friendly'], 'raw_error': err['message']}
