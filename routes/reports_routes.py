"""
Reports Blueprint: Intelligence Digest and Priority Analytics.
"""
from flask import Blueprint, render_template, jsonify
from auth.middleware import login_required, get_current_user
from database.database import query_db
from reports.service import generate_daily_report

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def index():
    """Intelligence Reports Catalog."""
    user = get_current_user()
    reports = query_db("SELECT * FROM reports ORDER BY id DESC LIMIT 20")
    return render_template('reports/index.html', user=user, reports=reports)

@reports_bp.route('/api/generate-daily', methods=['POST'])
@login_required
def api_generate():
    """Trigger on-demand daily intelligence report generation."""
    report = generate_daily_report()
    return jsonify({'success': True, 'report': report})
