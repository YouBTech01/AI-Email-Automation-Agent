"""
Settings Blueprint: General, Gmail OAuth, AI Providers, OpenRouter Models, Security & Backup.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for, send_file
from auth.middleware import login_required, permission_required, get_current_user
from database.database import query_db, insert_db, execute_db, log_activity, backup_db
from database.crypto import encrypt_value, decrypt_value
from config.settings import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from ai.openrouter import fetch_openrouter_models
from ai.providers import test_provider_connection

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/')
@login_required
@permission_required('manage_settings')
def index():
    """Settings Hub."""
    user = get_current_user()
    
    # 1. Gmail Accounts & OAuth Config
    gmail_accounts = query_db("SELECT * FROM gmail_accounts ORDER BY is_primary DESC, id ASC")
    client_id_row = query_db("SELECT value_enc FROM system_settings WHERE key = 'google_client_id'", one=True)
    client_secret_row = query_db("SELECT value_enc FROM system_settings WHERE key = 'google_client_secret'", one=True)
    redirect_uri_row = query_db("SELECT value_enc FROM system_settings WHERE key = 'google_redirect_uri'", one=True)

    oauth_client_id = decrypt_value(client_id_row['value_enc']) if client_id_row else GOOGLE_CLIENT_ID
    oauth_client_secret = decrypt_value(client_secret_row['value_enc']) if client_secret_row else GOOGLE_CLIENT_SECRET
    oauth_redirect_uri = redirect_uri_row['value_enc'] if redirect_uri_row else GOOGLE_REDIRECT_URI

    # 2. AI Providers
    ai_providers = query_db("SELECT * FROM ai_providers ORDER BY is_primary DESC, id ASC")
    for p in ai_providers:
        p['has_key'] = bool(p['api_key_enc'])
        p['api_key_masked'] = '••••••••••••••••' if p['has_key'] else ''

    # 3. System Users
    users = query_db("""
        SELECT u.*, r.name as role_name 
        FROM users u 
        LEFT JOIN user_roles ur ON u.id = ur.user_id 
        LEFT JOIN roles r ON ur.role_id = r.id
        ORDER BY u.id ASC
    """)
    roles = query_db("SELECT * FROM roles")

    # 4. Storage backups
    from config.settings import BACKUPS_DIR
    backups = []
    if BACKUPS_DIR.exists():
        for f in BACKUPS_DIR.glob('*.sqlite3'):
            backups.append({
                'name': f.name,
                'size_kb': round(f.stat().st_size / 1024, 1),
                'modified': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
        backups.sort(key=lambda x: x['modified'], reverse=True)

    return render_template(
        'settings/index.html',
        user=user,
        gmail_accounts=gmail_accounts,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
        oauth_redirect_uri=oauth_redirect_uri,
        ai_providers=ai_providers,
        users=users,
        roles=roles,
        backups=backups
    )

# ==================== Gmail OAuth Credentials API ====================
@settings_bp.route('/api/oauth-credentials', methods=['POST'])
@login_required
@permission_required('manage_settings')
def api_save_oauth_credentials():
    """Save Google OAuth Client ID & Secret with encryption."""
    data = request.get_json() or {}
    client_id = data.get('client_id', '').strip()
    client_secret = data.get('client_secret', '').strip()
    redirect_uri = data.get('redirect_uri', '').strip()

    # Save to system_settings
    _save_setting('google_client_id', client_id, encrypt=True)
    _save_setting('google_client_secret', client_secret, encrypt=True)
    _save_setting('google_redirect_uri', redirect_uri, encrypt=False)

    log_activity('SETTINGS', 'Updated Google OAuth Client Settings', actor=session.get('username', 'admin'))
    return jsonify({'success': True, 'message': 'OAuth credentials saved.'})

def _save_setting(key: str, val: str, encrypt: bool = False):
    enc_val = encrypt_value(val) if encrypt else val
    existing = query_db("SELECT key FROM system_settings WHERE key = ?", (key,), one=True)
    if existing:
        execute_db("UPDATE system_settings SET value_enc = ?, is_encrypted = ?, updated_at = ? WHERE key = ?",
                   (enc_val, 1 if encrypt else 0, datetime.utcnow().isoformat(), key))
    else:
        insert_db("INSERT INTO system_settings (key, value_enc, is_encrypted) VALUES (?, ?, ?)",
                  (key, enc_val, 1 if encrypt else 0))

# ==================== AI Providers & OpenRouter API ====================
@settings_bp.route('/api/providers/save', methods=['POST'])
@login_required
@permission_required('manage_ai_providers')
def api_save_provider():
    """Save or update AI provider configuration."""
    data = request.get_json() or {}
    p_id = data.get('id')
    name = data.get('name', '').strip()
    display_name = data.get('display_name', name).strip()
    provider_type = data.get('provider_type', 'openrouter')
    base_url = data.get('base_url', '').strip()
    api_key = data.get('api_key', '').strip()
    default_model = data.get('default_model', '').strip()
    fallback_model = data.get('fallback_model', '').strip()
    is_primary = 1 if data.get('is_primary') else 0
    is_active = 1 if data.get('is_active', True) else 0

    if is_primary:
        execute_db("UPDATE ai_providers SET is_primary = 0")

    if p_id:
        existing = query_db("SELECT api_key_enc FROM ai_providers WHERE id = ?", (p_id,), one=True)
        api_key_enc = encrypt_value(api_key) if api_key else (existing['api_key_enc'] if existing else '')
        
        execute_db(
            """UPDATE ai_providers 
               SET display_name = ?, base_url = ?, api_key_enc = ?, default_model = ?, 
                   fallback_model = ?, is_active = ?, is_primary = ?, updated_at = ?
               WHERE id = ?""",
            (display_name, base_url, api_key_enc, default_model, fallback_model, is_active, is_primary, datetime.utcnow().isoformat(), p_id)
        )
    else:
        api_key_enc = encrypt_value(api_key)
        p_id = insert_db(
            """INSERT INTO ai_providers 
               (name, display_name, provider_type, base_url, api_key_enc, default_model, fallback_model, is_active, is_primary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, display_name, provider_type, base_url, api_key_enc, default_model, fallback_model, is_active, is_primary)
        )

    log_activity('SETTINGS', f"Saved AI Provider: {display_name}", actor=session.get('username', 'admin'))
    return jsonify({'success': True, 'id': p_id})

