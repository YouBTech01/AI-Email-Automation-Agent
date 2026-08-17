/**
 * Visual Automation Builder & Workflow Management Controller.
 */

document.addEventListener('DOMContentLoaded', () => {
  const condContainer = document.getElementById('conditions-list-container');
  const actContainer = document.getElementById('actions-list-container');

  if (condContainer && actContainer) {
    const initialData = window.INITIAL_WORKFLOW_DATA || {};
    
    // Initialize Conditions
    if (initialData.conditions && initialData.conditions.length > 0) {
      initialData.conditions.forEach(c => {
        addConditionRow(c.field, c.operator, c.value);
      });
    } else {
      addConditionRow('sender', 'contains', '');
    }

    // Initialize Actions
    if (initialData.actions && initialData.actions.length > 0) {
      initialData.actions.forEach(a => {
        addActionRow(a.action_type, a.config || {});
      });
    } else {
      addActionRow('generate_draft', { instruction: 'Reply politely and address customer inquiry' });
    }
  }
});

function addConditionRow(field = 'sender', operator = 'contains', value = '') {
  const container = document.getElementById('conditions-list-container');
  if (!container) return;

  const row = document.createElement('div');
  row.className = 'condition-row';
  row.style.cssText = 'display: flex; gap: 10px; margin-bottom: 10px; align-items: center; background: var(--bg-surface-secondary); padding: 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);';

  row.innerHTML = `
    <select class="form-select condition-field" style="flex: 2; font-size: 13px;">
      <option value="sender" ${field === 'sender' ? 'selected' : ''}>Sender Email / Domain</option>
      <option value="subject" ${field === 'subject' ? 'selected' : ''}>Subject Line</option>
      <option value="body" ${field === 'body' ? 'selected' : ''}>Body Text</option>
      <option value="ai_category" ${field === 'ai_category' ? 'selected' : ''}>AI Intent Category</option>
      <option value="has_attachment" ${field === 'has_attachment' ? 'selected' : ''}>Has Attachment</option>
    </select>
    <select class="form-select condition-operator" style="flex: 2; font-size: 13px;">
      <option value="contains" ${operator === 'contains' ? 'selected' : ''}>contains</option>
      <option value="not_contains" ${operator === 'not_contains' ? 'selected' : ''}>does not contain</option>
      <option value="equals" ${operator === 'equals' ? 'selected' : ''}>equals</option>
      <option value="matches_regex" ${operator === 'matches_regex' ? 'selected' : ''}>matches regex</option>
    </select>
    <input type="text" class="form-control condition-value" value="${escapeHtml(value)}" placeholder="e.g. client.com, invoice, or refund" style="flex: 3; font-size: 13px;">
    <button type="button" class="btn btn-sm btn-outline" style="color:var(--danger); border-color:var(--danger); padding: 4px 10px;" onclick="this.closest('.condition-row').remove()" title="Delete condition">✕</button>
  `;

  container.appendChild(row);
}

