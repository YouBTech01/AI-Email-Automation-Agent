"""
Flask Application Factory, Blueprint Registrations, Error Handlers, and Scheduler.
"""
import os
import sys
from flask import Flask, render_template, session, g
from config.settings import SECRET_KEY, DB_FILE, SESSION_COOKIE_NAME, SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE, SESSION_COOKIE_SECURE, ENABLE_BACKGROUND_SCHEDULER
from database.database import init_db, query_db
from auth.middleware import generate_csrf_token, get_current_user

# Import Blueprints
from auth.routes import auth_bp
from routes.dashboard import dashboard_bp
from routes.gmail_routes import gmail_bp
from routes.automation_routes import automation_bp
from chat.routes import chat_bp
from routes.training_routes import training_bp
from routes.templates_routes import templates_bp
from routes.contacts_routes import contacts_bp
from routes.logs_routes import logs_bp
from routes.reports_routes import reports_bp
from routes.settings_routes import settings_bp

def create_app() -> Flask:
    """Create and configure Flask application instance."""
    app = Flask(__name__)
    
    # App Security & Session Config
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['SESSION_COOKIE_NAME'] = SESSION_COOKIE_NAME
    app.config['SESSION_COOKIE_HTTPONLY'] = SESSION_COOKIE_HTTPONLY
    app.config['SESSION_COOKIE_SAMESITE'] = SESSION_COOKIE_SAMESITE
    app.config['SESSION_COOKIE_SECURE'] = SESSION_COOKIE_SECURE
    app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB max upload

    # Initialize SQLite Database & Tables
    with app.app_context():
        init_db()

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(gmail_bp)
    app.register_blueprint(automation_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)

    # Context Processors for Templates
    @app.context_processor
    def inject_global_template_vars():
        user = get_current_user()
        gmail_acc = None
        ai_prov = None
        if user:
            gmail_acc = query_db("SELECT email, display_name, is_connected FROM gmail_accounts WHERE is_primary = 1 AND is_connected = 1", one=True)
            ai_prov = query_db("SELECT name, display_name, default_model FROM ai_providers WHERE is_primary = 1 AND is_active = 1", one=True)

        return {
            'csrf_token': generate_csrf_token,
            'current_user': user,
            'connected_gmail': gmail_acc,
            'active_ai_provider': ai_prov,
            'app_version': '1.0.0'
        }

    # Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html', description=getattr(error, 'description', 'Access forbidden.')), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    # Optional In-App Background Scheduler for Dev / VPS
    if ENABLE_BACKGROUND_SCHEDULER and os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from automation.worker import run_automation_worker_cycle
            
            scheduler = BackgroundScheduler(daemon=True)
            scheduler.add_job(func=run_automation_worker_cycle, trigger="interval", seconds=120, id="gmail_sync_job")
            scheduler.start()
        except Exception as e:
            print(f"Background scheduler initialization notice: {e}")

    return app

def main():
    """CLI entry point to launch the AI Email Automation Agent server."""
    application = create_app()
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    print(f"Starting AI Email Automation Agent on http://{host}:{port}")
    application.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    main()

