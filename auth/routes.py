"""
Authentication Blueprint: Login, Logout, Mandatory Password Change, and User Management.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, g
from database.database import query_db, execute_db, insert_db, log_activity
from auth.security import verify_password, hash_password, validate_password_strength, is_rate_limited, record_failed_login, clear_failed_logins
from auth.middleware import login_required, permission_required, get_current_user

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin Login with Rate Limiting & First-Login Detection."""
    if session.get('user_id'):
        user = get_current_user()
        if user and user['is_bootstrap_password']:
            return redirect(url_for('auth.force_password_change'))
        return redirect(url_for('dashboard.index'))
    
    ip = request.remote_addr or '127.0.0.1'
    limited, retry_after = is_rate_limited(ip)
    if limited:
        flash(f"Too many failed login attempts. Please wait {retry_after} seconds.", "danger")
        return render_template('auth/login.html', rate_limited=True, retry_after=retry_after)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Please enter both username and password.", "warning")
            return render_template('auth/login.html')

        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)

        if not user or not verify_password(password, user['password_hash']):
            record_failed_login(ip)
            log_activity('AUTH', 'Failed Login Attempt', actor=username or 'unknown', ip_address=ip, status='FAILED')
            flash("Invalid username or password.", "danger")
            return render_template('auth/login.html')

        if not user['is_active']:
            log_activity('AUTH', 'Deactivated Account Login Blocked', actor=username, ip_address=ip, status='BLOCKED')
            flash("This account has been deactivated. Please contact the administrator.", "danger")
            return render_template('auth/login.html')

        # Authentication Successful
        clear_failed_logins(ip)
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']

        execute_db("UPDATE users SET last_login_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), user['id']))
        log_activity('AUTH', 'User Login Successful', actor=user['username'], ip_address=ip, status='SUCCESS')

        # Check if bootstrap password change is required
        if user['is_bootstrap_password']:
            flash("Welcome! As this is your first login with the default bootstrap credentials, you must set a new secure password.", "info")
            return redirect(url_for('auth.force_password_change'))

        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')

@auth_bp.route('/force-password-change', methods=['GET', 'POST'])
def force_password_change():
    """Mandatory Password Change Screen for Bootstrap Credentials."""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))

    if not user['is_bootstrap_password']:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if new_password != confirm_password:
            flash("New passwords do not match. Please retype carefully.", "danger")
            return render_template('auth/change_password.html', forced=True)

        if new_password == 'admin123':
            flash("You cannot reuse the default bootstrap password. Please choose a strong unique password.", "danger")
            return render_template('auth/change_password.html', forced=True)

        is_valid, msg = validate_password_strength(new_password)
        if not is_valid:
            flash(msg, "warning")
            return render_template('auth/change_password.html', forced=True)

        # Hash new password and disable bootstrap flag
        new_hash = hash_password(new_password)
        execute_db(
            "UPDATE users SET password_hash = ?, is_bootstrap_password = 0, updated_at = ? WHERE id = ?",
            (new_hash, datetime.utcnow().isoformat(), user['id'])
        )

        log_activity('AUTH', 'Bootstrap Password Changed Successfully', actor=user['username'], 
                     ip_address=request.remote_addr or '', status='SUCCESS')
        
        flash("Password updated successfully! Welcome to your AI Email Automation Agent.", "success")
        return redirect(url_for('dashboard.index'))

    return render_template('auth/change_password.html', forced=True)

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Terminate user session."""
    username = session.get('username', 'user')
    ip = request.remote_addr or ''
    session.clear()
    log_activity('AUTH', 'User Logged Out', actor=username, ip_address=ip, status='SUCCESS')
    flash("You have been securely logged out.", "info")
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User Profile and Password Management."""
    user = get_current_user()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_info':
            email = request.form.get('email', '').strip()
            execute_db("UPDATE users SET email = ?, updated_at = ? WHERE id = ?", 
                       (email, datetime.utcnow().isoformat(), user['id']))
            flash("Profile information updated successfully.", "success")
            log_activity('AUTH', 'Profile Updated', actor=user['username'])
            return redirect(url_for('auth.profile'))
        
        elif action == 'change_password':
            current_pass = request.form.get('current_password', '')
            new_pass = request.form.get('new_password', '')
            confirm_pass = request.form.get('confirm_password', '')

            db_user = query_db("SELECT password_hash FROM users WHERE id = ?", (user['id'],), one=True)
            if not verify_password(current_pass, db_user['password_hash']):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for('auth.profile'))

            if new_pass != confirm_pass:
                flash("New passwords do not match.", "danger")
                return redirect(url_for('auth.profile'))

            is_valid, msg = validate_password_strength(new_pass)
            if not is_valid:
                flash(msg, "warning")
                return redirect(url_for('auth.profile'))

            new_hash = hash_password(new_pass)
            execute_db("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", 
                       (new_hash, datetime.utcnow().isoformat(), user['id']))
            flash("Password updated successfully.", "success")
            log_activity('AUTH', 'User Password Changed', actor=user['username'])
            return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', user=user)

# REST User Management Endpoints (CRUD)
@auth_bp.route('/api/users', methods=['GET', 'POST'])
@login_required
@permission_required('manage_users')
def api_users():
    """Manage System Users."""
    if request.method == 'GET':
        users = query_db("""
            SELECT u.id, u.username, u.email, u.is_active, u.is_bootstrap_password, 
                   u.created_at, u.last_login_at, r.name as role_name
            FROM users u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN roles r ON ur.role_id = r.id
            ORDER BY u.id ASC
        """)
        return jsonify({'users': users})
    
    elif request.method == 'POST':
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        email = data.get('email', '').strip()
        role_id = data.get('role_id', 1)

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        existing = query_db("SELECT id FROM users WHERE username = ?", (username,), one=True)
        if existing:
            return jsonify({'error': 'Username already exists'}), 400

        p_hash = hash_password(password)
        new_id = insert_db(
            "INSERT INTO users (username, password_hash, email, is_bootstrap_password) VALUES (?, ?, ?, 0)",
            (username, p_hash, email)
        )
        insert_db("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (new_id, role_id))
        log_activity('AUTH', 'Created User', actor=session.get('username', 'admin'), details={'new_user': username})
        return jsonify({'success': True, 'user_id': new_id}), 201
