"""
Application settings and environment configuration.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if available
load_dotenv(BASE_DIR / '.env')

# Storage Directory for SQLite, uploads, backups, and encryption keys
STORAGE_DIR = BASE_DIR / 'storage'
STORAGE_DIR.mkdir(exist_ok=True, parents=True)

UPLOADS_DIR = STORAGE_DIR / 'uploads'
UPLOADS_DIR.mkdir(exist_ok=True, parents=True)

BACKUPS_DIR = STORAGE_DIR / 'backups'
BACKUPS_DIR.mkdir(exist_ok=True, parents=True)

# Database file path
DB_FILE = os.getenv('DATABASE_PATH', str(STORAGE_DIR / 'database.sqlite3'))

# Flask & Session Security
SECRET_KEY = os.getenv('SECRET_KEY', 'ai-email-agent-default-insecure-secret-change-me')
SESSION_COOKIE_NAME = 'ai_email_agent_session'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')
PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7 days

# Encryption Key for sensitive fields at rest (Tokens, API Keys)
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '')

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/gmail/oauth2callback')

# Gmail Scopes required by the agent
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

# AI Configuration
DEFAULT_AI_PROVIDER = os.getenv('DEFAULT_AI_PROVIDER', 'openrouter')
DEFAULT_AI_MODEL = os.getenv('DEFAULT_AI_MODEL', 'openai/gpt-4o-mini')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

# Application Defaults
DEFAULT_CONFIDENCE_THRESHOLD = 85  # Confidence score % for trusted actions
MAX_ACTIONS_PER_RUN = 20
RATE_LIMIT_LOGIN_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 300
ENABLE_BACKGROUND_SCHEDULER = os.getenv('ENABLE_BACKGROUND_SCHEDULER', 'True').lower() in ('true', '1', 't')
