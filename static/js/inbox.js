/**
 * Gmail Inbox & Thread Viewer Controller with One-Click Instant AI Actions.
 */

let selectedMessageId = null;

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('inbox-messages-list')) {
    loadInboxMessages('label:INBOX');
  }

  const searchInput = document.getElementById('inbox-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        loadInboxMessages(searchInput.value.trim() || 'label:INBOX');
      }
    });
  }
});

async function loadInboxMessages(query = 'label:INBOX') {
  const listEl = document.getElementById('inbox-messages-list');
  if (!listEl) return;

  listEl.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-muted);"><div style="margin-bottom:8px; font-size:24px;">⏳</div>Fetching Gmail messages...</div>';

  try {
    const res = await apiFetch(`/gmail/api/messages?q=${encodeURIComponent(query)}`);
    const data = await res.json();

    if (!data.success) {
      if ((data.error || '').toLowerCase().includes('not connected')) {
        listEl.innerHTML = `
          <div style="padding:30px 20px; text-align:center; color:var(--text-muted);">
            <div style="font-size:32px; margin-bottom:10px;">✉️</div>
            <p style="font-weight:600; color:var(--text-main); margin-bottom:6px;">Gmail Not Connected</p>
            <p style="font-size:12px; margin-bottom:14px;">Connect your Gmail account via Google OAuth in Settings to view and manage emails.</p>
            <a href="/settings" class="btn btn-sm btn-primary">Connect Gmail in Settings</a>
          </div>
        `;
      } else {
        listEl.innerHTML = `
          <div style="padding:20px; color:var(--danger); text-align:center;">
            <p style="margin-bottom:10px;">${escapeHtml(data.error || 'Failed to load inbox')}</p>
            <button class="btn btn-sm btn-outline" onclick="loadInboxMessages('${query}')">🔄 Retry</button>
          </div>
        `;
      }
      return;
    }

    const messages = data.messages || [];
    if (messages.length === 0) {
      listEl.innerHTML = '<div style="padding:40px 20px; text-align:center; color:var(--text-muted);"><div style="font-size:28px; margin-bottom:8px;">📭</div>No emails found matching query.</div>';
      return;
    }

    listEl.innerHTML = '';
    messages.forEach((m, idx) => {
      const row = document.createElement('div');
      row.className = `email-row-item ${m.is_unread ? 'unread' : ''} ${selectedMessageId === m.id || (!selectedMessageId && idx === 0) ? 'active' : ''}`;
      row.onclick = () => selectMessage(m.id);
      
      row.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
          <span class="email-sender" style="font-size:0.875rem; color:var(--text-main);">${escapeHtml(m.from.split('<')[0])}</span>
          <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(m.date.split(' ').slice(0, 4).join(' '))}</span>
        </div>
        <div class="email-subject" style="font-size:0.875rem; margin-bottom:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
          ${escapeHtml(m.subject)}
        </div>
        <div style="font-size:0.8125rem; color:var(--text-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
          ${escapeHtml(m.snippet)}
        </div>
      `;
      listEl.appendChild(row);
    });

    if (!selectedMessageId && messages.length > 0) {
      selectMessage(messages[0].id);
    }
  } catch (err) {
    listEl.innerHTML = '<div style="padding:20px; color:var(--danger); text-align:center;">Error connecting to Gmail API.</div>';
  }
}

async function selectMessage(messageId) {
  selectedMessageId = messageId;
  document.querySelectorAll('.email-row-item').forEach(el => el.classList.remove('active'));

  const reader = document.getElementById('inbox-reader-pane');
  if (!reader) return;

  reader.innerHTML = '<div style="padding:40px; text-align:center; color:var(--text-muted);">Loading email conversation...</div>';

  try {
    const res = await apiFetch(`/gmail/api/messages/${messageId}`);
    const data = await res.json();

    if (!data.success) {
      reader.innerHTML = `<div style="padding:40px; color:var(--danger);">${escapeHtml(data.error || 'Failed to load email')}</div>`;
      return;
    }

    const m = data.message;
    const bodyContent = m.body_html || `<pre style="font-family:inherit; white-space:pre-wrap;">${escapeHtml(m.body_text)}</pre>`;

    reader.innerHTML = `
      <div class="reader-toolbar">
        <div style="display:flex; gap:8px;">
          <button class="btn btn-sm btn-primary" onclick="quickAiDraftReply('${m.id}')">✨ AI Draft Reply</button>
          <button class="btn btn-sm btn-secondary" onclick="quickAiSummarize('${m.id}')">🤖 AI Summarize</button>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-sm btn-outline" onclick="archiveEmail('${m.id}')">📦 Archive</button>
          <button class="btn btn-sm btn-outline" style="color:var(--danger);" onclick="trashEmail('${m.id}')">🗑️ Trash</button>
        </div>
      </div>
      <div class="reader-content">
        <div id="ai-summary-box" style="display:none; margin-bottom:20px; padding:14px; background:var(--primary-light-bg); border-left:4px solid var(--primary); border-radius:var(--radius-md);"></div>
        <h2 style="font-size:1.25rem; font-weight:700; margin-bottom:14px;">${escapeHtml(m.subject)}</h2>
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:20px; padding-bottom:14px; border-bottom:1px solid var(--border-color);">
          <div>
            <div style="font-weight:600; font-size:0.9375rem;">${escapeHtml(m.from)}</div>
            <div style="font-size:0.8125rem; color:var(--text-muted);">To: ${escapeHtml(m.to)}</div>
          </div>
          <div style="font-size:0.8125rem; color:var(--text-muted);">${escapeHtml(m.date)}</div>
        </div>
        <div class="email-body-rendered" style="line-height:1.6; font-size:0.9375rem;">
          ${bodyContent}
        </div>
      </div>
    `;
  } catch (err) {
    reader.innerHTML = '<div style="padding:40px; color:var(--danger);">Error loading message details.</div>';
  }
}

async function quickAiSummarize(messageId) {
  const box = document.getElementById('ai-summary-box');
  if (!box) return;
  box.style.display = 'block';
  box.innerHTML = '<em>Generating AI summary...</em>';

  try {
    const res = await apiFetch('/gmail/api/ai-summarize', {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId })
    });
    const data = await res.json();
    if (data.success) {
      box.innerHTML = `<strong>✨ AI Summary:</strong><div style="margin-top:6px;">${escapeHtml(data.summary).replace(/\n/g, '<br>')}</div>`;
    } else {
      box.innerHTML = `<span style="color:var(--danger);">AI summary failed: ${escapeHtml(data.error)}</span>`;
    }
  } catch (err) {
    box.innerHTML = '<span style="color:var(--danger);">Error generating AI summary.</span>';
  }
}

async function quickAiDraftReply(messageId) {
  showToast("AI is crafting reply draft...", "info");
  try {
    const res = await apiFetch('/gmail/api/ai-draft-reply', {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId })
    });
    const data = await res.json();
    if (data.success) {
      showToast("Draft saved successfully to Gmail!", "success");
      alert(`AI Draft Prepared & Saved to Gmail:\n\nTo: ${data.to}\nSubject: ${data.subject}\n\nContent:\n${data.reply_text}`);
    } else {
      showToast(data.error || "Failed to generate AI draft", "danger");
    }
  } catch (err) {
    showToast("Error generating AI draft", "danger");
  }
}

async function archiveEmail(messageId) {
  try {
    const res = await apiFetch('/gmail/api/actions/modify-labels', {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId, remove_labels: ['INBOX'] })
    });
    const data = await res.json();
    if (data.success) {
      showToast("Email archived", "success");
      loadInboxMessages();
    }
  } catch (err) {
    showToast("Failed to archive email", "danger");
  }
}

async function trashEmail(messageId) {
  if (!confirm("Are you sure you want to move this email to Gmail Trash?")) return;
  try {
    const res = await apiFetch('/gmail/api/actions/trash', {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId })
    });
    const data = await res.json();
    if (data.success) {
      showToast("Email moved to Trash", "info");
      loadInboxMessages();
    }
  } catch (err) {
    showToast("Failed to trash email", "danger");
  }
}
