/* account.js – Account management: tabs, edit, delete, change name */

// ── Inline name edit ──
const nameEl = document.getElementById('account-display-name');
nameEl.addEventListener('click', () => {
  const originalName = nameEl.textContent;

  const input = document.createElement('input');
  input.type = 'text';
  input.value = originalName;
  input.className = 'form-control';
  input.style.cssText = 'display:inline-block; width:15rem; padding:.2rem .4rem; font-size:inherit';

  const errorEl = document.createElement('span');
  errorEl.style.cssText = 'color:var(--color-danger); font-size:.85em; margin-left:.5rem';

  nameEl.replaceWith(input);
  input.after(errorEl);
  input.focus();
  input.select();

  async function save() {
    const newName = input.value.trim();
    if (!newName || newName === originalName) { cancel(); return; }
    try {
      const res = await fetch('/account/change_name', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `name=${encodeURIComponent(newName)}`
      });
      if (res.ok) {
        const json = await res.json();
        nameEl.textContent = json.name;
        errorEl.remove();
        input.replaceWith(nameEl);
      } else {
        errorEl.textContent = res.status === 409
          ? window.TRANSLATIONS.name_taken
          : window.TRANSLATIONS.save_error;
        input.focus();
      }
    } catch {
      errorEl.textContent = window.TRANSLATIONS.network_error;
      input.focus();
    }
  }

  function cancel() {
    errorEl.remove();
    input.replaceWith(nameEl);
  }

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); save(); }
    if (e.key === 'Escape') { cancel(); }
  });
  input.addEventListener('blur', () => setTimeout(() => {
    if (document.body.contains(input)) cancel();
  }, 150));
});

// ── Inline email edit ──
const emailEl = document.getElementById('account-display-email');
const pendingHint = document.getElementById('pending-email-hint');

function setupEmailEdit() {
  emailEl.classList.add('editable-name');
  emailEl.title = window.TRANSLATIONS.click_to_edit;
  emailEl.addEventListener('click', startEmailEdit);
}

function startEmailEdit() {
  const originalEmail = emailEl.textContent;

  const input = document.createElement('input');
  input.type = 'email';
  input.value = originalEmail;
  input.className = 'form-control';
  input.style.cssText = 'display:inline-block; width:18rem; padding:.2rem .4rem; font-size:inherit';

  const errorEl = document.createElement('span');
  errorEl.style.cssText = 'color:var(--color-danger); font-size:.85em; margin-left:.5rem';

  emailEl.replaceWith(input);
  input.after(errorEl);
  input.focus();
  input.select();

  async function save() {
    const newEmail = input.value.trim();
    if (!newEmail || newEmail === originalEmail) { cancel(); return; }
    if (!input.checkValidity()) {
      errorEl.textContent = window.TRANSLATIONS.invalid_email;
      input.focus();
      return;
    }
    try {
      const res = await fetch('/account/change_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `email=${encodeURIComponent(newEmail)}`
      });
      if (res.ok) {
        const json = await res.json();
        errorEl.remove();
        input.replaceWith(emailEl);
        // Show pending hint, disable editing until cancelled
        emailEl.classList.remove('editable-name');
        emailEl.removeEventListener('click', startEmailEdit);
        emailEl.title = '';
        pendingHint.innerHTML =
          ` &rarr; <em>${json.pending_email}</em> ${window.TRANSLATIONS.pending_confirmation} ` +
          `<a href="#" id="cancel-email-change-link">${window.TRANSLATIONS.cancel}</a>`;
        pendingHint.style.display = 'inline';
        setupCancelLink();
      } else if (res.status === 409) {
        errorEl.textContent = window.TRANSLATIONS.email_taken;
        input.focus();
      } else if (res.status === 422) {
        errorEl.textContent = window.TRANSLATIONS.invalid_email;
        input.focus();
      } else {
        errorEl.textContent = window.TRANSLATIONS.save_error;
        input.focus();
      }
    } catch {
      errorEl.textContent = window.TRANSLATIONS.network_error;
      input.focus();
    }
  }

  function cancel() {
    errorEl.remove();
    input.replaceWith(emailEl);
  }

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); save(); }
    if (e.key === 'Escape') { cancel(); }
  });
  input.addEventListener('blur', () => setTimeout(() => {
    if (document.body.contains(input)) cancel();
  }, 150));
}

function setupCancelLink() {
  const link = document.getElementById('cancel-email-change-link');
  if (!link) return;
  link.addEventListener('click', async e => {
    e.preventDefault();
    try {
      const res = await fetch('/account/cancel_email_change', { method: 'POST' });
      if (res.ok) {
        pendingHint.style.display = 'none';
        pendingHint.innerHTML = '';
        setupEmailEdit();
      }
    } catch { /* ignore */ }
  });
}

// Init: if no pending email on page load, make it editable
if (!pendingHint.textContent.trim()) {
  setupEmailEdit();
} else {
  setupCancelLink();
}

// ── Tabs ──
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const panel = document.getElementById('tab-' + btn.dataset.tab);
    panel.classList.add('active');
    panel.querySelectorAll('img[data-src]').forEach(img => {
      img.src = img.dataset.src;
      delete img.dataset.src;
    });
  });
});

// ── Edit form toggle ──
function toggleEdit(type, id) {
  const form = document.getElementById(`edit-${type}-${id}`);
  form.classList.toggle('active');
}

// ── Inline edit submit ──
async function submitEdit(event, type, id) {
  event.preventDefault();
  const form = event.target;
  const data = new FormData(form);
  const params = new URLSearchParams(data);

  try {
    const res = await fetch(`/account/${type}/${id}/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString()
    });
    if (res.ok) {
      const json = await res.json();
      // Update displayed name
      const item = document.getElementById(`${type}-item-${id}`);
      if (item) {
        const nameEl = item.querySelector('.account-item-name');
        if (nameEl) nameEl.textContent = json.name ?? json.title ?? '';
        const metaEl = item.querySelector('.account-item-meta');
        if (metaEl && type === 'shape') {
          metaEl.firstChild.textContent = `${window.TRANSLATIONS.keywords_label} ${json.keywords}`;
        }
      }
      toggleEdit(type, id);
    } else {
      alert(window.TRANSLATIONS.save_error);
    }
  } catch (err) {
    alert(window.TRANSLATIONS.network_error);
  }
}

// ── Delete ──
let pendingDelete = null;

function confirmDelete(type, id, name) {
  const dialog = document.getElementById('delete-dialog');
  document.getElementById('delete-dialog-text').textContent =
    window.TRANSLATIONS.delete_confirm.replace('{name}', name);
  pendingDelete = { type, id };
  dialog.showModal();
}

document.getElementById('delete-confirm-btn').addEventListener('click', async () => {
  if (!pendingDelete) return;
  const { type, id } = pendingDelete;
  const dialog = document.getElementById('delete-dialog');
  dialog.close();

  try {
    const res = await fetch(`/account/${type}/${id}/delete`, { method: 'POST' });
    if (res.ok) {
      const item = document.getElementById(`${type}-item-${id}`);
      if (item) item.remove();
    } else {
      alert(window.TRANSLATIONS.delete_error);
    }
  } catch (err) {
    alert(window.TRANSLATIONS.network_error);
  }
  pendingDelete = null;
});
