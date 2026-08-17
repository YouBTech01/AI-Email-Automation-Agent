"""
Dashboard Blueprint: Real-time Stats, Overview, and Quick Actions.
"""
from datetime import datetime
from flask import Blueprint, render_template, jsonify
from auth.middleware import login_required, get_current_user
from database.database import query_db
from gmail import messages as gmail_msg

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main Dashboard View with Metric Cards and Recent Activity."""
    user = get_current_user()
    today_str = datetime.utcnow().strftime('%Y-%m-%d')

    # Primary Gmail account status
    gmail_acc = query_db("SELECT * FROM gmail_accounts WHERE is_primary = 1 AND is_connected = 1", one=True)
    
    # AI Provider status
    ai_prov = query_db("SELECT * FROM ai_providers WHERE is_primary = 1 AND is_active = 1", one=True)

    # Active automations count
    active_automations = query_db("SELECT COUNT(*) as count FROM automations WHERE status = 'ACTIVE'", one=True)['count']

    # Today's automated runs
    today_runs = query_db(
        "SELECT COUNT(*) as count, SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as success_count FROM automation_runs WHERE started_at >= ?",
        (today_str,),
        one=True
    )
    total_runs_today = today_runs['count'] or 0
    successful_runs_today = today_runs['success_count'] or 0

    # Recent activity logs
    recent_logs = query_db("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 10")

    # Recent automations
    recent_automations = query_db("SELECT * FROM automations ORDER BY updated_at DESC LIMIT 5")

    # Inbox preview (if Gmail connected)
    inbox_preview = []
    unread_count = 0
    if gmail_acc:
        res = gmail_msg.search_messages(query="label:INBOX", max_results=5)
        if res.get('success'):
            inbox_preview = res.get('messages', [])
            unread_count = sum(1 for m in inbox_preview if m.get('is_unread'))

    return render_template(
        'dashboard/index.html',
        user=user,
        gmail_acc=gmail_acc,
        ai_prov=ai_prov,
        active_automations=active_automations,
        total_runs_today=total_runs_today,
        successful_runs_today=successful_runs_today,
        unread_count=unread_count,
        recent_logs=recent_logs,
        recent_automations=recent_automations,
        inbox_preview=inbox_preview
    )

@dashboard_bp.route('/inbox')
@login_required
def inbox():
    """Full Gmail Inbox Browser and Thread Viewer."""
    user = get_current_user()
    gmail_acc = query_db("SELECT * FROM gmail_accounts WHERE is_primary = 1 AND is_connected = 1", one=True)
    return render_template('dashboard/inbox.html', user=user, gmail_acc=gmail_acc)
