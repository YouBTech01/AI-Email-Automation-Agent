"""
Automation Trigger Evaluators.
"""
import re
from typing import Dict, Any

def evaluate_trigger(trigger_type: str, trigger_config: Dict[str, Any], email_data: Dict[str, Any]) -> bool:
    """Evaluate if an email matches the given trigger configuration."""
    if trigger_type == 'new_email':
        return True

    elif trigger_type == 'unread_email':
        return email_data.get('is_unread', False)

    elif trigger_type == 'sender_match':
        sender_pattern = trigger_config.get('sender', '').lower()
        from_field = email_data.get('from', '').lower()
        return sender_pattern in from_field

    elif trigger_type == 'keyword_match':
        keywords = trigger_config.get('keywords', [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(',') if k.strip()]
        
        subject = email_data.get('subject', '').lower()
        body = email_data.get('body_text', '').lower()
        combined = f"{subject} {body}"

        match_all = trigger_config.get('match_all', False)
        if match_all:
            return all(k.lower() in combined for k in keywords)
        return any(k.lower() in combined for k in keywords)

    elif trigger_type == 'has_attachment':
        attachments = email_data.get('attachments', [])
        return len(attachments) > 0

    elif trigger_type == 'label_match':
        target_label = trigger_config.get('label', '')
        labels = email_data.get('labels', [])
        return target_label in labels

    elif trigger_type.startswith('schedule_'):
        # Handled by time-based cron runner
        return True

    return False
