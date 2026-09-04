// AT Canvas calendar view options patch
(() => {
  const addViews = root => {
    const sel = (root || document).querySelector?.('#dvCalView');
    if (!sel || sel.dataset.atViewsEnhanced) return;
    sel.dataset.atViewsEnhanced = '1';
    const wanted = [
      ['month_grid','Month Grid / Tiles'],
      ['scroll_agenda','Scrolling Agenda']
    ];
    for (const [value,label] of wanted) {
      if (![...sel.options].some(o => o.value === value)) {
        const o=document.createElement('option'); o.value=value; o.textContent=label; sel.appendChild(o);
      }
    }
    const layer = typeof layers !== 'undefined' ? layers.find(x => x.id === selectedLayer) : null;
    if (layer) {
      try {
        const c=JSON.parse(layer.config||'{}');
        if (c.view && [...sel.options].some(o=>o.value===c.view)) sel.value=c.view;
      } catch {}
    }
  };
  const obs = new MutationObserver(ms => {
    for (const m of ms) for (const n of m.addedNodes) if (n.nodeType===1) addViews(n);
    addViews(document);
  });
  obs.observe(document.body,{childList:true,subtree:true});
  setTimeout(()=>addViews(document),100);
})();
