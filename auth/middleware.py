"""
Authentication and Authorization Middleware, session management, and CSRF protection.
"""
import secrets
from functools import wraps
from flask import session, redirect, url_for, request, jsonify, abort, g
from database.database import query_db

def generate_csrf_token() -> str:
    """Generate or retrieve the session CSRF token."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def validate_csrf():
    """Validate CSRF token on state-changing requests."""
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        # Check header or form data
        token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        expected = session.get('_csrf_token')
        if not token or not expected or not secrets.compare_digest(token, expected):
            if request.is_json or request.path.startswith('/api/'):
                abort(403, description="CSRF token validation failed.")
            abort(403)

def get_current_user():
    """Retrieve currently authenticated user dict from session."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    if hasattr(g, 'current_user') and g.current_user and g.current_user['id'] == user_id:
        return g.current_user
    
    user = query_db("SELECT id, username, email, is_active, is_bootstrap_password, two_factor_enabled, created_at FROM users WHERE id = ?", (user_id,), one=True)
    g.current_user = user
    return user

def user_has_permission(user_id: int, permission_name: str) -> bool:
    """Check if the user has a specific permission via assigned roles."""
    query = """
        SELECT 1 FROM user_roles ur
        JOIN role_permissions rp ON ur.role_id = rp.role_id
        JOIN permissions p ON rp.permission_id = p.id
        WHERE ur.user_id = ? AND p.name = ?
    """
    match = query_db(query, (user_id, permission_name), one=True)
    return bool(match)

def login_required(f):
    """Decorator ensuring the user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or not user['is_active']:
            session.clear()
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
            return redirect(url_for('auth.login', next=request.path))
        
        # Enforce forced password change on bootstrap password
        if user['is_bootstrap_password'] and request.endpoint not in ('auth.force_password_change', 'auth.logout', 'static'):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Password change required before proceeding', 'code': 'PASSWORD_CHANGE_REQUIRED'}), 403
            return redirect(url_for('auth.force_password_change'))
            
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_name: str):
    """Decorator ensuring the current user possesses a specific permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
                return redirect(url_for('auth.login'))
            
            if not user_has_permission(user['id'], permission_name):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': f"Permission '{permission_name}' denied", 'code': 'PERMISSION_DENIED'}), 403
                abort(403, description=f"You lack the required permission: {permission_name}")
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
