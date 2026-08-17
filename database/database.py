"""
Database connection, initialization, migrations, and query execution helpers.
"""
import sqlite3
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from werkzeug.security import generate_password_hash
from config.settings import DB_FILE, BACKUPS_DIR
from config.providers import SUPPORTED_PROVIDERS
from database.models import SCHEMA_SQL
from database.crypto import encrypt_value, decrypt_value

import contextlib

@contextlib.contextmanager
def get_db_connection():
    """Context manager for SQLite database connection with row factory and auto-close."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()

def query_db(query: str, args: Union[Tuple, List] = (), one: bool = False) -> Any:
    """Execute a SELECT query and return dict or list of dicts."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        cur.close()
        if one:
            return dict(rv[0]) if rv else None
        return [dict(row) for row in rv]

def execute_db(query: str, args: Union[Tuple, List] = ()) -> int:
    """Execute an INSERT, UPDATE, or DELETE query and return rows affected."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, args)
        conn.commit()
        affected = cur.rowcount
        cur.close()
        return affected

def insert_db(query: str, args: Union[Tuple, List] = ()) -> int:
    """Execute an INSERT query and return lastrowid."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, args)
        conn.commit()
        last_id = cur.lastrowid
        cur.close()
        return last_id

def log_activity(category: str, action: str, actor: str = 'system', 
                 details: Optional[Dict[str, Any]] = None, ip_address: str = '', status: str = 'SUCCESS'):
    """Record an audit / activity log entry."""
    details_str = json.dumps(details or {}, default=str)
    try:
        insert_db(
            """INSERT INTO activity_logs (category, action, actor, details_json, ip_address, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (category.upper(), action, actor, details_str, ip_address, status, datetime.utcnow().isoformat())
        )
    except Exception as e:
        print(f"Error logging activity: {e}")

def init_db():
    """Initialize database tables, default roles, permissions, admin user, and seed providers."""
    # Ensure database directory exists
    Path(DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    
    with get_db_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    # 1. Seed Roles & Permissions
    _seed_roles_and_permissions()

    # 2. Seed Default Admin User (admin / admin123 with mandatory change flag)
    _seed_bootstrap_admin()

    # 3. Seed Default AI Providers
    _seed_ai_providers()

    # 4. Seed Default Email Templates
    _seed_default_templates()

    # 5. Seed Default Training Rules & Knowledge
    _seed_default_training_data()

def _seed_roles_and_permissions():
    """Create default Admin and Operator roles and permission matrix."""
    permissions = [
        ('manage_users', 'AUTH', 'Create, edit, and delete system users'),
        ('manage_roles', 'AUTH', 'Manage roles and system permissions'),
        ('view_emails', 'GMAIL', 'Read, search, and view Gmail messages and threads'),
        ('send_emails', 'GMAIL', 'Send, reply, forward, and compose emails'),
        ('manage_drafts', 'GMAIL', 'Create, update, and delete Gmail drafts'),
        ('modify_labels', 'GMAIL', 'Add or remove Gmail labels, archive, trash'),
        ('manage_automations', 'AUTOMATION', 'Create, edit, toggle, and delete automated workflows'),
        ('execute_automations', 'AUTOMATION', 'Run or trigger automation passes'),
        ('use_ai_chat', 'AI', 'Communicate with AI chatbot and use email tools'),
        ('manage_ai_training', 'AI', 'Manage behavioral rules, FAQ knowledge base, examples'),
        ('manage_ai_providers', 'SETTINGS', 'Configure AI provider keys, endpoints, and models'),
        ('manage_settings', 'SETTINGS', 'Configure Gmail OAuth, system settings, and backups'),
        ('view_logs', 'AUDIT', 'View activity, audit, and automation logs')
    ]
    
    for perm_name, cat, desc in permissions:
        existing = query_db("SELECT id FROM permissions WHERE name = ?", (perm_name,), one=True)
        if not existing:
            insert_db("INSERT INTO permissions (name, category, description) VALUES (?, ?, ?)", (perm_name, cat, desc))
    
    # Create Admin Role
    admin_role = query_db("SELECT id FROM roles WHERE name = 'Admin'", one=True)
    if not admin_role:
        admin_role_id = insert_db("INSERT INTO roles (name, description, is_system) VALUES (?, ?, ?)", 
                                  ('Admin', 'Full administrative access to all features', 1))
    else:
        admin_role_id = admin_role['id']
    
    # Grant all permissions to Admin
    all_perms = query_db("SELECT id FROM permissions")
    for perm in all_perms:
        existing = query_db("SELECT 1 FROM role_permissions WHERE role_id = ? AND permission_id = ?", 
                            (admin_role_id, perm['id']), one=True)
        if not existing:
            insert_db("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", 
                      (admin_role_id, perm['id']))

def _seed_bootstrap_admin():
    """Create initial admin user with bootstrap password 'admin123' if no users exist."""
    user_count = query_db("SELECT COUNT(*) as count FROM users", one=True)
    if user_count and user_count['count'] == 0:
        # Default bootstrap password is admin123 with is_bootstrap_password = 1
        password_hash = generate_password_hash('admin123')
        user_id = insert_db(
            """INSERT INTO users (username, password_hash, email, is_active, is_bootstrap_password, created_at)
               VALUES (?, ?, ?, 1, 1, ?)""",
            ('admin', password_hash, 'admin@example.com', datetime.utcnow().isoformat())
        )
        # Assign Admin role
        admin_role = query_db("SELECT id FROM roles WHERE name = 'Admin'", one=True)
        if admin_role:
            insert_db("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, admin_role['id']))
        
        log_activity('AUTH', 'Bootstrap Admin Account Created (Pending Password Change)', 'system', 
                     {'username': 'admin'}, status='SUCCESS')

def _seed_ai_providers():
    """Seed supported AI providers."""
    for key, p in SUPPORTED_PROVIDERS.items():
        existing = query_db("SELECT id FROM ai_providers WHERE name = ?", (key,), one=True)
        if not existing:
            is_primary = 1 if key == 'openrouter' else 0
            provider_id = insert_db(
                """INSERT INTO ai_providers 
                   (name, display_name, provider_type, base_url, default_model, fallback_model, is_active, is_primary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (key, p['display_name'], key, p['base_url'], p['default_model'], 
                 'google/gemini-2.0-flash-exp:free' if key == 'openrouter' else None, 1, is_primary)
            )
            # Insert popular models for this provider
            for m in p.get('popular_models', []):
                insert_db(
                    """INSERT INTO ai_models (provider_id, model_id, name, context_length, pricing_tier, is_active)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (provider_id, m['id'], m['name'], m.get('context', 128000), m.get('pricing', 'Standard'))
                )

def _seed_default_templates():
    """Seed initial email templates."""
    templates = [
        ('Professional Reply', 'business', 'Re: {{subject}}', 
         '<p>Hi {{recipient_name}},</p><p>Thank you for reaching out. {{ai_response}}</p><p>Best regards,<br>{{sender_name}}<br>{{company}}</p>',
         'Hi {{recipient_name}},\n\nThank you for reaching out. {{ai_response}}\n\nBest regards,\n{{sender_name}}\n{{company}}',
         'recipient_name, sender_name, company, subject, ai_response'),
        ('Customer Support Follow-up', 'support', 'Follow-up on your inquiry: {{subject}}',
         '<p>Dear {{recipient_name}},</p><p>{{ai_response}}</p><p>Please let us know if you have any further questions.</p><p>Warmly,<br>{{company}} Support Team</p>',
         'Dear {{recipient_name}},\n\n{{ai_response}}\n\nPlease let us know if you have any further questions.\n\nWarmly,\n{{company}} Support Team',
         'recipient_name, company, subject, ai_response'),
        ('Meeting Confirmation', 'scheduling', 'Meeting Confirmation: {{subject}}',
         '<p>Hello {{recipient_name}},</p><p>This is to confirm our meeting. {{ai_response}}</p><p>Looking forward to speaking with you.</p><p>Sincerely,<br>{{sender_name}}</p>',
         'Hello {{recipient_name}},\n\nThis is to confirm our meeting. {{ai_response}}\n\nLooking forward to speaking with you.\n\nSincerely,\n{{sender_name}}',
         'recipient_name, sender_name, subject, ai_response')
    ]
    for name, cat, subj, html, text, vars_list in templates:
        existing = query_db("SELECT id FROM email_templates WHERE name = ?", (name,), one=True)
        if not existing:
            insert_db(
                """INSERT INTO email_templates (name, category, subject, body_html, body_text, variables, is_system)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (name, cat, subj, html, text, vars_list)
            )

def _seed_default_training_data():
    """Seed initial behavioral instructions, FAQ knowledge, and response rules."""
    rules = [
        ('instruction', 'Professionalism & Tone', 'Always maintain a courteous, concise, and professional tone in all generated drafts and responses. Avoid overly casual slang.', 1),
        ('constraint', 'Financial & Refund Safeguard', 'Never authorize refunds or make binding financial commitments directly. If a user asks for a refund or dispute, acknowledge the message and escalate to human review.', 1),
        ('constraint', 'Conciseness Limit', 'Keep automated email replies under 150 words unless providing a structured technical explanation or requested report.', 2),
        ('safety', 'Confidentiality Shield', 'Never disclose internal API keys, passwords, database contents, or proprietary system configurations in email drafts or chat answers.', 1)
    ]
    for r_type, title, content, prio in rules:
        existing = query_db("SELECT id FROM ai_training_rules WHERE title = ?", (title,), one=True)
        if not existing:
            insert_db("INSERT INTO ai_training_rules (rule_type, title, content, priority) VALUES (?, ?, ?, ?)",
                      (r_type, title, content, prio))
    
    knowledge = [
        ('company', 'Company Overview', 'We provide enterprise AI productivity solutions and automated email workflow assistance for modern businesses.', 'about,company'),
        ('policy', 'Support Hours & Response Time', 'Standard customer support hours are Monday through Friday, 9:00 AM to 6:00 PM EST. Typical email response time is within 4 hours.', 'support,hours'),
        ('faq', 'How to request human assistance', 'Recipients can request human intervention anytime by replying with "Human" or asking to speak with an account manager.', 'human,escalation')
    ]
    for cat, title, content, tags in knowledge:
        existing = query_db("SELECT id FROM ai_knowledge WHERE title = ?", (title,), one=True)
        if not existing:
            insert_db("INSERT INTO ai_knowledge (category, title, content, tags) VALUES (?, ?, ?, ?)",
                      (cat, title, content, tags))

def backup_db() -> str:
    """Create a timestamped copy of SQLite database in storage/backups/."""
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUPS_DIR / f"backup_{timestamp}.sqlite3"
    shutil.copy2(DB_FILE, backup_file)
    log_activity('SETTINGS', 'Database Backup Created', 'system', {'backup_file': backup_file.name})
    return str(backup_file)