@settings_bp.route('/api/providers/test', methods=['POST'])
@login_required
@permission_required('manage_ai_providers')
def api_test_provider():
    """Test connection with an AI provider."""
    data = request.get_json() or {}
    p_id = data.get('id')
    
    if p_id:
        p = query_db("SELECT * FROM ai_providers WHERE id = ?", (p_id,), one=True)
        if not p:
            return jsonify({'success': False, 'error': 'Provider not found'}), 404
        api_key = decrypt_value(p['api_key_enc'])
        base_url = p['base_url']
        model = p['default_model']
        p_type = p['provider_type']
    else:
        api_key = data.get('api_key', '')
        base_url = data.get('base_url', '')
        model = data.get('model', '')
        p_type = data.get('provider_type', 'openrouter')

    res = test_provider_connection(base_url=base_url, api_key=api_key, model=model, provider_type=p_type)
    return jsonify(res)

@settings_bp.route('/api/openrouter/models', methods=['GET'])
@login_required
def api_openrouter_models():
    """Fetch live OpenRouter model catalog with search and pricing."""
    p = query_db("SELECT api_key_enc FROM ai_providers WHERE name = 'openrouter'", one=True)
    api_key = decrypt_value(p['api_key_enc']) if p and p['api_key_enc'] else None
    models = fetch_openrouter_models(api_key)
    return jsonify({'models': models})

# ==================== Backup Management ====================
@settings_bp.route('/api/backup/create', methods=['POST'])
@login_required
@permission_required('manage_settings')
def api_create_backup():
    """Create instant SQLite database backup."""
    backup_path = backup_db()
    return jsonify({'success': True, 'file': backup_path})

@settings_bp.route('/backup/download/<filename>')
@login_required
@permission_required('manage_settings')
def download_backup(filename: str):
    """Download database backup file."""
    from config.settings import BACKUPS_DIR
    target = BACKUPS_DIR / filename
    if not target.exists():
        return "Backup not found", 404
    return send_file(target, as_attachment=True)
