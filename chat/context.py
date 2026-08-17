"""
Chat Context Resolution: Email Reference Mapping and Multi-Turn Memory.
"""
from typing import Dict, Any, List, Optional
from database.database import query_db

def build_chat_history_messages(session_id: int, max_turns: int = 10) -> List[Dict[str, Any]]:
    """Fetch and format recent messages for the LLM context."""
    raw_msgs = query_db(
        """SELECT role, content, pending_action_json FROM chat_messages 
           WHERE session_id = ? 
           ORDER BY id ASC""",
        (session_id,)
    )

    # Take the last N messages
    selected = raw_msgs[-max_turns*2:] if len(raw_msgs) > max_turns*2 else raw_msgs
    formatted = []

    for m in selected:
        role = m['role']
        content = m['content'] or ''
        
        # If there was a pending action, append its summary to context
        if m.get('pending_action_json'):
            content += f"\n[System Note: Action proposed: {m['pending_action_json']}]"

        if role in ('user', 'assistant', 'system'):
            formatted.append({'role': role, 'content': content})

    return formatted
