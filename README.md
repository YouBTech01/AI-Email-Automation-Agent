# AI Email Automation Agent

An enterprise-grade, controlled, AI-powered Gmail automation and management platform built with Python (Flask), SQLite, Google Gmail API, Google OAuth 2.0, OpenRouter AI, and a responsive Material Design 3 user interface.

Designed specifically for production deployment on **cPanel Python / Phusion Passenger** shared hosting or standalone VPS environments.

---

## 🌟 Key Features

1. **Controlled AI Assistant Chat**:
   - Natural language commands to search, analyze, draft, reply, and organize Gmail messages.
   - Multi-turn conversation history and context awareness.
   - **Safe Risk Gate**: Low-risk operations (search, read, report) run automatically; high-risk actions (sending, deleting, modifying workflows) require explicit user confirmation via visual preview cards.

2. **Official Google Gmail API Integration**:
   - Google OAuth 2.0 with minimum required scopes.
   - Token refresh handling with encrypted credential storage at rest.
   - Search, read multipart/HTML emails, draft creation, sending, replies with proper `In-Reply-To` and `References` headers, archiving, labeling, and trash management.

3. **Multi-Provider AI Router with Fallback Chain**:
   - **OpenRouter** integration with live dynamic model catalog search and pricing browser.
   - Support for OpenAI, Google Gemini, Groq, DeepSeek, and Custom OpenAI-compatible endpoints.
   - Automatic multi-level fallback: Primary Model $\rightarrow$ Fallback Model $\rightarrow$ Secondary Provider $\rightarrow$ Safe pause & alert.

4. **Behavioral Training & Knowledge Base**:
   - Custom tone rules, financial/refund constraints, and conciseness limits.
   - Few-shot response examples.
   - FAQ and company knowledge base articles automatically injected into AI prompts.

5. **Visual Automation Builder & Workflow Engine**:
   - Multi-condition evaluator (sender, domain, subject keywords, AI intent classification, attachment).
   - 3-Tier Safety Levels:
     - **Level 1 (Draft Only)**: AI crafts reply and saves as a Gmail draft for review.
     - **Level 2 (Approval Required)**: Prepares response and creates a one-click dashboard approval card.
     - **Level 3 (Trusted Automation)**: Auto-sends if AI confidence exceeds the configured threshold.
   - **Mandatory Duplicate Guard**: `(message_id, automation_id)` tracking table prevents duplicate runs or replies.

6. **Enterprise Security & cPanel Ready**:
   - Bootstrap credentials (`admin` / `admin123`) with **forced password change on first login**.
   - Cryptographically hashed passwords (`scrypt` / `pbkdf2`).
   - Sensitive tokens encrypted at rest via AES/Fernet.
   - cPanel `passenger_wsgi.py` integration and standalone `cron/automation_worker.py` for cPanel Cron.
   - Instant SQLite database snapshot backup and download.

---

## 🚀 Quick Start & Local Development

### 1. Prerequisites
- Python 3.10 or higher
- pip and virtualenv

### 2. Installation
```bash
# 1. Clone or navigate to the directory
cd "AI Email Automation Agent"

# 2. Create and activate a Python virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install required dependencies
pip install -r requirements.txt

# 4. Create environment file
copy .env.example .env
```

### 3. Run Development Server
```bash
python app.py
```
Open your browser at `http://127.0.0.1:5000`.

### 4. Initial Bootstrap Login
- **Username**: `admin`
- **Password**: `admin123`
- *On first login, the system will prompt you to set a new strong password.*

---

## ☁️ cPanel Shared Hosting Deployment Guide

cPanel supports Python applications via **Application Manager / Phusion Passenger**.

### Step 1: Create Python App in cPanel
1. Log in to your cPanel dashboard.
2. Navigate to **Setup Python App** (under Software section).
3. Click **Create Application**.
4. Select:
   - **Python Version**: `3.10` or higher
   - **Application Root**: `ai-email-agent` (or your chosen directory)
   - **Application URL**: `yourdomain.com` (or `agent.yourdomain.com`)
   - **Application Startup File**: `passenger_wsgi.py`
   - **Application Entry Point**: `application`
5. Click **Create**.

### Step 2: Upload Files & Install Dependencies
1. Upload the project files to `/home/USERNAME/ai-email-agent/`.
2. In cPanel Python App Manager, enter the virtual environment command displayed in the top banner:
   ```bash
   source /home/USERNAME/virtualenv/ai-email-agent/3.10/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` in the application root and set your `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `OPENROUTER_API_KEY`.

### Step 4: Configure cPanel Cron for Automations
On shared cPanel hosting, background threads may sleep. Use cPanel Cron to execute the automation worker regularly:
1. Go to **Cron Jobs** in cPanel.
2. Add a new cron job running every 5 or 15 minutes (`*/5 * * * *`):
   ```bash
   /home/USERNAME/virtualenv/ai-email-agent/3.10/bin/python /home/USERNAME/ai-email-agent/cron/automation_worker.py --limit 20
   ```

---

## ⚙️ Google Cloud OAuth Configuration

To connect Gmail to the platform:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `AI Email Agent`).
3. Enable the **Gmail API** under **APIs & Services > Library**.
4. Configure the **OAuth Consent Screen**:
   - User Type: External (or Internal for Google Workspace).
   - Scopes: `https://www.googleapis.com/auth/gmail.modify`, `https://www.googleapis.com/auth/gmail.compose`, `openid`, `email`, `profile`.
5. Create Credentials:
   - Type: **OAuth 2.0 Client ID**
   - Application Type: **Web application**
   - Authorized redirect URIs: `http://127.0.0.1:5000/gmail/oauth2callback` (or `https://yourdomain.com/gmail/oauth2callback`)
6. Copy the **Client ID** and **Client Secret** into **Settings > Gmail & OAuth** in the web interface.
7. Click **Connect Gmail Account**!

---

## 🔒 Security Architecture

| Security Domain | Safeguard Implementation |
| :--- | :--- |
| **Passwords** | Hashed using `scrypt` / PBKDF2 with salt. Plaintext passwords never stored. |
| **Bootstrap Lock** | Mandatory password reset required before dashboard access is permitted. |
| **OAuth Tokens** | Encrypted at rest via Fernet AES-128/256 authenticated cipher. |
| **AI Safety Gate** | High-impact actions (`send`, `trash`, `delete`) gated by visual confirmation. |
| **AI Boundaries** | Operates strictly via whitelisted JSON Schema tool functions. No shell/code execution. |
| **Duplicate Guard** | `(message_id, automation_id)` tracking table prevents duplicate emails/replies. |
| **Web Security** | CSRF tokens on all state-changing endpoints, rate limiting, and RBAC middleware. |

---

## 📄 License
Enterprise MIT License - Built for high-security autonomous email workflows.
