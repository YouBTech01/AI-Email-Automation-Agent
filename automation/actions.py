"""
Automation Action Executors: Draft Generation, Safe Reply, Labelling, Archiving.
"""
import json
from typing import Dict, Any
from gmail import messages as gmail_msg, actions as gmail_act
from ai.router import route_ai_request
from ai.prompts import build_system_prompt
from database.database import log_activity, query_db

def generate_ai_reply_text(email_data: Dict[str, Any], prompt_instruction: str = '') -> str:
    """Generate professional AI reply according to behavioral rules and email content."""
    system_prompt = build_system_prompt()
    sender = email_data.get('from', '')
    subject = email_data.get('subject', '')
    body = email_data.get('body_text', '')

    user_prompt = f"""Incoming Email:
From: {sender}
Subject: {subject}
Content:
{body}

Instruction:
{prompt_instruction or "Draft a helpful, professional, and clear reply to this email, addressing the sender's inquiry according to our company rules and guidelines."}

Return ONLY the reply email body text (do not include subject headers)."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    res = route_ai_request(messages)
    if res.get('success'):
        return res.get('content', '').strip()
    return "Thank you for reaching out. We have received your email and will get back to you shortly."

def execute_automation_action(
    action: Dict[str, Any],
    automation: Dict[str, Any],
    email_data: Dict[str, Any],
    ai_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute action with safeguard approval mode check."""
    action_type = action.get('action_type')
    config = json.loads(action.get('config_json', '{}')) if isinstance(action.get('config_json'), str) else (action.get('config_json') or {})
    approval_mode = automation.get('approval_mode', 'draft_only')
    confidence = ai_analysis.get('confidence', 0)
    threshold = automation.get('confidence_threshold', 85)

    msg_id = email_data.get('id')
    thread_id = email_data.get('threadId')
    to = email_data.get('from')
    subject = email_data.get('subject', '')
    if not subject.lower().startswith('re:'):
        subject = f"Re: {subject}"

    # 1. Reply / Draft actions
    if action_type in ('generate_reply', 'generate_draft', 'send_reply'):
        instruction = config.get('instruction', '')
        generated_reply = generate_ai_reply_text(email_data, instruction)

        # Level 1: Draft Only
        if approval_mode == 'draft_only' or action_type == 'generate_draft':
            draft_res = gmail_msg.create_draft(
                to=to,
                subject=subject,
                body_text=generated_reply,
                thread_id=thread_id
            )
            return {
                'success': True,
                'action_taken': 'draft_created',
                'draft_id': draft_res.get('draft_id'),
                'reply_content': generated_reply,
                'summary': f"Created draft reply for {to} (Confidence: {confidence}%)"
            }

        # Level 2: Approval Required
        elif approval_mode == 'approval_required':
            return {
                'success': True,
                'action_taken': 'pending_approval',
                'reply_content': generated_reply,
                'summary': f"Reply generated for {to}. Waiting for admin approval."
            }

        # Level 3: Trusted Automation
        elif approval_mode == 'trusted_auto':
            if confidence >= threshold:
                send_res = gmail_msg.send_message(
                    to=to,
                    subject=subject,
                    body_text=generated_reply,
                    thread_id=thread_id
                )
                if send_res.get('success'):
                    return {
                        'success': True,
                        'action_taken': 'reply_sent',
                        'message_id': send_res.get('message_id'),
                        'reply_content': generated_reply,
                        'summary': f"Auto-replied to {to} (Confidence: {confidence}%)"
                    }
                return send_res
            else:
                # Confidence too low -> Fallback to Draft
                draft_res = gmail_msg.create_draft(to=to, subject=subject, body_text=generated_reply, thread_id=thread_id)
                return {
                    'success': True,
                    'action_taken': 'draft_created_confidence_fallback',
                    'draft_id': draft_res.get('draft_id'),
                    'reply_content': generated_reply,
                    'summary': f"Confidence {confidence}% was below threshold {threshold}%. Draft saved instead of auto-sending."
                }

    # 2. Add Label
    elif action_type == 'add_label':
        label = config.get('label', '')
        res = gmail_act.modify_labels(msg_id, add_labels=[label])
        return {'success': res.get('success', False), 'action_taken': f"add_label_{label}"}

    # 3. Archive
    elif action_type == 'archive':
        res = gmail_act.archive_message(msg_id)
        return {'success': res.get('success', False), 'action_taken': 'archived'}

    # 4. Forward
    elif action_type == 'forward':
        forward_to = config.get('forward_to', '')
        note = config.get('note', '')
        res = gmail_msg.send_message(
            to=forward_to,
            subject=f"Fwd: {email_data.get('subject')}",
            body_text=f"{note}\n\n---------- Forwarded ----------\nFrom: {to}\n\n{email_data.get('body_text')}"
        )
        return {'success': res.get('success', False), 'action_taken': f"forwarded_to_{forward_to}"}

    return {'success': False, 'error': f"Unknown action type: {action_type}"}
