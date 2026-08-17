"""
Executive Intelligence Reports & Inbox Summary Generator.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from database.database import query_db, insert_db
from gmail import messages as gmail_msg
from ai.router import route_ai_request

def generate_daily_report() -> Dict[str, Any]:
    """Generate daily executive email summary report."""
    today_str = datetime.utcnow().strftime('%Y-%m-%d')

    # 1. Fetch Inbox Messages
    search_res = gmail_msg.search_messages(query="newer_than:1d", max_results=30)
    messages = search_res.get('messages', [])

    total_received = len(messages)
    unread_count = sum(1 for m in messages if m.get('is_unread'))
    important_count = sum(1 for m in messages if m.get('is_important'))

    # 2. Automation runs stats
    auto_runs = query_db(
        "SELECT status, confidence_score FROM automation_runs WHERE started_at >= ?",
        (today_str,)
    )
    total_auto_actions = len(auto_runs)
    successful_auto = sum(1 for r in auto_runs if r['status'] == 'COMPLETED')
    failed_auto = sum(1 for r in auto_runs if r['status'] == 'FAILED')

    # 3. AI Priority & Category Extraction
    msg_summaries = []
    for m in messages[:15]:
        msg_summaries.append(f"- From: {m.get('from')} | Subject: {m.get('subject')} | Snippet: {m.get('snippet')[:100]}")

    msg_text = "\n".join(msg_summaries) if msg_summaries else "No new messages received today."

    ai_prompt = f"""Analyze the following recent email summaries and generate a brief executive summary:
{msg_text}

Provide:
1. Top 3-5 Priority Items requiring human attention
2. Category Breakdown count (Business, Support, Meeting, Invoices, Other)
3. One-paragraph overall executive digest."""

    messages_payload = [
        {"role": "system", "content": "You are an executive inbox analytics assistant."},
        {"role": "user", "content": ai_prompt}
    ]

    ai_res = route_ai_request(messages_payload)
    summary_text = ai_res.get('content', 'Daily activity recorded.')

    report_data = {
        'date': today_str,
        'total_received': total_received,
        'unread_count': unread_count,
        'important_count': important_count,
        'automated_actions': total_auto_actions,
        'successful_auto': successful_auto,
        'failed_auto': failed_auto,
        'summary_text': summary_text
    }

    # Store in database
    report_id = insert_db(
        """INSERT INTO reports (report_type, title, summary_text, data_json, created_at)
           VALUES ('daily_summary', ?, ?, ?, ?)""",
        (f"Daily Email Report - {today_str}", summary_text, json.dumps(report_data), datetime.utcnow().isoformat())
    )
    report_data['id'] = report_id

    return report_data
