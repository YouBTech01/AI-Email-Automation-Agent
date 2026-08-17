/**
 * AI Chat Assistant Controller: Multi-Turn Conversations, Safe Tool Confirmation, Session Management.
 */

let currentSessionId = null;

document.addEventListener('DOMContentLoaded', () => {
  loadChatSessions();

  const chatInput = document.getElementById('chat-input-textarea');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }
});

async function loadChatSessions() {
  try {
    const res = await apiFetch('/chat/api/sessions');
    const data = await res.json();
    const listEl = document.getElementById('chat-sessions-list');
    if (!listEl) return;

    listEl.innerHTML = '';
    if (data.sessions && data.sessions.length > 0) {
      data.sessions.forEach((s, idx) => {
        const item = document.createElement('div');
        item.className = `chat-session-item ${currentSessionId === s.id || (!currentSessionId && idx === 0) ? 'active' : ''}`;
        item.innerHTML = `
          <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;" onclick="switchSession(${s.id})">
            ${escapeHtml(s.title)}
          </span>
          <button class="btn btn-sm btn-outline" style="padding:2px 6px; font-size:10px;" onclick="deleteSession(event, ${s.id})">✕</button>
        `;
        listEl.appendChild(item);
      });

      if (!currentSessionId) {
        switchSession(data.sessions[0].id);
      }
    } else {
      listEl.innerHTML = '<div style="padding:12px; color:var(--text-muted); font-size:12px; text-align:center;">No previous chats</div>';
    }
  } catch (err) {
    console.error("Failed to load chat sessions:", err);
  }
}

async function switchSession(sessionId) {
  currentSessionId = sessionId;
  document.querySelectorAll('.chat-session-item').forEach(el => el.classList.remove('active'));
  
  const container = document.getElementById('chat-messages-container');
  if (container) container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted);">Loading conversation...</div>';

  try {
    const res = await apiFetch(`/chat/api/sessions/${sessionId}/messages`);
    const data = await res.json();
    renderMessages(data.messages || []);
    loadChatSessions(); // Update active highlights
  } catch (err) {
    showToast("Failed to load messages", "danger");
  }
}

function startNewChat() {
  currentSessionId = null;
  const container = document.getElementById('chat-messages-container');
  if (container) {
    container.innerHTML = `
      <div class="chat-message assistant">
        <div class="chat-avatar assistant">AI</div>
        <div class="chat-bubble">
          Hello! I am your AI Email Automation Agent. I can help you search, summarize, draft, reply, and organize your Gmail messages safely. What would you like to do today?
        </div>
      </div>
    `;
  }
  document.querySelectorAll('.chat-session-item').forEach(el => el.classList.remove('active'));
  document.getElementById('chat-input-textarea').focus();
}

async function deleteSession(event, sessionId) {
  event.stopPropagation();
  if (!confirm("Are you sure you want to delete this chat session?")) return;
  try {
    await apiFetch(`/chat/api/sessions/${sessionId}`, { method: 'DELETE' });
    showToast("Chat deleted", "info");
    if (currentSessionId === sessionId) currentSessionId = null;
    loadChatSessions();
  } catch (err) {
    showToast("Failed to delete chat", "danger");
  }
}

async function sendChatMessage() {
  const inputEl = document.getElementById('chat-input-textarea');
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = '';
  inputEl.style.height = 'auto';

  // Append user message bubble
  appendMessageBubble('user', text);

  // Show typing indicator
  const typingId = appendTypingIndicator();

  const providerSelect = document.getElementById('chat-provider-select');
  const modelSelect = document.getElementById('chat-model-select');
  const providerId = providerSelect ? providerSelect.value : null;
  const modelName = modelSelect ? modelSelect.value : null;

  try {
    const res = await apiFetch('/chat/api/send', {
      method: 'POST',
      body: JSON.stringify({
        session_id: currentSessionId,
        message: text,
        provider_id: providerId,
        model_name: modelName
      })
    });

    const data = await res.json();
    removeTypingIndicator(typingId);

    if (data.session_id && (!currentSessionId || currentSessionId !== data.session_id)) {
      currentSessionId = data.session_id;
      loadChatSessions();
    }

    if (data.requires_confirmation && data.pending_actions) {
      appendConfirmationCard(data.message_id, data.content, data.pending_actions);
    } else {
      appendMessageBubble('assistant', data.content);
    }

  } catch (err) {
    removeTypingIndicator(typingId);
    appendMessageBubble('assistant', "Sorry, an error occurred while processing your request.");
    showToast("Error communicating with AI server", "danger");
  }
}

