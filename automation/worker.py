"""
Automation Worker: Polling, Gmail Inbox Checking, and Trigger Dispatcher.
"""
from datetime import datetime
from typing import Dict, Any
from database.database import query_db, execute_db, log_activity
from gmail import messages as gmail_msg
from automation.engine import run_automations_on_email

def run_automation_worker_cycle(max_emails: int = 15) -> Dict[str, Any]:
    """Single-pass execution cycle for automation engine (ideal for cPanel Cron & APScheduler)."""
    # 1. Check if primary Gmail account is connected
    account = query_db("SELECT id, email, is_connected, last_sync_at FROM gmail_accounts WHERE is_connected = 1 AND is_primary = 1", one=True)
    if not account:
        account = query_db("SELECT id, email, is_connected, last_sync_at FROM gmail_accounts WHERE is_connected = 1 ORDER BY id ASC", one=True)
        if not account:
            return {'success': False, 'message': 'No connected Gmail accounts found. Skipping cycle.'}

    # 2. Check for active automations
    active_count = query_db("SELECT COUNT(*) as c FROM automations WHERE status = 'ACTIVE'", one=True)['c']
    if active_count == 0:
        return {'success': True, 'message': 'No active automations configured.', 'processed': 0}

    # 3. Fetch recent inbox messages from Gmail
    search_res = gmail_msg.search_messages(query="label:INBOX", max_results=max_emails, account_id=account['id'])
    if not search_res.get('success'):
        return {'success': False, 'error': search_res.get('error', 'Failed to retrieve messages from Gmail')}

    messages = search_res.get('messages', [])
    processed_count = 0
    triggered_runs = []

    for m in messages:
        runs = run_automations_on_email(m)
        if runs:
            triggered_runs.extend(runs)
            processed_count += 1

    # Update sync timestamp
    execute_db("UPDATE gmail_accounts SET last_sync_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), account['id']))

    return {
        'success': True,
        'emails_checked': len(messages),
        'automations_triggered': len(triggered_runs),
        'runs': triggered_runs
    }
