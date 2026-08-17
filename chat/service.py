"""
Chat Service: Multi-Turn Conversation Loop, Tool Calling, and Action Approvals.
"""
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from database.database import query_db, insert_db, execute_db, log_activity
from ai.prompts import build_system_prompt
from ai.tools import TOOL_DEFINITIONS, execute_tool
from ai.safety import classify_tool_risk, validate_tool_execution
from ai.router import route_ai_request
from chat.context import build_chat_history_messages

def handle_user_chat_message(
    session_id: int,
    user_id: int,
    user_message_text: str,
    preferred_provider_id: Optional[int] = None,
    preferred_model: Optional[str] = None
) -> Dict[str, Any]:
    """Process incoming user chat message, execute safe tools, and request confirmation for high-risk actions."""
    
    # 1. Save user message to database
    user_msg_id = insert_db(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES (?, 'user', ?, ?)""",
        (session_id, user_message_text, datetime.utcnow().isoformat())
    )

    # 2. Build system prompt + history
    system_prompt = build_system_prompt()
    history = build_chat_history_messages(session_id, max_turns=8)
    
    llm_messages = [{"role": "system", "content": system_prompt}] + history

    # 3. Call AI with tool definitions
    ai_resp = route_ai_request(
        messages=llm_messages,
        tools=TOOL_DEFINITIONS,
        preferred_provider_id=preferred_provider_id,
        preferred_model=preferred_model
    )

    if not ai_resp.get('success'):
        error_text = f"AI Error: {ai_resp.get('error', 'Unable to process request at this time.')}"
        asst_msg_id = insert_db(
            """INSERT INTO chat_messages (session_id, role, content, model, provider, created_at)
               VALUES (?, 'assistant', ?, ?, ?, ?)""",
            (session_id, error_text, ai_resp.get('model', 'unknown'), ai_resp.get('provider', 'unknown'), datetime.utcnow().isoformat())
        )
        return {
            'success': False,
            'message_id': asst_msg_id,
            'role': 'assistant',
            'content': error_text,
            'tool_calls': []
        }

    tool_calls = ai_resp.get('tool_calls', [])
    content = ai_resp.get('content', '')
    tokens = ai_resp.get('usage', {}).get('total_tokens', 0)
    model = ai_resp.get('model', '')
    provider = ai_resp.get('provider', '')

    # Case A: AI generated text answer without tools
    if not tool_calls:
        asst_msg_id = insert_db(
            """INSERT INTO chat_messages (session_id, role, content, model, provider, tokens, risk_tier, created_at)
               VALUES (?, 'assistant', ?, ?, ?, ?, 'LOW', ?)""",
            (session_id, content, model, provider, tokens, datetime.utcnow().isoformat())
        )
        return {
            'success': True,
            'message_id': asst_msg_id,
            'role': 'assistant',
            'content': content,
            'tool_calls': []
        }

    # Case B: AI requested tool calls
    tool_results_for_llm = []
    pending_actions = []

    for tc in tool_calls:
        func = tc.get('function', {})
        t_name = func.get('name')
        t_args_raw = func.get('arguments', '{}')
        try:
            t_args = json.loads(t_args_raw) if isinstance(t_args_raw, str) else t_args_raw
        except Exception:
            t_args = {}

        risk_tier = classify_tool_risk(t_name)

        # If HIGH risk: Gate behind user confirmation card
        if risk_tier == 'HIGH':
            pending_actions.append({
                'tool_call_id': tc.get('id', f"call_{int(time.time()*1000)}"),
                'tool_name': t_name,
                'tool_args': t_args,
                'risk_tier': risk_tier,
                'description': _generate_action_description(t_name, t_args)
            })
        else:
            # Low or Medium risk: execute immediately
            t_start = time.time()
            res = execute_tool(t_name, t_args)
            exec_time = int((time.time() - t_start) * 1000)

            tool_results_for_llm.append({
                'tool_call_id': tc.get('id'),
                'role': 'tool',
                'name': t_name,
                'content': json.dumps(res, default=str)
            })

    # If we have HIGH risk pending actions, pause and present confirmation card to user
    if pending_actions:
        pending_json = json.dumps(pending_actions)
        summary_msg = content or "I have prepared the following action for your review and confirmation:"
        asst_msg_id = insert_db(
            """INSERT INTO chat_messages (session_id, role, content, model, provider, tokens, risk_tier, pending_action_json, created_at)
               VALUES (?, 'assistant', ?, ?, ?, ?, 'HIGH', ?, ?)""",
            (session_id, summary_msg, model, provider, tokens, pending_json, datetime.utcnow().isoformat())
        )
        return {
            'success': True,
            'message_id': asst_msg_id,
            'role': 'assistant',
            'content': summary_msg,
            'pending_actions': pending_actions,
            'requires_confirmation': True
        }

    # If all tools were executed automatically, send tool outputs back to LLM for final response
    followup_messages = list(llm_messages)
    followup_messages.append({
        'role': 'assistant',
        'content': content,
        'tool_calls': tool_calls
    })
    followup_messages.extend(tool_results_for_llm)

    final_resp = route_ai_request(
        messages=followup_messages,
        preferred_provider_id=preferred_provider_id,
        preferred_model=preferred_model
    )

    final_content = final_resp.get('content', content or 'Action completed.')
    asst_msg_id = insert_db(
        """INSERT INTO chat_messages (session_id, role, content, model, provider, tokens, risk_tier, created_at)
           VALUES (?, 'assistant', ?, ?, ?, ?, 'LOW', ?)""",
        (session_id, final_content, model, provider, tokens, datetime.utcnow().isoformat())
    )

    return {
        'success': True,
        'message_id': asst_msg_id,
        'role': 'assistant',
        'content': final_content,
        'tool_calls': [t['name'] for t in tool_results_for_llm]
    }

def execute_confirmed_chat_action(message_id: int, approved: bool, user_id: int) -> Dict[str, Any]:
    """Execute or reject a pending high-risk tool call after user confirmation."""
    msg = query_db("SELECT * FROM chat_messages WHERE id = ?", (message_id,), one=True)
    if not msg or not msg['pending_action_json']:
        return {'success': False, 'error': 'Pending action not found for this message.'}

    pending_actions = json.loads(msg['pending_action_json'])
    session_id = msg['session_id']

    if not approved:
        # User rejected the action
        execute_db("UPDATE chat_messages SET pending_action_json = NULL, risk_tier = 'REJECTED' WHERE id = ?", (message_id,))
        reject_msg_id = insert_db(
            """INSERT INTO chat_messages (session_id, role, content, created_at)
               VALUES (?, 'assistant', 'The action was cancelled.', ?)""",
            (session_id, datetime.utcnow().isoformat())
        )
        return {'success': True, 'approved': False, 'message': 'Action cancelled.'}

    results = []
    for pa in pending_actions:
        t_name = pa.get('tool_name')
        t_args = pa.get('tool_args', {})
        res = execute_tool(t_name, t_args)
        results.append({'tool': t_name, 'result': res})
        log_activity('AI', f"User Confirmed Action Executed: {t_name}", actor=f"user_{user_id}", details=t_args)

    # Clear pending state and record execution
    execute_db("UPDATE chat_messages SET pending_action_json = NULL, risk_tier = 'EXECUTED' WHERE id = ?", (message_id,))
    
    confirm_text = f"Action confirmed and executed successfully: {', '.join([r['tool'] for r in results])}"
    insert_db(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES (?, 'assistant', ?, ?)""",
        (session_id, confirm_text, datetime.utcnow().isoformat())
    )

    return {'success': True, 'approved': True, 'results': results, 'message': confirm_text}

def _generate_action_description(tool_name: str, tool_args: dict) -> str:
    """Generate a clean human-readable summary of the pending action."""
    if tool_name == 'gmail_send':
        return f"Send email to **{tool_args.get('to')}** with subject *\"{tool_args.get('subject')}\"*"
    if tool_name == 'gmail_reply':
        return f"Send reply to email (Message ID: {tool_args.get('message_id')})"
    if tool_name == 'gmail_forward':
        return f"Forward email to **{tool_args.get('to')}**"
    if tool_name == 'gmail_trash':
        return f"Move message **{tool_args.get('message_id')}** to Gmail Trash"
    return f"Execute {tool_name} with arguments {json.dumps(tool_args)}"
