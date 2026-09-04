// AT Canvas - live WYSIWYG preview in the layout designer canvas.
// Renders the real /layout/{id}/preview page (same render pipeline as the actual
// display) as a scaled background behind the existing draggable/resizable widget
// boxes, so the designer shows what will actually appear on screen.
(() => {
  const _renderCanvas = window.renderCanvas;
  window.renderCanvas = function () {
    _renderCanvas();
    refreshLivePreview();
  };

  async function refreshLivePreview() {
    const c = document.getElementById('canvas');
    if (!c) return;
    if (!currentLayout) {
      const old = c.querySelector('#atLivePreview');
      if (old) old.remove();
      return;
    }
    let lay;
    try {
      const all = await api('/api/layouts');
      lay = all.find(x => x.id === currentLayout);
    } catch (e) { return; }
    if (!lay) return;
    let frame = c.querySelector('#atLivePreview');
    if (!frame) {
      frame = document.createElement('iframe');
      frame.id = 'atLivePreview';
      frame.style.cssText = 'position:absolute;top:0;left:0;border:0;pointer-events:none;transform-origin:top left;z-index:-1';
      c.insertBefore(frame, c.firstChild);
    }
    const rect = c.getBoundingClientRect();
    if (!rect.width) return;
    const scale = rect.width / lay.width;
    frame.width = lay.width;
    frame.height = lay.height;
    frame.style.width = lay.width + 'px';
    frame.style.height = lay.height + 'px';
    frame.style.transform = `scale(${scale})`;
    frame.src = `/layout/${currentLayout}/preview?_=${Date.now()}`;
  }

  const style = document.createElement('style');
  style.textContent = `
    .widget{background:rgba(35,22,45,.22)!important}
    .widget.sel{background:rgba(35,22,45,.08)!important}
    .widget strong,.widget .muted{background:rgba(9,7,13,.55);padding:1px 5px;border-radius:5px;display:inline-block}
  `;
  document.head.appendChild(style);
})();
