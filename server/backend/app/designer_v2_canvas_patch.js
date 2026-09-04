// AT Canvas Designer v2 - canvas/workspace pass
(() => {
  const q=s=>document.querySelector(s);
  const css=document.createElement('style');
  css.textContent=`
  #page-layouts .card:has(#canvas){overflow:visible}
  #dv2Workspace{height:clamp(430px,68vh,820px);min-height:430px;background:#09090c;border:1px solid #2b2630;border-radius:12px;overflow:auto;display:flex;align-items:center;justify-content:center;padding:32px;position:relative;box-shadow:inset 0 0 60px #0008}
  #dv2Workspace.dv2-pan{cursor:grab}#dv2Workspace.dv2-pan:active{cursor:grabbing}
  #canvas.dv2-canvas{flex:0 0 auto;width:auto;height:auto;max-width:none;max-height:none;margin:0;transform-origin:center center;box-shadow:0 14px 48px #000c;border:1px solid #77508c;border-radius:3px;transition:width .12s ease,height .12s ease}
  #canvas.dv2-grid{background-image:linear-gradient(rgba(255,255,255,.055) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.055) 1px,transparent 1px);background-size:5% 5%}
  #canvas .widget{border:1px solid rgba(194,106,255,.65);border-radius:3px;padding:8px;cursor:move}
  #canvas .widget.sel{outline:2px solid #c13cff;outline-offset:1px;box-shadow:0 0 0 1px #111,0 0 20px rgba(177,0,255,.35)}
  #canvas .widget.sel:before,#canvas .widget.sel:after{content:'';position:absolute;width:9px;height:9px;background:#fff;border:2px solid #b100ff;border-radius:2px;z-index:20;pointer-events:none}
  #canvas .widget.sel:before{left:-6px;top:-6px}#canvas .widget.sel:after{right:-6px;top:-6px}
  #canvas .resize{width:13px;height:13px;right:-6px;bottom:-6px;background:#fff;border:2px solid #b100ff;border-radius:2px;z-index:21;cursor:nwse-resize}
  #canvas .widget.sel .dv2-bl{position:absolute;width:9px;height:9px;left:-6px;bottom:-6px;background:#fff;border:2px solid #b100ff;border-radius:2px;z-index:20;pointer-events:none}
  .dv2-canvas-toolbar{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:0 0 12px;padding:9px 10px;background:#120e16;border:1px solid var(--border);border-radius:10px}.dv2-canvas-toolbar .grow{flex:1}.dv2-zoom{min-width:58px;text-align:center;color:#ddd;font-size:13px;font-weight:800}.dv2-toggle.on{border-color:#b100ff;color:#fff;background:#26152f}.dv2-resolution{color:var(--muted);font-size:12px;padding:0 5px}.dv2-help{color:var(--muted);font-size:12px}
  @media(max-width:900px){#dv2Workspace{height:58vh;padding:18px}.dv2-help{display:none}}
  `;document.head.appendChild(css);

  let zoomMode='fit', zoom=1, grid=true, snap=true;
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const round=(n,p=2)=>Number(Number(n).toFixed(p));

  function ensureWorkspace(){
    const canvas=q('#canvas'); if(!canvas) return null;
    let ws=q('#dv2Workspace');
    if(!ws){ws=document.createElement('div');ws.id='dv2Workspace';canvas.parentNode.insertBefore(ws,canvas);ws.appendChild(canvas)}
    canvas.classList.add('dv2-canvas');
    ensureToolbar();
    return ws;
  }

  function ensureToolbar(){
    if(q('#dv2CanvasToolbar')) return;
    const canvas=q('#canvas'); if(!canvas) return;
    const ws=q('#dv2Workspace'); if(!ws) return;
    const bar=document.createElement('div');bar.id='dv2CanvasToolbar';bar.className='dv2-canvas-toolbar';
    bar.innerHTML=`<button class="secondary" id="dv2ZoomOut">−</button><span class="dv2-zoom" id="dv2ZoomLabel">Fit</span><button class="secondary" id="dv2ZoomIn">＋</button><button class="secondary" id="dv2Fit">Fit</button><button class="secondary dv2-toggle on" id="dv2Grid">Grid</button><button class="secondary dv2-toggle on" id="dv2Snap">Snap</button><span class="dv2-resolution" id="dv2Resolution"></span><span class="grow"></span><span class="dv2-help">Drag to move · purple corner to resize</span>`;
    ws.parentNode.insertBefore(bar,ws);
    q('#dv2ZoomOut').onclick=()=>setManualZoom(zoom-.1);q('#dv2ZoomIn').onclick=()=>setManualZoom(zoom+.1);q('#dv2Fit').onclick=()=>{zoomMode='fit';fitCanvas()};
    q('#dv2Grid').onclick=()=>{grid=!grid;q('#dv2Grid').classList.toggle('on',grid);applyGrid()};
    q('#dv2Snap').onclick=()=>{snap=!snap;q('#dv2Snap').classList.toggle('on',snap);toast(snap?'Snap enabled':'Snap disabled')};
  }

  function baseFit(){
    const ws=q('#dv2Workspace'), l=typeof currentLayoutData!=='undefined'?currentLayoutData:null;if(!ws||!l)return 1;
    const availW=Math.max(200,ws.clientWidth-64),availH=Math.max(200,ws.clientHeight-64);
    return Math.min(availW/l.width,availH/l.height);
  }
  function setManualZoom(v){zoomMode='manual';zoom=clamp(v,.15,2);applyCanvasSize()}
  function fitCanvas(){zoom=baseFit();applyCanvasSize()}
  function applyCanvasSize(){
    const canvas=q('#canvas'),l=typeof currentLayoutData!=='undefined'?currentLayoutData:null;if(!canvas||!l)return;
    if(zoomMode==='fit')zoom=baseFit();
    canvas.style.width=Math.max(80,l.width*zoom)+'px';canvas.style.height=Math.max(80,l.height*zoom)+'px';canvas.style.aspectRatio='auto';
    q('#dv2ZoomLabel').textContent=zoomMode==='fit'?'Fit '+Math.round(zoom*100)+'%':Math.round(zoom*100)+'%';
    q('#dv2Resolution').textContent=`${l.width}×${l.height} · ${l.width>=l.height?'Landscape':'Portrait'}`;applyGrid();
  }
  function applyGrid(){const c=q('#canvas');if(c)c.classList.toggle('dv2-grid',grid)}

  function enhanceSelectedHandle(){const c=q('#canvas');if(!c)return;const sel=c.querySelector('.widget.sel');if(sel&&!sel.querySelector('.dv2-bl')){const h=document.createElement('span');h.className='dv2-bl';sel.appendChild(h)}}

  const originalOpen=typeof openLayout==='function'?openLayout:null;
  if(originalOpen){window.openLayout=async function(id){const r=await originalOpen(id);ensureWorkspace();requestAnimationFrame(()=>{applyCanvasSize();enhanceSelectedHandle()});return r};openLayout=window.openLayout}
  const originalRender=typeof renderCanvas==='function'?renderCanvas:null;
  if(originalRender){window.renderCanvas=function(){const r=originalRender();requestAnimationFrame(()=>{ensureWorkspace();applyCanvasSize();enhanceSelectedHandle()});return r};renderCanvas=window.renderCanvas}

  // Replace continuous free-float movement with optional clean snapping and rounded saved coordinates.
  window.dragLayer=function(e,l,w,resize){
    e.preventDefault();e.stopPropagation();w.setPointerCapture(e.pointerId);
    const box=q('#canvas').getBoundingClientRect(),sx=e.clientX,sy=e.clientY,ox=Number(l.x),oy=Number(l.y),ow=Number(l.w),oh=Number(l.h);
    const tidy=v=>snap?Math.round(v):round(v,2);
    w.onpointermove=v=>{
      const dx=(v.clientX-sx)/box.width*100,dy=(v.clientY-sy)/box.height*100;
      if(resize){l.w=clamp(tidy(ow+dx),3,100-l.x);l.h=clamp(tidy(oh+dy),3,100-l.y)}
      else{l.x=clamp(tidy(ox+dx),0,100-l.w);l.y=clamp(tidy(oy+dy),0,100-l.h)}
      Object.assign(w.style,{left:l.x+'%',top:l.y+'%',width:l.w+'%',height:l.h+'%'})
    };
    w.onpointerup=async()=>{
      w.onpointermove=null;w.onpointerup=null;l.x=round(l.x);l.y=round(l.y);l.w=round(l.w);l.h=round(l.h);
      await api(`/api/layers/${l.id}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({x:l.x,y:l.y,w:l.w,h:l.h})});
      toast(`Position saved · ${l.x}, ${l.y} · ${l.w}×${l.h}`);renderLayers();
    }
  };dragLayer=window.dragLayer;

  // Keyboard nudging for selected unlocked blocks.
  document.addEventListener('keydown',async e=>{
    if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)||!q('#page-layouts.active'))return;
    if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;
    const l=typeof layers!=='undefined'?layers.find(x=>x.id===selectedLayer):null;if(!l||l.locked)return;
    e.preventDefault();const step=e.shiftKey?5:1;if(e.key==='ArrowLeft')l.x=clamp(l.x-step,0,100-l.w);if(e.key==='ArrowRight')l.x=clamp(l.x+step,0,100-l.w);if(e.key==='ArrowUp')l.y=clamp(l.y-step,0,100-l.h);if(e.key==='ArrowDown')l.y=clamp(l.y+step,0,100-l.h);
    l.x=round(l.x);l.y=round(l.y);renderCanvas();await api(`/api/layers/${l.id}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({x:l.x,y:l.y})})
  });

  window.addEventListener('resize',()=>{if(zoomMode==='fit')requestAnimationFrame(fitCanvas)});
  setTimeout(()=>{ensureWorkspace();if(typeof currentLayoutData!=='undefined'&&currentLayoutData)fitCanvas()},150);
})();
