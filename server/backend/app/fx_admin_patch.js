// AT Canvas seasonal/holiday event effects - adds an effect picker to each Events row.
(() => {
  const EFFECT_OPTIONS = [
    ['none', 'No effect'],
    ['snow', 'Snow'],
    ['rain', 'Rain'],
    ['halloween', 'Halloween'],
    ['confetti', 'Confetti'],
    ['hearts', 'Hearts'],
    ['stars', 'Stars'],
  ];

  async function enhanceEventEffects() {
    const list = document.getElementById('eventList');
    if (!list) return;
    const rows = [...list.querySelectorAll('.row')];
    if (!rows.length) return;
    if (!rows.some(r => !r.querySelector('[data-fx-select]'))) return;
    let events;
    try { events = await api('/api/events'); } catch (e) { return; }
    const byId = {};
    events.forEach(e => byId[e.id] = e);
    rows.forEach(r => {
      if (r.querySelector('[data-fx-select]')) return;
      const editBtn = r.querySelector('[data-event-edit]');
      if (!editBtn) return;
      const id = editBtn.dataset.eventEdit;
      const ev = byId[id];
      if (!ev) return;
      const actions = r.querySelector('.actions');
      if (!actions) return;
      const sel = document.createElement('select');
      sel.dataset.fxSelect = id;
      sel.title = 'Display effect while this event is active';
      sel.style.cssText = 'width:auto;padding:8px 10px';
      sel.innerHTML = EFFECT_OPTIONS.map(([v, label]) => `<option value="${v}" ${ev.effect === v ? 'selected' : ''}>${label}</option>`).join('');
      sel.onchange = async () => {
        try {
          await api(`/api/events/${id}/effect`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ effect: sel.value }) });
          toast('Effect saved');
        } catch (e) { toast(e.message, true); }
      };
      actions.insertBefore(sel, actions.firstChild);
    });
  }

  new MutationObserver(() => enhanceEventEffects()).observe(document.body, { childList: true, subtree: true });
  setTimeout(enhanceEventEffects, 250);
})();
