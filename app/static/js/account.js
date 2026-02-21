/* account.js – Account management: tabs, edit, delete */

// ── Tabs ──
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
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
          metaEl.firstChild.textContent = `Keywords: ${json.keywords}`;
        }
      }
      toggleEdit(type, id);
    } else {
      alert('Fehler beim Speichern. Bitte versuche es erneut.');
    }
  } catch (err) {
    alert('Netzwerkfehler. Bitte versuche es erneut.');
  }
}

// ── Delete ──
let pendingDelete = null;

function confirmDelete(type, id, name) {
  const dialog = document.getElementById('delete-dialog');
  document.getElementById('delete-dialog-text').textContent =
    `Möchtest du "${name}" wirklich unwiderruflich löschen?`;
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
      alert('Fehler beim Löschen. Bitte versuche es erneut.');
    }
  } catch (err) {
    alert('Netzwerkfehler. Bitte versuche es erneut.');
  }
  pendingDelete = null;
});
