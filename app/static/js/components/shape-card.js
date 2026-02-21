/* shape-card.js – Web Component for Panel Drag & Drop */

class ShapeCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.render();
    const shape = JSON.parse(this.getAttribute('shape'));
    const preview = this.shadowRoot.getElementById('preview-' + shape.id);
    if (preview) {
      preview.addEventListener('mousedown', e => {
        if (e.button !== 0) return;
        this.triggerDragDrop();
      });
    }
  }

  static get observedAttributes() { return ['shape']; }

  render() {
    const shape = JSON.parse(this.getAttribute('shape'));
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; font-family: 'Open Sans', sans-serif; }
        .card {
          background: #fff;
          border: 1px solid #E8E0D8;
          border-radius: 8px;
          padding: 0.5rem;
          margin-bottom: 0.4rem;
          display: flex;
          gap: 0.5rem;
          align-items: center;
          cursor: grab;
          transition: background-color 150ms ease;
          user-select: none;
        }
        .card:hover { background-color: #F5F0EB; }
        .card:active { cursor: grabbing; }
        .img-wrap {
          width: 44px;
          height: 44px;
          flex-shrink: 0;
          background: #F5F0EB;
          border-radius: 4px;
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        img { max-width: 100%; max-height: 100%; object-fit: contain; display: block; }
        .body { flex: 1; min-width: 0; }
        .name {
          font-size: 0.82rem;
          font-weight: 600;
          color: #1C1C1A;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .meta {
          font-size: 0.7rem;
          color: #6B6B67;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      </style>
      <div class="card" id="preview-${shape.id}">
        <div class="img-wrap">
          <img src="/static/images/shapes/${shape.id}.png" alt="${this._esc(shape.name)}">
        </div>
        <div class="body">
          <div class="name">${this._esc(shape.name)}</div>
          <div class="meta">${this._esc(shape.keywords)}</div>
        </div>
      </div>
    `;
  }

  _esc(str) {
    return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  triggerDragDrop() {
    const shape = JSON.parse(this.getAttribute('shape'));
    if (shape.data_object) {
      this._doDragDrop(shape.data_object);
    } else {
      fetch(`/get_shape/${shape.id}`)
        .then(r => r.text())
        .then(dataObject => {
          shape.data_object = dataObject;
          this.setAttribute('shape', JSON.stringify(shape));
          this.dispatchEvent(new CustomEvent('dataObjectAdded', {
            detail: { shape }, bubbles: true, composed: true
          }));
          this._doDragDrop(dataObject);
        })
        .catch(err => console.error('get_shape failed:', err));
    }
  }

  _doDragDrop(dataObject) {
    try {
      const hostObjects = window.chrome?.webview?.hostObjects;
      if (hostObjects && hostObjects.WebViewDragDrop) {
        hostObjects.WebViewDragDrop.DragDropShape(dataObject);
      }
    } catch (err) {
      console.warn('WebViewDragDrop not available:', err);
    }
  }
}

customElements.define('shape-card', ShapeCard);