function renderMessages(messages) {
  const container = document.getElementById('chat-messages-container');
  if (!container) return;

  container.innerHTML = '';
  if (messages.length === 0) {
    startNewChat();
    return;
  }

  messages.forEach(m => {
    if (m.pending_action_json && m.risk_tier === 'HIGH') {
      try {
        const pending = JSON.parse(m.pending_action_json);
        appendConfirmationCard(m.id, m.content, pending);
      } catch (e) {
        appendMessageBubble(m.role, m.content);
      }
    } else {
      appendMessageBubble(m.role, m.content);
    }
  });

  scrollToBottom();
}

function appendMessageBubble(role, content) {
  const container = document.getElementById('chat-messages-container');
  if (!container) return;

  const div = document.createElement('div');
  div.className = `chat-message ${role}`;
  const avatarText = role === 'user' ? 'U' : 'AI';

  div.innerHTML = `
    <div class="chat-avatar ${role}">${avatarText}</div>
    <div class="chat-bubble">${formatMarkdown(content)}</div>
  `;

  container.appendChild(div);
  scrollToBottom();
}

function appendConfirmationCard(messageId, promptText, actions) {
  const container = document.getElementById('chat-messages-container');
  if (!container) return;

  const div = document.createElement('div');
  div.className = 'chat-message assistant';
  div.id = `msg-confirm-${messageId}`;

  let actionsHtml = '';
  actions.forEach(a => {
    actionsHtml += `
      <div class="action-details-preview">
        <strong>${escapeHtml(a.description || a.tool_name)}</strong>
        <pre style="margin-top:6px; font-size:11px; white-space:pre-wrap;">${escapeHtml(JSON.stringify(a.tool_args, null, 2))}</pre>
      </div>
    `;
  });

  div.innerHTML = `
    <div class="chat-avatar assistant">AI</div>
    <div class="chat-bubble">
      <div>${formatMarkdown(promptText)}</div>
      <div class="action-confirmation-card">
        <h4>⚠️ High-Impact Action Requires Confirmation</h4>
        <p style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">
          This action will modify your Gmail inbox or send an email. Please review the details carefully before proceeding:
        </p>
        ${actionsHtml}
        <div style="display:flex; gap:10px; margin-top:12px;">
          <button class="btn btn-sm btn-primary" onclick="confirmChatAction(${messageId}, true)">✓ Confirm & Execute</button>
          <button class="btn btn-sm btn-outline" onclick="confirmChatAction(${messageId}, false)">✕ Cancel</button>
        </div>
      </div>
    </div>
  `;

  container.appendChild(div);
  scrollToBottom();
}

async function confirmChatAction(messageId, approved) {
  const cardEl = document.getElementById(`msg-confirm-${messageId}`);
  if (cardEl) {
    const card = cardEl.querySelector('.action-confirmation-card');
    if (card) card.innerHTML = `<div style="color:var(--text-muted); font-size:12px;">${approved ? 'Executing action...' : 'Cancelling action...'}</div>`;
  }

  try {
    const res = await apiFetch('/chat/api/confirm-action', {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId, approved: approved })
    });
    const data = await res.json();
    
    if (cardEl) {
      cardEl.remove();
    }
    
    appendMessageBubble('assistant', data.message || (approved ? 'Action executed.' : 'Action cancelled.'));
    showToast(data.message, approved ? 'success' : 'info');
  } catch (err) {
    showToast("Failed to execute confirmed action", "danger");
  }
}

function appendTypingIndicator() {
  const container = document.getElementById('chat-messages-container');
  const id = `typing-${Date.now()}`;
  const div = document.createElement('div');
  div.id = id;
  div.className = 'chat-message assistant';
  div.innerHTML = `
    <div class="chat-avatar assistant">AI</div>
    <div class="chat-bubble" style="color:var(--text-muted); font-style:italic;">Thinking & inspecting Gmail...</div>
  `;
  container.appendChild(div);
  scrollToBottom();
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function scrollToBottom() {
  const container = document.getElementById('chat-messages-container');
  if (container) container.scrollTop = container.scrollHeight;
}

function exportCurrentChat() {
  if (!currentSessionId) {
    showToast("No chat session selected", "warning");
    return;
  }
  window.location.href = `/chat/api/export/${currentSessionId}`;
}

function formatMarkdown(text) {
  if (!text) return '';
  let str = escapeHtml(text);
  // Links [text](url)
  str = str.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" style="color:var(--primary); font-weight:600; text-decoration:underline;">$1</a>');
  // Bold
  str = str.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic
  str = str.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Code block
  str = str.replace(/```(.*?)```/gs, '<pre style="background:var(--bg-surface); padding:8px; border-radius:4px; margin:6px 0; overflow-x:auto;"><code>$1</code></pre>');
  // Inline code
  str = str.replace(/`([^`]+)`/g, '<code style="background:var(--bg-surface); padding:2px 6px; border-radius:4px; font-size:12px;">$1</code>');
  // Line breaks
  str = str.replace(/\n/g, '<br>');
  return str;
}

function escapeHtml(unsafe) {
  if (!unsafe) return '';
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