function addActionRow(actionType = 'generate_draft', config = {}) {
  const container = document.getElementById('actions-list-container');
  if (!container) return;

  const row = document.createElement('div');
  row.className = 'action-row';
  row.style.cssText = 'display: flex; flex-direction: column; gap: 10px; margin-bottom: 14px; padding: 14px; background: var(--bg-surface-secondary); border-radius: var(--radius-md); border: 1px solid var(--border-color);';

  row.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <select class="form-select action-type" style="width: auto; font-weight: 600; font-size: 13px;" onchange="updateActionConfigBox(this)">
        <option value="generate_draft" ${actionType === 'generate_draft' ? 'selected' : ''}>📝 Generate AI Reply Draft</option>
        <option value="send_reply" ${actionType === 'send_reply' ? 'selected' : ''}>⚡ Send AI Auto-Reply (If Trusted)</option>
        <option value="add_label" ${actionType === 'add_label' ? 'selected' : ''}>🏷️ Apply Gmail Label</option>
        <option value="archive" ${actionType === 'archive' ? 'selected' : ''}>📦 Archive Message</option>
        <option value="forward" ${actionType === 'forward' ? 'selected' : ''}>↗️ Forward Email</option>
      </select>
      <button type="button" class="btn btn-sm btn-outline" style="color:var(--danger); border-color:var(--danger);" onclick="this.closest('.action-row').remove()">✕ Remove</button>
    </div>
    <div class="action-config-box"></div>
  `;

  container.appendChild(row);
  const typeSelect = row.querySelector('.action-type');
  renderActionConfigInputs(row.querySelector('.action-config-box'), typeSelect.value, config);
}

function updateActionConfigBox(selectEl) {
  const row = selectEl.closest('.action-row');
  const box = row.querySelector('.action-config-box');
  renderActionConfigInputs(box, selectEl.value, {});
}

function renderActionConfigInputs(container, actionType, config = {}) {
  if (actionType === 'add_label') {
    container.innerHTML = `
      <label class="form-label" style="font-size:12px; margin-bottom:4px;">Gmail Label Name</label>
      <input type="text" class="form-control action-label" value="${escapeHtml(config.label || '')}" placeholder="e.g. VIP, Invoices, Support, or Urgent">
    `;
  } else if (actionType === 'forward') {
    container.innerHTML = `
      <label class="form-label" style="font-size:12px; margin-bottom:4px;">Forward To Email Address</label>
      <input type="email" class="form-control action-forward-to" value="${escapeHtml(config.to || '')}" placeholder="e.g. manager@yourcompany.com">
      <input type="text" class="form-control action-instruction" style="margin-top:6px;" value="${escapeHtml(config.instruction || '')}" placeholder="Optional note to include in forwarded message">
    `;
  } else if (actionType === 'archive') {
    container.innerHTML = `
      <p style="font-size: 12px; color: var(--text-muted); margin: 0;">Automatically archives matched email by removing it from the Gmail INBOX.</p>
    `;
  } else {
    // generate_draft or send_reply
    container.innerHTML = `
      <label class="form-label" style="font-size:12px; margin-bottom:4px;">Custom AI Instructions / Tone Guidelines</label>
      <textarea class="form-control action-instruction" rows="2" placeholder="e.g. Acknowledge customer question politely, refer to our pricing policy, and invite them to schedule a call.">${escapeHtml(config.instruction || '')}</textarea>
    `;
  }
}

async function saveAutomation(event) {
  if (event) event.preventDefault();

  const id = document.getElementById('automation-id') ? document.getElementById('automation-id').value : null;
  const name = document.getElementById('automation-name').value.trim();
  const description = document.getElementById('automation-description').value.trim();
  const triggerType = document.getElementById('automation-trigger-type').value;
  const confidenceThreshold = document.getElementById('automation-confidence').value;
  const approvalMode = document.getElementById('automation-approval-mode').value;

  if (!name) {
    showToast("Please provide a name for this automation", "warning");
    return;
  }

  // Collect conditions
  const conditions = [];
  document.querySelectorAll('.condition-row').forEach(row => {
    const f = row.querySelector('.condition-field').value;
    const op = row.querySelector('.condition-operator').value;
    const val = row.querySelector('.condition-value').value.trim();
    if (val) {
      conditions.push({ field: f, operator: op, value: val });
    }
  });

  // Collect actions
  const actions = [];
  document.querySelectorAll('.action-row').forEach(row => {
    const aType = row.querySelector('.action-type').value;
    let cfg = {};
    if (aType === 'add_label') {
      const labelInput = row.querySelector('.action-label');
      cfg = { label: labelInput ? labelInput.value.trim() : '' };
    } else if (aType === 'forward') {
      const toInput = row.querySelector('.action-forward-to');
      const instInput = row.querySelector('.action-instruction');
      cfg = { 
        to: toInput ? toInput.value.trim() : '',
        instruction: instInput ? instInput.value.trim() : ''
      };
    } else {
      const instInput = row.querySelector('.action-instruction');
      cfg = { instruction: instInput ? instInput.value.trim() : '' };
    }

    actions.push({
      action_type: aType,
      config: cfg
    });
  });

  if (actions.length === 0) {
    showToast("Please add at least one action for this automation", "warning");
    return;
  }

  const payload = {
    id: id || null,
    name: name,
    description: description,
    trigger_type: triggerType,
    confidence_threshold: confidenceThreshold,
    approval_mode: approvalMode,
    triggers: [{ trigger_type: triggerType, config: {} }],
    conditions: conditions,
    actions: actions
  };

  try {
    const res = await apiFetch('/automations/api/save', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast("Automation workflow saved successfully!", "success");
      setTimeout(() => {
        window.location.href = '/automations';
      }, 700);
    } else {
      showToast(data.error || "Failed to save automation", "danger");
    }
  } catch (err) {
    showToast("Error saving automation", "danger");
  }
}

async function toggleAutomation(autoId) {
  try {
    const res = await apiFetch(`/automations/api/${autoId}/toggle`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(`Automation status: ${data.new_status}`, "info");
      setTimeout(() => window.location.reload(), 500);
    }
  } catch (err) {
    showToast("Failed to toggle status", "danger");
  }
}

async function deleteAutomation(autoId) {
  if (!confirm("Are you sure you want to delete this automation workflow?")) return;
  try {
    const res = await apiFetch(`/automations/api/${autoId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      showToast("Automation deleted", "info");
      setTimeout(() => window.location.reload(), 500);
    }
  } catch (err) {
    showToast("Failed to delete automation", "danger");
  }
}

function toggleAIAssistantBox() {
  const box = document.getElementById('ai-builder-assistant-card');
  if (!box) return;
  box.style.display = box.style.display === 'none' ? 'block' : 'none';
}

