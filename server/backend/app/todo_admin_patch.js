// AT Canvas To-Do / chores page
(() => {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];

  // ---------- Nav wiring ----------
  const nav = document.getElementById('nav');
  if (nav && !nav.querySelector('[data-page="todos"]')) {
    const btn = document.createElement('button');
    btn.dataset.page = 'todos';
    btn.textContent = 'To-Do';
    nav.appendChild(btn);
    btn.onclick = () => window.go('todos');
  }

  // Wrap the base go() so the To-Do page loads its data, same pattern as layouts/media/events do.
  const _go = window.go;
  window.go = function (p) {
    _go(p);
    if (p === 'todos') loadTodos();
  };

  // The base bundle already forced go('dashboard') on startup before this file ran
  // (since 'todos' isn't in its hardcoded pages list) - re-honor a #todos deep link.
  if (location.hash === '#todos') window.go('todos');

  // ---------- Widget bar "+ todo" button ----------
  const bar = document.getElementById('widgetBar');
  if (bar && !bar.querySelector('[data-widget="todo"]')) {
    const wbtn = document.createElement('button');
    wbtn.className = 'secondary';
    wbtn.dataset.widget = 'todo';
    wbtn.textContent = '+ todo';
    wbtn.onclick = async () => {
      if (!currentLayout) return alert('Select a layout first');
      await api(`/api/layouts/${currentLayout}/layers`, {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ type: 'todo' }),
      });
      openLayout(currentLayout);
    };
    bar.appendChild(wbtn);
  }

  // ---------- To-Do page ----------
  async function loadTodos() {
    const list = document.getElementById('todoList');
    if (!list) return;
    const all = await api('/api/todos');
    const showDone = document.getElementById('todoShowDone')?.checked;
    const items = showDone ? all : all.filter(t => !t.done);
    list.innerHTML = items.length ? '' : '<div class="empty">Nothing on the list.</div>';
    items.forEach(t => {
      const r = document.createElement('div');
      r.className = 'row';
      r.innerHTML = `<div style="display:flex;align-items:center;gap:10px">
        <input type="checkbox" data-todo-toggle="${t.id}" ${t.done ? 'checked' : ''} style="width:1.2em;height:1.2em">
        <div style="${t.done ? 'opacity:.5;text-decoration:line-through' : ''}"><strong>${esc(t.text)}</strong>${t.assignee ? `<div class="muted">${esc(t.assignee)}${t.points ? ' &middot; ' + t.points + ' pts' : ''}</div>` : ''}</div>
      </div><button class="danger" data-todo-del="${t.id}">Delete</button>`;
      list.appendChild(r);
    });
    list.querySelectorAll('[data-todo-toggle]').forEach(cb => cb.onchange = async () => {
      await api(`/api/todos/${cb.dataset.todoToggle}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ done: cb.checked }) });
      loadTodos();
    });
    list.querySelectorAll('[data-todo-del]').forEach(b => b.onclick = async () => {
      if (!confirm('Delete this item?')) return;
      await api(`/api/todos/${b.dataset.todoDel}`, { method: 'DELETE' });
      loadTodos();
    });
  }
  window.loadTodos = loadTodos;

  document.getElementById('newTodo')?.addEventListener('click', () => {
    modal('New to-do item',
      '<label>Item<input name="text" required placeholder="Take the bins out"></label>' +
      '<div class="two"><label>Assignee (optional)<input name="assignee"></label><label>Points (optional)<input name="points" type="number" value="0"></label></div>' +
      '<button class="action">Add</button>',
      async f => {
        await api('/api/todos', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text: f.get('text'), assignee: f.get('assignee') || '', points: +(f.get('points') || 0) }) });
        loadTodos();
      });
  });
  document.getElementById('todoShowDone')?.addEventListener('change', loadTodos);

  // ---------- Per-widget settings (title / show completed) on the layout designer ----------
  const cfgOf = l => { try { return JSON.parse(l?.config || '{}') } catch { return {} } };
  function enhanceTodoLayer() {
    const modalEl = document.getElementById('dv2Edit');
    if (!modalEl || modalEl.dataset.todoFx) return;
    const layer = (typeof layers !== 'undefined') ? layers.find(x => x.id === selectedLayer) : null;
    if (!layer || layer.type !== 'todo') return;
    modalEl.dataset.todoFx = '1';
    const c = cfgOf(layer);
    const pane = modalEl.querySelector('[data-pane="settings"]');
    if (!pane) return;
    const box = document.createElement('div');
    box.innerHTML = `<h3 style="margin-top:18px">To-Do widget</h3>
      <div class="dv2-grid"><label class="dv2-field"><span>Title</span><input id="todoTitle" value=""></label></div>
      <div class="dv2-checks" style="margin-top:14px"><label class="dv2-check"><input type="checkbox" id="todoShowDoneWidget"> Show completed items</label></div>`;
    pane.appendChild(box);
    document.getElementById('todoTitle').value = c.title || 'To-Do';
    document.getElementById('todoShowDoneWidget').checked = c.show_done !== false;
    const save = modalEl.querySelector('[data-save]');
    save?.addEventListener('click', () => {
      const merged = { ...c, title: document.getElementById('todoTitle')?.value || 'To-Do', show_done: !!document.getElementById('todoShowDoneWidget')?.checked };
      setTimeout(() => api(`/api/layers/${layer.id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ config: merged }) }).then(() => openLayout(currentLayout)).catch(() => {}), 350);
    }, true);
  }
  new MutationObserver(() => enhanceTodoLayer()).observe(document.body, { childList: true, subtree: true });
})();
