"""
Activity & Audit Logs Blueprint: Log Browser, Filter Engine, and Data Export.
"""
import io
import csv
import json
from flask import Blueprint, render_template, request, jsonify, Response
from auth.middleware import login_required, permission_required, get_current_user
from database.database import query_db

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@logs_bp.route('/')
@login_required
@permission_required('view_logs')
def index():
    """System Activity & Audit Log Viewer."""
    user = get_current_user()
    category = request.args.get('category', 'ALL')
    status = request.args.get('status', 'ALL')

    query = "SELECT * FROM activity_logs WHERE 1=1"
    params = []

    if category != 'ALL':
        query += " AND category = ?"
        params.append(category.upper())

    if status != 'ALL':
        query += " AND status = ?"
        params.append(status.upper())

    query += " ORDER BY id DESC LIMIT 100"
    logs = query_db(query, params)

    return render_template('logs/index.html', user=user, logs=logs, current_cat=category, current_status=status)

@logs_bp.route('/export/csv')
@login_required
@permission_required('view_logs')
def export_csv():
    """Export activity logs to CSV format."""
    logs = query_db("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 500")
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Timestamp', 'Category', 'Action', 'Actor', 'Status', 'IP Address', 'Details'])

    for l in logs:
        writer.writerow([
            l['id'], l['created_at'], l['category'], l['action'], 
            l['actor'], l['status'], l['ip_address'], l['details_json']
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=activity_logs.csv"}
    )
