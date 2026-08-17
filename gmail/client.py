"""
Gmail Service Builder and API Client wrapper.
"""
from typing import Optional, Any
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from gmail.auth import get_gmail_credentials
from database.database import log_activity

def get_gmail_service(account_id: Optional[int] = None) -> Optional[Resource]:
    """Build and return an authorized Gmail API service Resource."""
    creds = get_gmail_credentials(account_id)
    if not creds:
        return None
    try:
        service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
        return service
    except Exception as e:
        log_activity('GMAIL', 'Failed to Build Gmail Service', actor='system', details={'error': str(e)}, status='FAILED')
        return None

def parse_gmail_error(error: Exception) -> dict:
    """Format and classify Gmail API errors into structured error responses."""
    if isinstance(error, HttpError):
        status_code = error.resp.status
        reason = error._get_reason() if hasattr(error, '_get_reason') else str(error)
        
        category = 'API_ERROR'
        if status_code in (401, 403):
            category = 'AUTH_ERROR'
        elif status_code == 429:
            category = 'RATE_LIMIT'
        elif status_code == 404:
            category = 'NOT_FOUND'

        return {
            'category': category,
            'status_code': status_code,
            'message': reason,
            'user_friendly': _friendly_message(category, reason)
        }
    return {
        'category': 'UNKNOWN_ERROR',
        'status_code': 500,
        'message': str(error),
        'user_friendly': 'An unexpected error occurred while communicating with Gmail.'
    }

def _friendly_message(category: str, raw_reason: str) -> str:
    if category == 'AUTH_ERROR':
        return 'Gmail authorization has expired or is invalid. Please reconnect your Gmail account in Settings.'
    if category == 'RATE_LIMIT':
        return 'Gmail API rate limit exceeded. Please wait a few moments before retrying.'
    if category == 'NOT_FOUND':
        return 'The requested email, thread, or draft was not found in Gmail.'
    return f"Gmail API error: {raw_reason}"
