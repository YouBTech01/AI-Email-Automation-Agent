"""
Admin Password Reset CLI Utility.
Usage:
    python set_password.py <username> <new_password>
Example:
    python set_password.py admin AdminSecure2026!
"""
import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from database.database import init_db, query_db, execute_db, log_activity
from auth.security import hash_password, validate_password_strength

def set_user_password(username: str, new_pass: str):
    init_db()
    user = query_db("SELECT id, username FROM users WHERE username = ?", (username,), one=True)
    if not user:
        print(f"Error: User '{username}' does not exist.")
        return False

    is_valid, msg = validate_password_strength(new_pass)
    if not is_valid:
        print(f"Validation Error: {msg}")
        return False

    p_hash = hash_password(new_pass)
    execute_db(
        "UPDATE users SET password_hash = ?, is_bootstrap_password = 0, updated_at = ? WHERE id = ?",
        (p_hash, datetime.now().isoformat(), user['id'])
    )
    log_activity('AUTH', f"Password Reset via CLI for {username}", actor='cli', status='SUCCESS')
    print(f"Success: Password for '{username}' has been updated to '{new_pass}' and bootstrap lock disabled.")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python set_password.py <username> <new_password>")
        print("Example: python set_password.py admin AdminSecure2026!")
        sys.exit(1)

    username_arg = sys.argv[1].strip()
    new_pass_arg = sys.argv[2]
    success = set_user_password(username_arg, new_pass_arg)
    sys.exit(0 if success else 1)
