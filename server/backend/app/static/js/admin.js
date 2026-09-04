async function api(url, opts) {
  const r = await fetch(url, opts);
  let body = {};
  try { body = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(body.detail || 'Request failed');
  return body;
}

function atCanvas() {
  return {
    version: '',
    pages: [
      { id: 'dashboard', label: 'Dashboard' },
      { id: 'layouts', label: 'Layouts' },
      { id: 'displays', label: 'Displays' },
    ],
    page: 'dashboard',
    widgetTypes: ['clock', 'text'],
    layouts: [],
    displays: [],
    currentLayout: null,
    layers: [],
    selectedLayer: null,
    modal: { open: false, title: '', type: '', form: {}, onSubmit: null },
    toast: { msg: '', error: false },

    async init() {
      try {
        const h = await api('/api/health');
        this.version = h.version;
      } catch (e) {}
      await Promise.all([this.loadLayouts(), this.loadDisplays()]);
      const hash = location.hash.replace('#', '');
      if (['layouts', 'displays'].includes(hash)) this.go(hash);
    },

    go(page) {
      this.page = page;
      location.hash = page === 'dashboard' ? '' : page;
    },

    showToast(msg, error = false) {
      this.toast = { msg, error };
      setTimeout(() => { this.toast.msg = ''; }, 2500);
    },

    async loadLayouts() { this.layouts = await api('/api/layouts'); },
    async loadDisplays() { this.displays = await api('/api/displays'); },

    currentLayoutName() {
      const l = this.layouts.find(x => x.id === this.currentLayout);
      return l ? l.name : '';
    },
    currentLayoutInfo() {
      const l = this.layouts.find(x => x.id === this.currentLayout);
      return l ? `${l.width}×${l.height}` : '';
    },

    promptCreateLayout() {
      this.modal = {
        open: true, title: 'Create layout', type: 'layout',
        form: { name: '', width: 1920, height: 1080 },
        onSubmit: async () => {
          try {
            const j = await api('/api/layouts', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(this.modal.form) });
            this.modal.open = false;
            await this.loadLayouts();
            await this.openLayout(j.id);
            this.showToast('Layout created');
          } catch (e) { this.showToast(e.message, true); }
        },
      };
    },

    async deleteLayout(id) {
      if (!confirm('Delete this layout?')) return;
      await api(`/api/layouts/${id}`, { method: 'DELETE' });
      if (this.currentLayout === id) { this.currentLayout = null; this.layers = []; }
      await this.loadLayouts();
      this.showToast('Layout deleted');
    },

    async openLayout(id) {
      this.currentLayout = id;
      this.selectedLayer = null;
      if (!id) { this.layers = []; return; }
      this.layers = await api(`/api/layouts/${id}/layers`);
      this.$nextTick(() => this.refreshPreview());
    },

    async addWidget(type) {
      if (!this.currentLayout) { this.showToast('Select a layout first', true); return; }
      await api(`/api/layouts/${this.currentLayout}/layers`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ type }) });
      await this.openLayout(this.currentLayout);
    },

    async toggleLayerVisible(l) {
      l.visible = l.visible ? 0 : 1;
      await api(`/api/layers/${l.id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ visible: !!l.visible }) });
      this.refreshPreview();
    },

    async deleteLayer(id) {
      await api(`/api/layers/${id}`, { method: 'DELETE' });
      await this.openLayout(this.currentLayout);
    },

    startDrag(evt, layer, resize) {
      if (evt.button !== undefined && evt.button !== 0) return;
      evt.preventDefault();
      const canvas = this.$refs.canvas;
      const rect = canvas.getBoundingClientRect();
      const sx = evt.clientX, sy = evt.clientY;
      const ox = layer.x, oy = layer.y, ow = layer.w, oh = layer.h;
      const move = e => {
        const dx = (e.clientX - sx) / rect.width * 100;
        const dy = (e.clientY - sy) / rect.height * 100;
        if (resize) {
          layer.w = Math.max(5, Math.min(100 - layer.x, ow + dx));
          layer.h = Math.max(5, Math.min(100 - layer.y, oh + dy));
        } else {
          layer.x = Math.max(0, Math.min(100 - layer.w, ox + dx));
          layer.y = Math.max(0, Math.min(100 - layer.h, oy + dy));
        }
      };
      const up = async () => {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        await api(`/api/layers/${layer.id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ x: layer.x, y: layer.y, w: layer.w, h: layer.h }) });
        this.refreshPreview();
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    },

    refreshPreview() {
      const frame = this.$refs.previewFrame;
      if (!frame) return;
      if (!this.currentLayout) { frame.removeAttribute('src'); return; }
      const lay = this.layouts.find(x => x.id === this.currentLayout);
      if (!lay) return;
      const canvas = this.$refs.canvas;
      const rect = canvas.getBoundingClientRect();
      if (!rect.width) return;
      const scale = rect.width / lay.width;
      frame.width = lay.width;
      frame.height = lay.height;
      frame.style.width = lay.width + 'px';
      frame.style.height = lay.height + 'px';
      frame.style.transform = `scale(${scale})`;
      frame.src = `/layout/${this.currentLayout}/preview?_=${Date.now()}`;
    },

    promptCreateDisplay() {
      this.modal = {
        open: true, title: 'New display', type: 'display',
        form: { name: '' },
        onSubmit: async () => {
          try {
            await api('/api/displays', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(this.modal.form) });
            this.modal.open = false;
            await this.loadDisplays();
            this.showToast('Display created');
          } catch (e) { this.showToast(e.message, true); }
        },
      };
    },

    async assignDisplayLayout(d, layoutId) {
      await api(`/api/displays/${d.id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ layout_id: layoutId, test_mode: !layoutId }) });
      await this.loadDisplays();
      this.showToast('Display updated');
    },

    async deleteDisplay(id) {
      if (!confirm('Delete this display URL?')) return;
      await api(`/api/displays/${id}`, { method: 'DELETE' });
      await this.loadDisplays();
      this.showToast('Display deleted');
    },

    copyDisplayUrl(d) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(d.url).then(() => this.showToast('URL copied')).catch(() => this.showToast('Could not copy URL', true));
      }
    },
    openDisplayUrl(d) { window.open(d.url, '_blank'); },
  };
}

window.atCanvas = atCanvas;
