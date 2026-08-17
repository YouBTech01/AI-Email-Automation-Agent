"""
Automation Condition Evaluators & AI Sentiment/Intent Analyzer.
"""
import json
import re
from typing import Dict, Any, List, Optional
from ai.router import route_ai_request

def analyze_email_with_ai(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze email content for intent, category, urgency, and confidence score."""
    subject = email_data.get('subject', '')
    body = email_data.get('body_text', '')[:2000] # Trim for fast processing
    sender = email_data.get('from', '')

    system_prompt = """You are an email analysis AI for an automated inbox manager.
Classify the given email and return a strictly valid JSON object with the following fields:
- "category": One of ["customer_support", "business_inquiry", "payment_invoice", "meeting_request", "newsletter", "spam", "refund_request", "other"]
- "sentiment": One of ["positive", "neutral", "negative", "urgent"]
- "is_urgent": boolean
- "requires_reply": boolean
- "confidence": integer between 0 and 100 representing your classification certainty
- "reasoning": brief one-sentence explanation of your assessment
- "suggested_action": One of ["reply", "draft_reply", "archive", "escalate_to_human", "ignore"]
"""

    user_prompt = f"From: {sender}\nSubject: {subject}\n\nBody:\n{body}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    res = route_ai_request(messages, preferred_model='openai/gpt-4o-mini')
    if res.get('success'):
        content = res.get('content', '').strip()
        try:
            # Extract JSON block if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            parsed = json.loads(content)
            return parsed
        except Exception:
            pass

    # Fallback default analysis if parsing fails
    return {
        "category": "business_inquiry",
        "sentiment": "neutral",
        "is_urgent": False,
        "requires_reply": True,
        "confidence": 75,
        "reasoning": "Standard heuristic classification fallback.",
        "suggested_action": "draft_reply"
    }

def evaluate_conditions(conditions: List[Dict[str, Any]], email_data: Dict[str, Any], ai_analysis: Optional[Dict[str, Any]] = None) -> bool:
    """Evaluate all conditions for an automation (AND logic)."""
    if not conditions:
        return True

    for cond in conditions:
        field = cond.get('field')
        operator = cond.get('operator')
        target_val = cond.get('value', '').lower()

        # Extract source field value
        if field in ('sender', 'from'):
            actual_val = email_data.get('from', '').lower()
        elif field == 'subject':
            actual_val = email_data.get('subject', '').lower()
        elif field == 'body':
            actual_val = email_data.get('body_text', '').lower()
        elif field == 'ai_category' and ai_analysis:
            actual_val = ai_analysis.get('category', '').lower()
        elif field == 'ai_confidence' and ai_analysis:
            actual_val = str(ai_analysis.get('confidence', 0))
        elif field == 'has_attachment':
            actual_val = 'true' if len(email_data.get('attachments', [])) > 0 else 'false'
        else:
            actual_val = ''

        # Evaluate Operator
        if operator == 'contains':
            if target_val not in actual_val:
                return False
        elif operator == 'not_contains':
            if target_val in actual_val:
                return False
        elif operator == 'equals':
            if actual_val != target_val:
                return False
        elif operator == 'not_equals':
            if actual_val == target_val:
                return False
        elif operator == 'matches_regex':
            try:
                if not re.search(target_val, actual_val, re.IGNORECASE):
                    return False
            except Exception:
                return False
        elif operator == 'greater_than':
            try:
                if float(actual_val) <= float(target_val):
                    return False
            except Exception:
                return False
        elif operator == 'less_than':
            try:
                if float(actual_val) >= float(target_val):
                    return False
            except Exception:
                return False

    return True
