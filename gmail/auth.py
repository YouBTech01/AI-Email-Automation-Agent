"""
Google OAuth 2.0 Flow, Token Exchange, and Refresh Engine.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from flask import session, url_for
from config.settings import GMAIL_SCOPES, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from database.database import query_db, execute_db, insert_db, log_activity
from database.crypto import encrypt_value, decrypt_value

def get_oauth_config() -> Dict[str, Any]:
    """Retrieve OAuth client configuration from DB or settings."""
    # Check DB system_settings first, then settings.py
    client_id_row = query_db("SELECT value_enc FROM system_settings WHERE key = 'google_client_id'", one=True)
    client_secret_row = query_db("SELECT value_enc FROM system_settings WHERE key = 'google_client_secret'", one=True)
    redirect_uri_row = query_db("SELECT value_enc FROM system_settings WHERE key = 'google_redirect_uri'", one=True)

    client_id = decrypt_value(client_id_row['value_enc']) if client_id_row else GOOGLE_CLIENT_ID
    client_secret = decrypt_value(client_secret_row['value_enc']) if client_secret_row else GOOGLE_CLIENT_SECRET
    redirect_uri = redirect_uri_row['value_enc'] if redirect_uri_row else GOOGLE_REDIRECT_URI

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": [redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }

import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def create_oauth_flow(redirect_uri: Optional[str] = None, state: Optional[str] = None) -> Flow:
    """Instantiate a Google OAuth Flow object."""
    config = get_oauth_config()
    target_redirect = redirect_uri or config['web']['redirect_uris'][0]
    
    flow = Flow.from_client_config(
        config,
        scopes=GMAIL_SCOPES,
        redirect_uri=target_redirect,
        state=state
    )
    return flow

def save_gmail_credentials(credentials: Credentials, user_info: Dict[str, Any]):
    """Persist and encrypt Gmail tokens in database."""
    email = user_info.get('email')
    display_name = user_info.get('name', email)
    
    config = get_oauth_config()
    client_id = config['web']['client_id']
    client_secret = config['web']['client_secret']

    # Update or insert gmail_accounts
    existing_acc = query_db("SELECT id FROM gmail_accounts WHERE email = ?", (email,), one=True)
    if existing_acc:
        account_id = existing_acc['id']
        execute_db(
            """UPDATE gmail_accounts 
               SET display_name = ?, is_connected = 1, scopes = ?, updated_at = ? 
               WHERE id = ?""",
            (display_name, ' '.join(credentials.scopes or GMAIL_SCOPES), datetime.utcnow().isoformat(), account_id)
        )
    else:
        # Check if this is the first account (mark primary)
        total_accounts = query_db("SELECT COUNT(*) as c FROM gmail_accounts", one=True)['c']
        is_primary = 1 if total_accounts == 0 else 0
        account_id = insert_db(
            """INSERT INTO gmail_accounts (email, display_name, is_primary, is_connected, scopes)
               VALUES (?, ?, ?, 1, ?)""",
            (email, display_name, is_primary, ' '.join(credentials.scopes or GMAIL_SCOPES))
        )

    # Save encrypted tokens
    access_enc = encrypt_value(credentials.token) if credentials.token else ''
    refresh_enc = encrypt_value(credentials.refresh_token) if credentials.refresh_token else ''
    client_id_enc = encrypt_value(client_id)
    client_secret_enc = encrypt_value(client_secret)
    expires_at = credentials.expiry.isoformat() if credentials.expiry else None

    existing_token = query_db("SELECT id, refresh_token_enc FROM gmail_tokens WHERE account_id = ?", (account_id,), one=True)
    if existing_token:
        # Preserve refresh token if Google didn't return a new one on this exchange
        if not refresh_enc and existing_token['refresh_token_enc']:
            refresh_enc = existing_token['refresh_token_enc']
        
        execute_db(
            """UPDATE gmail_tokens 
               SET access_token_enc = ?, refresh_token_enc = ?, token_uri = ?, 
                   client_id_enc = ?, client_secret_enc = ?, expires_at = ?, updated_at = ?
               WHERE account_id = ?""",
            (access_enc, refresh_enc, credentials.token_uri, client_id_enc, client_secret_enc, expires_at, datetime.utcnow().isoformat(), account_id)
        )
    else:
        insert_db(
            """INSERT INTO gmail_tokens 
               (account_id, access_token_enc, refresh_token_enc, token_uri, client_id_enc, client_secret_enc, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (account_id, access_enc, refresh_enc, credentials.token_uri, client_id_enc, client_secret_enc, expires_at)
        )

    log_activity('GMAIL', 'Gmail Account Connected', actor=session.get('username', 'admin'), details={'email': email})

def get_gmail_credentials(account_id: Optional[int] = None) -> Optional[Credentials]:
    """Retrieve and refresh Google Credentials for the primary or specified account."""
    if account_id:
        acc = query_db("SELECT id, email FROM gmail_accounts WHERE id = ? AND is_connected = 1", (account_id,), one=True)
    else:
        acc = query_db("SELECT id, email FROM gmail_accounts WHERE is_primary = 1 AND is_connected = 1", one=True)
        if not acc:
            acc = query_db("SELECT id, email FROM gmail_accounts WHERE is_connected = 1 ORDER BY id ASC", one=True)

    if not acc:
        return None

    token_row = query_db("SELECT * FROM gmail_tokens WHERE account_id = ?", (acc['id'],), one=True)
    if not token_row:
        return None

    access_token = decrypt_value(token_row['access_token_enc'])
    refresh_token = decrypt_value(token_row['refresh_token_enc'])
    client_id = decrypt_value(token_row['client_id_enc'])
    client_secret = decrypt_value(token_row['client_secret_enc'])

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=token_row['token_uri'] or "https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=GMAIL_SCOPES
    )

    # Automatically refresh if expired or about to expire
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Update DB with new encrypted access token
            new_access_enc = encrypt_value(creds.token)
            expires_at = creds.expiry.isoformat() if creds.expiry else None
            execute_db(
                "UPDATE gmail_tokens SET access_token_enc = ?, expires_at = ?, updated_at = ? WHERE account_id = ?",
                (new_access_enc, expires_at, datetime.utcnow().isoformat(), acc['id'])
            )
        except Exception as e:
            log_activity('GMAIL', 'Token Refresh Failed', actor='system', details={'error': str(e), 'email': acc['email']}, status='FAILED')
            return None

    return creds

def disconnect_gmail_account(account_id: int):
    """Disconnect Gmail account and erase stored tokens."""
    acc = query_db("SELECT email FROM gmail_accounts WHERE id = ?", (account_id,), one=True)
    email = acc['email'] if acc else f"Account #{account_id}"
    execute_db("DELETE FROM gmail_tokens WHERE account_id = ?", (account_id,))
    execute_db("UPDATE gmail_accounts SET is_connected = 0, updated_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), account_id))
    log_activity('GMAIL', 'Gmail Account Disconnected', actor=session.get('username', 'admin'), details={'email': email})
