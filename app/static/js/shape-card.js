/* shape-card.js – shared card builder for browse and landing */

function escHtml(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

const DL_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;

function buildCard(shape) {
  const stencilRow = shape.stencil_id
    ? `<div class="shape-card-stencil">
        <span class="shape-card-stencil-name">${escHtml(shape.stencil_file_name)}</span>
        <a href="/download_stencil/${shape.stencil_id}" class="shape-card-dl-btn" title="${window.TRANSLATIONS.download}">${DL_ICON}</a>
      </div>`
    : '';

  return `
    <div class="shape-card" title="${escHtml(shape.prompt)}">
      <div class="shape-card-image">
        <img src="/static/images/shapes/${shape.id}.png" alt="${escHtml(shape.name)}" loading="lazy">
      </div>
      <div class="shape-card-body">
        <div class="shape-card-name">${escHtml(shape.name)}</div>
        <div class="shape-card-keywords">${escHtml(shape.keywords)}</div>
        ${stencilRow}
      </div>
      <div class="shape-card-footer">
        <span class="shape-card-user">${escHtml(shape.team_name || shape.user_name)}</span>
        <span class="shape-card-count">&darr; ${shape.download_count ?? 0}</span>
      </div>
    </div>
  `;
}
