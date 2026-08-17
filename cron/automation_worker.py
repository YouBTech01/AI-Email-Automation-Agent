"""
cPanel Cron Automation Worker.
Execute via cPanel Cron:
/home/USERNAME/virtualenv/ai-email-agent/3.10/bin/python /home/USERNAME/ai-email-agent/cron/automation_worker.py
"""
import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from database.database import init_db
from automation.worker import run_automation_worker_cycle

def main():
    parser = argparse.ArgumentParser(description="AI Email Automation Agent Cron Worker")
    parser.add_argument('--limit', type=int, default=20, help="Maximum emails to inspect per cycle")
    parser.add_argument('--test', action='store_true', help="Run single test cycle with verbose output")
    args = parser.parse_args()

    # Ensure database is initialized
    init_db()

    print(f"[{Path(__file__).name}] Starting automation cycle (limit={args.limit})...")
    res = run_automation_worker_cycle(max_emails=args.limit)

    if res.get('success'):
        print(f"[{Path(__file__).name}] Success: Checked {res.get('emails_checked', 0)} emails, triggered {res.get('automations_triggered', 0)} automation runs.")
        if args.test and res.get('runs'):
            print(f"Details: {res['runs']}")
    else:
        print(f"[{Path(__file__).name}] Notice/Error: {res.get('error') or res.get('message')}")

if __name__ == '__main__':
    main()
