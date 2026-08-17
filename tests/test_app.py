"""
Comprehensive Automated Test Suite for AI Email Automation Agent.
Tests database bootstrap, auth, encryption, safety gates, duplicate guard, and automation engine.
"""
import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Set test environment
os.environ['DATABASE_PATH'] = 'storage/test_database.sqlite3'
os.environ['ENABLE_BACKGROUND_SCHEDULER'] = 'False'

from database.database import init_db, query_db, execute_db, insert_db
from database.crypto import encrypt_value, decrypt_value
from auth.security import verify_password, hash_password, validate_password_strength
from ai.tools import TOOL_DEFINITIONS, execute_tool
from ai.safety import classify_tool_risk, validate_tool_execution
from automation.triggers import evaluate_trigger
from automation.conditions import evaluate_conditions
from automation.engine import is_message_already_processed, record_processed_message, run_automations_on_email
from app import create_app

class TestAIEmailAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize test database."""
        init_db()
        cls.app = create_app()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        """Clean up test database."""
        test_db = Path('storage/test_database.sqlite3')
        if test_db.exists():
            try:
                test_db.unlink()
            except Exception:
                pass

    def test_01_database_bootstrap_and_admin(self):
        """Verify default admin bootstrap user and permissions exist."""
        admin = query_db("SELECT * FROM users WHERE username = 'admin'", one=True)
        self.assertIsNotNone(admin)
        self.assertEqual(admin['is_bootstrap_password'], 1)
        self.assertTrue(verify_password('admin123', admin['password_hash']))

        # Verify roles and permissions
        admin_role = query_db("SELECT * FROM roles WHERE name = 'Admin'", one=True)
        self.assertIsNotNone(admin_role)
        perms = query_db("SELECT COUNT(*) as c FROM permissions", one=True)
        self.assertGreater(perms['c'], 5)

    def test_02_encryption_at_rest(self):
        """Verify AES/Fernet encryption and decryption of secrets."""
        secret_token = "ya29.a0AfH6SMD_SampleGmailRefreshToken12345"
        encrypted = encrypt_value(secret_token)
        self.assertNotEqual(secret_token, encrypted)
        decrypted = decrypt_value(encrypted)
        self.assertEqual(secret_token, decrypted)

    def test_03_password_strength_validation(self):
        """Test password validation rules."""
        valid, _ = validate_password_strength("Weak")
        self.assertFalse(valid)
        valid, _ = validate_password_strength("alllowercase123")
        self.assertFalse(valid)
        valid, _ = validate_password_strength("ALLUPPERCASE123")
        self.assertFalse(valid)
        valid, _ = validate_password_strength("ValidStrongPass123!")
        self.assertTrue(valid)

    def test_04_ai_tool_registry_and_safety_risk(self):
        """Verify JSON Schema AI tools and risk tier classification."""
        self.assertGreater(len(TOOL_DEFINITIONS), 8)
        
        # Verify risk classification
        self.assertEqual(classify_tool_risk('gmail_search'), 'LOW')
        self.assertEqual(classify_tool_risk('gmail_get_message'), 'LOW')
        self.assertEqual(classify_tool_risk('gmail_create_draft'), 'MEDIUM')
        self.assertEqual(classify_tool_risk('gmail_send'), 'HIGH')
        self.assertEqual(classify_tool_risk('gmail_trash'), 'HIGH')

        # Safety gate checks
        allowed, risk, _ = validate_tool_execution(user_id=1, tool_name='gmail_search', tool_args={})
        self.assertTrue(allowed)
        self.assertEqual(risk, 'LOW')

        allowed, risk, reason = validate_tool_execution(user_id=1, tool_name='gmail_send', tool_args={}, is_automation=False)
        self.assertFalse(allowed)  # Gated by confirmation in chat
        self.assertEqual(risk, 'HIGH')

    def test_05_automation_trigger_and_conditions(self):
        """Test trigger and multi-condition evaluation."""
        sample_email = {
            'id': 'msg_test_101',
            'from': 'billing@clientcorp.com',
            'subject': 'Invoice #9021 Inquiry',
            'body_text': 'Please find attached invoice for review.',
            'is_unread': True,
            'attachments': [{'filename': 'invoice.pdf'}]
        }

        # Trigger check
        trig_match = evaluate_trigger('sender_match', {'sender': 'clientcorp.com'}, sample_email)
        self.assertTrue(trig_match)

        trig_no_match = evaluate_trigger('sender_match', {'sender': 'unknown.org'}, sample_email)
        self.assertFalse(trig_no_match)

        # Condition check
        conditions = [
            {'field': 'sender', 'operator': 'contains', 'value': 'clientcorp.com'},
            {'field': 'subject', 'operator': 'contains', 'value': 'Invoice'}
        ]
        cond_match = evaluate_conditions(conditions, sample_email)
        self.assertTrue(cond_match)

    def test_06_duplicate_protection_guard(self):
        """Test that duplicate guard strictly prevents double-processing."""
        msg_id = "gmail_msg_unique_9988"
        auto_id = insert_db("INSERT INTO automations (name, trigger_type) VALUES ('Test Guard Auto', 'new_email')")

        # Initially not processed
        self.assertFalse(is_message_already_processed(msg_id, auto_id))

        # Record processing
        record_processed_message(msg_id, "thread_123", auto_id)

        # Now must return True
        self.assertTrue(is_message_already_processed(msg_id, auto_id))

    def test_07_auth_routes_flow(self):
        """Test login and mandatory password change redirect."""
        # 1. Login with bootstrap credentials
        res = self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/force-password-change', res.headers['Location'])

    def test_08_ai_natural_language_automation_create(self):
        """Test AI natural language automation creation tool."""
        tool_args = {
            "name": "Refund Inquiries Handler",
            "description": "When customer asks about refunds, draft a polite explanation and escalate",
            "trigger_type": "keyword_match",
            "trigger_config": {"keywords": "refund, money back, dispute"},
            "conditions": [
                {"field": "body", "operator": "contains", "value": "refund"}
            ],
            "actions": [
                {"action_type": "generate_draft", "config": {"instruction": "Acknowledge receipt and explain review procedure"}}
            ],
            "approval_mode": "draft_only",
            "confidence_threshold": 90
        }

        res = execute_tool("automation_create", tool_args)
        self.assertTrue(res['success'])
        self.assertIn('automation_id', res)
        self.assertIn('/automations/builder/', res['view_url'])

        # Verify in database
        auto = query_db("SELECT * FROM automations WHERE id = ?", (res['automation_id'],), one=True)
        self.assertIsNotNone(auto)
        self.assertEqual(auto['name'], "Refund Inquiries Handler")
        self.assertEqual(auto['approval_mode'], "draft_only")
        self.assertEqual(auto['confidence_threshold'], 90)

if __name__ == '__main__':
    unittest.main(verbosity=2)
