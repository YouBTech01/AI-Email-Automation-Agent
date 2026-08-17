"""
Contacts Blueprint: Address Book, Contact Tagging, and Interaction Logs.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from auth.middleware import login_required, get_current_user
from database.database import query_db, insert_db, execute_db, log_activity

contacts_bp = Blueprint('contacts', __name__, url_prefix='/contacts')

@contacts_bp.route('/')
@login_required
def index():
    """Contacts Directory."""
    user = get_current_user()
    contacts = query_db("SELECT * FROM contacts ORDER BY is_vip DESC, name ASC")
    return render_template('contacts/index.html', user=user, contacts=contacts)

@contacts_bp.route('/api/save', methods=['POST'])
@login_required
def api_save():
    """Create or update contact."""
    data = request.get_json() or {}
    c_id = data.get('id')
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    company = data.get('company', '').strip()
    notes = data.get('notes', '').strip()
    tags = data.get('tags', '').strip()
    is_vip = 1 if data.get('is_vip') else 0

    if not name or not email:
        return jsonify({'error': 'Name and Email are required'}), 400

    if c_id:
        execute_db(
            """UPDATE contacts 
               SET name = ?, email = ?, phone = ?, company = ?, notes = ?, tags = ?, is_vip = ?, updated_at = ?
               WHERE id = ?""",
            (name, email, phone, company, notes, tags, is_vip, datetime.utcnow().isoformat(), c_id)
        )
    else:
        existing = query_db("SELECT id FROM contacts WHERE email = ?", (email,), one=True)
        if existing:
            return jsonify({'error': 'A contact with this email already exists'}), 400
        c_id = insert_db(
            """INSERT INTO contacts (name, email, phone, company, notes, tags, is_vip)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, email, phone, company, notes, tags, is_vip)
        )
    log_activity('GMAIL', f"Saved Contact: {name} ({email})", actor=session.get('username', 'admin'))
    return jsonify({'success': True, 'id': c_id})

@contacts_bp.route('/api/<int:c_id>', methods=['DELETE'])
@login_required
def api_delete(c_id: int):
    execute_db("DELETE FROM contacts WHERE id = ?", (c_id,))
    return jsonify({'success': True})