const STARTER_RECIPES = {
  support: {
    name: 'Customer Inquiries & Support',
    description: 'Auto-drafts polite, helpful replies to incoming customer inquiries',
    trigger_type: 'new_email',
    conditions: [
      { field: 'body', operator: 'contains', value: 'help' }
    ],
    actions: [
      { action_type: 'generate_draft', config: { instruction: 'Thank customer, acknowledge question politely, and explain standard response time.' } }
    ],
    approval_mode: 'draft_only',
    confidence_threshold: 85
  },
  pricing: {
    name: 'Pricing & Quote Requests',
    description: 'Prepares draft reply for pricing questions and invites them to demo call',
    trigger_type: 'new_email',
    conditions: [
      { field: 'body', operator: 'contains', value: 'pricing' }
    ],
    actions: [
      { action_type: 'generate_draft', config: { instruction: 'Provide standard pricing overview and invite them to schedule a walkthrough call.' } }
    ],
    approval_mode: 'draft_only',
    confidence_threshold: 85
  },
  refund: {
    name: 'Refund & Dispute Shield',
    description: 'Acknowledge refund inquiries and create a 1-click admin approval card before sending',
    trigger_type: 'keyword_match',
    conditions: [
      { field: 'body', operator: 'contains', value: 'refund' }
    ],
    actions: [
      { action_type: 'generate_draft', config: { instruction: 'Acknowledge refund request and state that our billing team will review within 3 business days.' } }
    ],
    approval_mode: 'approval_required',
    confidence_threshold: 90
  },
  vip: {
    name: 'VIP & Urgent Client Escalation',
    description: 'Applies VIP label and drafts quick receipt confirmation',
    trigger_type: 'new_email',
    conditions: [
      { field: 'subject', operator: 'contains', value: 'urgent' }
    ],
    actions: [
      { action_type: 'add_label', config: { label: 'VIP' } },
      { action_type: 'generate_draft', config: { instruction: 'Confirm receipt of urgent priority message and state that our lead manager is reviewing.' } }
    ],
    approval_mode: 'draft_only',
    confidence_threshold: 90
  },
  newsletter: {
    name: 'Auto-Archive Newsletters & Promotions',
    description: 'Automatically labels newsletters and removes them from the Inbox',
    trigger_type: 'new_email',
    conditions: [
      { field: 'body', operator: 'contains', value: 'unsubscribe' }
    ],
    actions: [
      { action_type: 'add_label', config: { label: 'Newsletters' } },
      { action_type: 'archive', config: {} }
    ],
    approval_mode: 'trusted_auto',
    confidence_threshold: 80
  }
};

function applyRecipe(recipeKey) {
  const recipe = STARTER_RECIPES[recipeKey];
  if (!recipe) return;
  populateFormFromWorkflow(recipe);
  showToast(`Applied "${recipe.name}" recipe!`, 'success');
}

function populateFormFromWorkflow(wf) {
  if (wf.name) document.getElementById('automation-name').value = wf.name;
  if (wf.description) document.getElementById('automation-description').value = wf.description;
  if (wf.trigger_type) document.getElementById('automation-trigger-type').value = wf.trigger_type;
  if (wf.approval_mode) document.getElementById('automation-approval-mode').value = wf.approval_mode;
  if (wf.confidence_threshold) {
    document.getElementById('automation-confidence').value = wf.confidence_threshold;
    const valEl = document.getElementById('confidence-val');
    if (valEl) valEl.innerText = wf.confidence_threshold + '%';
  }

  // Clear & fill conditions
  const condContainer = document.getElementById('conditions-list-container');
  if (condContainer) {
    condContainer.innerHTML = '';
    const conds = wf.conditions || [];
    if (conds.length > 0) {
      conds.forEach(c => addConditionRow(c.field, c.operator, c.value));
    } else {
      addConditionRow('sender', 'contains', '');
    }
  }

  // Clear & fill actions
  const actContainer = document.getElementById('actions-list-container');
  if (actContainer) {
    actContainer.innerHTML = '';
    const acts = wf.actions || [];
    if (acts.length > 0) {
      acts.forEach(a => addActionRow(a.action_type, a.config || {}));
    } else {
      addActionRow('generate_draft', { instruction: 'Reply politely and address customer inquiry' });
    }
  }
}

async function generateWorkflowWithAI() {
  const input = document.getElementById('ai-assistant-prompt-input');
  if (!input) return;
  const prompt = input.value.trim();
  if (!prompt) {
    showToast("Please describe what you want to automate", "warning");
    input.focus();
    return;
  }

  const btn = document.getElementById('btn-generate-ai-workflow');
  const btnText = document.getElementById('ai-generate-btn-text');
  if (btn) btn.disabled = true;
  if (btnText) btnText.innerHTML = '⏳ Analyzing & Generating...';

  try {
    const res = await apiFetch('/automations/api/ai-generate-workflow', {
      method: 'POST',
      body: JSON.stringify({ prompt: prompt })
    });
    const data = await res.json();
    if (data.success && data.workflow) {
      populateFormFromWorkflow(data.workflow);
      showToast("🪄 Workflow auto-configured by AI! Review below and click Save.", "success");
    } else {
      showToast(data.error || "Failed to generate workflow", "danger");
    }
  } catch (err) {
    showToast("Error communicating with AI assistant", "danger");
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.innerHTML = '🪄 Auto-Fill Workflow';
  }
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
