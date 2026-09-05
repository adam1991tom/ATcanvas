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
      { id: 'people', label: 'People' },
      { id: 'lists', label: 'Lists' },
      { id: 'settings', label: 'Settings' },
    ],
    page: 'dashboard',
    widgetTypes: ['clock', 'text', 'weather', 'calendar', 'list'],
    widgetFields: {
      clock: [
        { key: 'clock_format', label: 'Format', type: 'select', options: [['24', '24-hour'], ['12', '12-hour']] },
        { key: 'seconds', label: 'Show seconds', type: 'checkbox' },
        { key: 'show_date', label: 'Show date', type: 'checkbox' },
      ],
      text: [
        { key: 'text', label: 'Text', type: 'textarea' },
      ],
      weather: [
        { key: 'location', label: 'Location', type: 'text', placeholder: 'London, UK' },
        { key: 'units', label: 'Units', type: 'select', options: [['c', 'Celsius'], ['f', 'Fahrenheit']] },
      ],
      calendar: [
        { key: 'days', label: 'Days ahead', type: 'select', options: [['7', '1 week'], ['14', '2 weeks'], ['30', '1 month']] },
        { key: 'limit', label: 'Max events shown', type: 'select', options: [['8', '8'], ['12', '12'], ['20', '20']] },
      ],
      list: [
        { key: 'list_id', label: 'List', type: 'select', options: [] },
        { key: 'title', label: 'Title override', type: 'text', placeholder: 'Leave blank to use list name' },
        { key: 'show_done', label: 'Show completed items', type: 'checkbox' },
      ],
    },
    google: { configured: false, connected: false, calendars: [] },
    people: [],
    rewards: [],
    lists: [],
    currentList: null,
    listItems: [],
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
      window.addEventListener('message', e => {
        if (e.data === 'atcanvas-google-connected') this.loadGoogleStatus();
      });
      const hash = location.hash.replace('#', '');
      if (['layouts', 'displays', 'settings', 'people', 'lists'].includes(hash)) this.go(hash);
      this.$nextTick(() => {
        if (this.$refs.canvas) {
          // The canvas can still be zero-width on first paint (grid/aspect-ratio
          // layout not settled yet), which used to make refreshPreview() silently
          // bail out and never retry - the iframe kept no `src` forever. Watching
          // for real size changes makes this self-heal instead of failing once.
          new ResizeObserver(() => this.refreshPreview()).observe(this.$refs.canvas);
        }
      });
    },

    go(page) {
      this.page = page;
      location.hash = page === 'dashboard' ? '' : page;
      if (page === 'settings') this.loadGoogleStatus();
      if (page === 'people') { this.loadPeople(); this.loadRewards(); }
      if (page === 'lists') { this.loadLists(); this.loadPeople(); }
    },

    async loadGoogleStatus() {
      try {
        const s = await api('/api/google/status');
        this.google.configured = s.configured;
        this.google.connected = s.connected;
        this.google.redirectUri = s.redirect_uri;
        if (s.connected) await this.loadGoogleCalendars();
      } catch (e) {}
    },

    async loadGoogleCalendars() {
      try { this.google.calendars = await api('/api/google/calendars'); } catch (e) { this.google.calendars = []; }
    },

    promptGoogleConfig() {
      this.modal = {
        open: true, title: 'Google OAuth credentials', type: 'google-config',
        form: { client_id: '', client_secret: '', redirect_uri: this.google.redirectUri || (location.origin + '/api/google/oauth/callback') },
        onSubmit: async () => {
          try {
            await api('/api/google/config', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(this.modal.form) });
            this.modal.open = false;
            await this.loadGoogleStatus();
            this.showToast('Google credentials saved');
          } catch (e) { this.showToast(e.message, true); }
        },
      };
    },

    async connectGoogle() {
      try {
        const j = await api('/api/google/auth/start');
        window.open(j.url, 'atcanvas-google-connect', 'width=520,height=680');
      } catch (e) { this.showToast(e.message, true); }
    },

    async disconnectGoogle() {
      if (!confirm('Disconnect Google Calendar?')) return;
      await api('/api/google/disconnect', { method: 'POST' });
      await this.loadGoogleStatus();
      this.showToast('Disconnected');
    },

    async toggleGoogleCalendar(cal) {
      cal.selected = !cal.selected;
      const ids = this.google.calendars.filter(c => c.selected).map(c => c.id);
      await api('/api/google/calendars/selection', { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ calendar_ids: ids }) });
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

    async editWidget(l) {
      let fields = this.widgetFields[l.type];
      if (!fields) return;
      if (l.type === 'list') {
        let lists = [];
        try { lists = await api('/api/lists'); } catch (e) {}
        fields = fields.map(f => f.key === 'list_id' ? { ...f, options: lists.map(x => [String(x.id), x.name]) } : f);
      }
      let cfg = {};
      try { cfg = JSON.parse(l.config || '{}'); } catch (e) {}
      const form = {};
      fields.forEach(f => { form[f.key] = f.key in cfg ? cfg[f.key] : (f.type === 'checkbox' ? false : (f.type === 'select' ? (f.options[0] ? f.options[0][0] : '') : '')); });
      this.modal = {
        open: true, title: `Edit ${l.type}`, type: 'widget-settings', fields, form,
        onSubmit: async () => {
          try {
            await api(`/api/layers/${l.id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ config: { ...cfg, ...this.modal.form } }) });
            this.modal.open = false;
            await this.openLayout(this.currentLayout);
            this.showToast('Widget updated');
          } catch (e) { this.showToast(e.message, true); }
        },
      };
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
      frame.style.zIndex = '0';
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

    // ---------- People / rewards ----------
    async loadPeople() { this.people = await api('/api/people'); },
    async loadRewards() { this.rewards = await api('/api/rewards'); },

    promptCreatePerson() {
      this.modal = {
        open: true, title: 'Add person', type: 'person',
        form: { name: '', color: '#6aa7ff', avatar: '' },
        onSubmit: async () => {
          try {
            await api('/api/people', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(this.modal.form) });
            this.modal.open = false;
            await this.loadPeople();
            this.showToast('Person added');
          } catch (e) { this.showToast(e.message, true); }
        },
      };
    },
    async deletePerson(id) {
      if (!confirm('Remove this person?')) return;
      await api(`/api/people/${id}`, { method: 'DELETE' });
      await this.loadPeople();
    },

    promptCreateReward() {
      this.modal = {
        open: true, title: 'Add reward', type: 'reward',
        form: { name: '', point_cost: 10 },
        onSubmit: async () => {
          try {
            await api('/api/rewards', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(this.modal.form) });
            this.modal.open = false;
            await this.loadRewards();
            this.showToast('Reward added');
          } catch (e) { this.showToast(e.message, true); }
        },
      };
    },
    async deleteReward(id) {
      if (!confirm('Delete this reward?')) return;
      await api(`/api/rewards/${id}`, { method: 'DELETE' });
      await this.loadRewards();
    },
    async redeemReward(reward) {
      const personId = prompt('Redeem for which person? Enter their name:');
      if (!personId) return;
      const person = this.people.find(p => p.name.toLowerCase() === personId.toLowerCase());
      if (!person) { this.showToast('No person with that name', true); return; }
      try {
        await api(`/api/rewards/${reward.id}/redeem`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ person_id: person.id }) });
        await this.loadPeople();
        this.showToast(`Redeemed for ${person.name}`);
      } catch (e) { this.showToast(e.message, true); }
    },

    // ---------- Lists (chores / shopping / generic) ----------
    async loadLists() { this.lists = await api('/api/lists'); },

    promptCreateList() {
      this.modal = {
        open: true, title: 'New list', type: 'list-create',
        form: { name: '', type: 'chore' },
        onSubmit: async () => {
          try {
            const j = await api('/api/lists', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(this.modal.form) });
            this.modal.open = false;
            await this.loadLists();
            await this.openList(j.id);
            this.showToast('List created');
          } catch (e) { this.showToast(e.message, true); }
        },
      };
    },
    async deleteList(id) {
      if (!confirm('Delete this list and all its items?')) return;
      await api(`/api/lists/${id}`, { method: 'DELETE' });
      if (this.currentList === id) { this.currentList = null; this.listItems = []; }
      await this.loadLists();
    },
    async openList(id) {
      this.currentList = id;
      this.listItems = id ? await api(`/api/lists/${id}/items`) : [];
    },
    currentListObj() { return this.lists.find(l => l.id === this.currentList); },

    promptAddItem() {
      const isChore = this.currentListObj()?.type === 'chore';
      this.modal = {
        open: true, title: 'Add item', type: 'list-item',
        form: { text: '', assignee_id: '', points: 0 },
        isChore,
        onSubmit: async () => {
          try {
            const body = { text: this.modal.form.text, points: isChore ? +(this.modal.form.points || 0) : 0 };
            if (isChore && this.modal.form.assignee_id) body.assignee_id = +this.modal.form.assignee_id;
            await api(`/api/lists/${this.currentList}/items`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
            this.modal.open = false;
            await this.openList(this.currentList);
            this.showToast('Item added');
          } catch (e) { this.showToast(e.message, true); }
        },
      };
    },
    async toggleItem(item) {
      await api(`/api/list-items/${item.id}/toggle`, { method: 'POST' });
      await this.openList(this.currentList);
    },
    async deleteItem(id) {
      await api(`/api/list-items/${id}`, { method: 'DELETE' });
      await this.openList(this.currentList);
    },
  };
}

window.atCanvas = atCanvas;
