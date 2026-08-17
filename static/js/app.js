/**
 * Global Application Utilities: Theme, Modals, Snackbars, CSRF AJAX Headers.
 */

// Theme Management (Dark / Light)
function initTheme() {
  const savedTheme = localStorage.getItem('app_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('app_theme', next);
}

// Global Snackbar / Toast Alert
function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('snackbar-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'snackbar-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `snackbar snackbar-${type}`;
  
  const icon = type === 'success' ? '✓' : (type === 'danger' ? '✕' : 'ℹ');
  toast.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <span style="font-weight: bold;">${icon}</span>
      <span>${message}</span>
    </div>
    <button style="background:none; border:none; color:inherit; cursor:pointer; font-size:16px;" onclick="this.parentElement.remove()">✕</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Modal Dialog Helpers
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

// CSRF Header Helper for Fetch requests
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

async function apiFetch(url, options = {}) {
  const headers = options.headers || {};
  headers['X-CSRF-Token'] = getCsrfToken();
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  options.headers = headers;
  return fetch(url, options);
}

// Initialize on DOM Load
document.addEventListener('DOMContentLoaded', () => {
  initTheme();

  // Close modals on clicking overlay background
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('active');
    });
  });
});
