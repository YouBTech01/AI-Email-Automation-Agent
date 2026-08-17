"""
cPanel Cron Email Synchronizer.
Fetches latest message headers from Gmail and maintains sync checkpoint.
"""
import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from database.database import init_db, query_db, execute_db
from gmail import messages as gmail_msg

def sync():
    init_db()
    acc = query_db("SELECT id, email FROM gmail_accounts WHERE is_connected = 1 AND is_primary = 1", one=True)
    if not acc:
        print("No connected primary Gmail account.")
        return

    print(f"Syncing Gmail for {acc['email']}...")
    res = gmail_msg.search_messages(query="label:INBOX", max_results=25, account_id=acc['id'])
    if res.get('success'):
        count = len(res.get('messages', []))
        execute_db("UPDATE gmail_accounts SET last_sync_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), acc['id']))
        print(f"Sync complete. Retrieved {count} recent message headers.")
    else:
        print(f"Sync failed: {res.get('error')}")

if __name__ == '__main__':
    sync()
