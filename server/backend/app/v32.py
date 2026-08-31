from fastapi.responses import HTMLResponse, Response
from . import v31

app = v31.app
BASE = v31.BASE
VERSION = '0.3.2'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION

# Replace admin + JS routes with a stable, single-owner display manager.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (
        (getattr(r, 'path', None) == '/' and 'GET' in getattr(r, 'methods', set()))
        or (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))
    )
]

@app.get('/', response_class=HTMLResponse)
def admin_v32():
    src = BASE.UI_FILE.read_text().replace('__VERSION__', VERSION)
    # Use the embedded logo from the known-good branding module and never show a broken image icon.
    logo_data = v31.v30.v24.v23.LOGO_DATA
    src = src.replace('/assets/atcanvas-logo.webp', logo_data)
    src = src.replace(
        '<div class="brand"><img src="'+logo_data+'" alt="AT Canvas"></div>',
        '<div class="brand"><img src="'+logo_data+'" alt="AT Canvas" onerror="this.remove();this.parentElement.innerHTML=\'<div style=&quot;font-size:26px;font-weight:900&quot;>AT <span style=&quot;color:#b100ff&quot;>Canvas</span></div>\'"></div>'
    )
    src = src.replace('<input id="pairRoom" placeholder="Room">', '<select id="pairSchedule"><option value="">No schedule</option></select>')
    return src

STABLE_PATCH = r'''

// ===== AT Canvas v0.3.2 stable admin controls =====
function toast(msg){let x=document.getElementById('atToast');if(!x){x=document.createElement('div');x.id='atToast';Object.assign(x.style,{position:'fixed',right:'22px',bottom:'22px',zIndex:9999,background:'#24112f',border:'1px solid #6d3b83',padding:'12px 16px',borderRadius:'10px',color:'white',boxShadow:'0 8px 30px #0008'});document.body.appendChild(x)}x.textContent=msg;x.style.display='block';clearTimeout(x._t);x._t=setTimeout(()=>x.style.display='none',2200)}
const orientationCycle={landscape:'portrait',portrait:'landscape_flipped',landscape_flipped:'portrait_flipped',portrait_flipped:'landscape'};
const orientationLabel={landscape:'Landscape 0°',portrait:'Portrait 90°',landscape_flipped:'Landscape 180°',portrait_flipped:'Portrait 270°'};
let displayRefreshBusy=false;

async function stableLoadDisplays(force=false){
  if(displayRefreshBusy)return;
  if(!force && document.activeElement && document.activeElement.matches('.display select')) return;
  displayRefreshBusy=true;
  try{
    const [ds,ls,ss,ms]=await Promise.all([api('/api/displays'),api('/api/layouts'),api('/api/schedules'),api('/api/media')]);
    $('#mDisplays').textContent=ds.length;$('#mOnline').textContent=ds.filter(x=>x.online).length;$('#mLayouts').textContent=ls.length;$('#mMedia').textContent=ms.length;
    for(const target of ['#dashDisplays','#displayManager']){
      const root=$(target);if(!root)continue;root.innerHTML='';
      if(!ds.length){root.innerHTML='<div class="empty">No displays paired yet.</div>';continue}
      ds.forEach(d=>{
        const row=document.createElement('div');row.className='display';row.dataset.displayId=d.id;
        const layoutOptions='<option value="">No layout</option>'+ls.map(l=>`<option value="${l.id}" ${Number(d.layout_id)===Number(l.id)?'selected':''}>${esc(l.name)}</option>`).join('');
        const scheduleOptions='<option value="">No schedule</option>'+ss.map(s=>`<option value="${s.id}" ${Number(d.schedule_id)===Number(s.id)?'selected':''}>${esc(s.name)}</option>`).join('');
        row.innerHTML=`<div style="min-width:210px;flex:1"><div><span class="dot ${d.online?'':'offline'}"></span><strong>${esc(d.name)}</strong></div><div class="muted" style="margin-top:4px">${esc(d.resolution||'unknown')} · ${esc(d.layout_name||d.current_layout||'No layout')} · Schedule: ${esc(d.schedule_name||'None')} · ${orientationLabel[d.orientation||'landscape']}</div><div class="muted" data-save-status style="margin-top:4px">${d.test_mode?'Output: Test Screen':'Output: Layout'}</div></div><div style="display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap;justify-content:flex-end"><label style="min-width:170px;font-size:12px;color:var(--muted)">Layout<select data-layout-select="${d.id}" style="margin-top:4px">${layoutOptions}</select></label><label style="min-width:170px;font-size:12px;color:var(--muted)">Schedule<select data-schedule-select="${d.id}" style="margin-top:4px">${scheduleOptions}</select></label><div class="actions"><button class="secondary" data-test="${d.id}">Test Screen</button><button class="secondary" data-open="${d.id}">Open Display</button><button class="secondary" data-cmd="identify" data-id="${d.id}">Identify</button><button class="secondary" data-cmd="reload" data-id="${d.id}">Reload</button><button class="secondary" data-cmd="screen_off" data-id="${d.id}">Screen Off</button><button class="secondary" data-cmd="screen_on" data-id="${d.id}">Screen On</button><button class="action" data-cmd="update" data-id="${d.id}">Update</button><button class="secondary" data-rotate="${d.id}">↻ Rotate 90°</button></div></div>`;
        root.appendChild(row);
        const status=row.querySelector('[data-save-status]');
        const layoutSel=row.querySelector('[data-layout-select]');
        layoutSel.onchange=async()=>{
          const val=layoutSel.value;if(!val){layoutSel.value=d.layout_id??'';toast('Choose a layout, or use Test Screen');return}
          layoutSel.disabled=true;status.textContent='Saving layout…';
          try{await api(`/api/displays/${d.id}/output`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({test_mode:false,layout_id:Number(val)})});status.textContent='Layout saved ✓';toast('Layout saved and sent');setTimeout(()=>stableLoadDisplays(true),700)}catch(e){status.textContent='Save failed: '+e.message;layoutSel.value=d.layout_id??''}finally{layoutSel.disabled=false}
        };
        const scheduleSel=row.querySelector('[data-schedule-select]');
        scheduleSel.onchange=async()=>{
          const val=scheduleSel.value;scheduleSel.disabled=true;status.textContent='Saving schedule…';
          try{await api(`/api/displays/${d.id}/schedule`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({schedule_id:val?Number(val):null})});status.textContent='Schedule saved ✓';toast('Schedule saved');setTimeout(()=>stableLoadDisplays(true),700)}catch(e){status.textContent='Save failed: '+e.message;scheduleSel.value=d.schedule_id??''}finally{scheduleSel.disabled=false}
        };
        row.querySelector('[data-test]').onclick=async()=>{status.textContent='Sending test screen…';await api(`/api/displays/${d.id}/output`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({test_mode:true,layout_id:null})});toast('Test screen sent');setTimeout(()=>stableLoadDisplays(true),600)};
        row.querySelector('[data-open]').onclick=()=>window.open(d.display_url,'_blank');
        row.querySelectorAll('[data-cmd]').forEach(b=>b.onclick=async()=>{const original=b.textContent;b.disabled=true;b.textContent='Sending…';try{await api(`/api/displays/${d.id}/command/${b.dataset.cmd}`,{method:'POST'});b.textContent='Queued ✓'}catch(e){b.textContent='Failed'}setTimeout(()=>{b.disabled=false;b.textContent=original},1600)});
        row.querySelector('[data-rotate]').onclick=async()=>{const next=orientationCycle[d.orientation||'landscape'];await api(`/api/displays/${d.id}/orientation`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({orientation:next})});toast('Rotation saved');stableLoadDisplays(true)};
      })
    }
    const pairSel=$('#pairSchedule');if(pairSel){const cur=pairSel.value;pairSel.innerHTML='<option value="">No schedule</option>'+ss.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');pairSel.value=cur}
  }finally{displayRefreshBusy=false}
}
loadDisplays=stableLoadDisplays;
$('#dashRefresh').onclick=()=>stableLoadDisplays(true);$('#displayRefresh').onclick=()=>stableLoadDisplays(true);

// Pairing: schedule is assigned immediately after the display is claimed.
$('#pairForm').onsubmit=async e=>{e.preventDefault();const m=$('#pairMsg');m.hidden=false;m.textContent='Pairing…';try{const claim=await api('/api/pair/claim',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({code:$('#pairCode').value,name:$('#pairName').value,room:null})});const sid=$('#pairSchedule')?.value;if(sid)await api(`/api/displays/${claim.display_id}/schedule`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({schedule_id:Number(sid)})});m.textContent='Display paired ✓';e.target.reset();stableLoadDisplays(true)}catch(x){m.textContent=x.message}};

// One guaranteed server renderer test button.
const dispTop=document.querySelector('#page-displays .top');if(dispTop&&!document.getElementById('serverTestButton')){const b=document.createElement('button');b.id='serverTestButton';b.className='action';b.textContent='Open Server Test Screen';b.onclick=()=>window.open('/display/test','_blank');dispTop.appendChild(b)}

// Layout rotation retained without timer-based UI mutation.
const rotateLayoutBtn=document.createElement('button');rotateLayoutBtn.className='secondary';rotateLayoutBtn.type='button';rotateLayoutBtn.textContent='↻ Rotate layout';rotateLayoutBtn.onclick=async()=>{if(!currentLayout)return alert('Select a layout first');await api(`/api/layouts/${currentLayout}/rotate`,{method:'POST'});loadLayouts()};$('#widgetBar').prepend(rotateLayoutBtn);
const originalOpenLayout=openLayout;openLayout=async function(id){await originalOpenLayout(id);const all=await api('/api/layouts'),l=all.find(x=>x.id===id);if(l){$('#canvas').style.aspectRatio=`${l.width}/${l.height}`;$('#layoutInfo').textContent=`${l.width}×${l.height} · ${l.width>=l.height?'Landscape':'Portrait'}`}};

// Selected-layer property editor.
function cfgOf(l){try{return JSON.parse(l.config||'{}')}catch{return {}}}
const layerCard=$('#layerList')?.parentElement;if(layerCard&&!$('#propertyEditor')){const box=document.createElement('div');box.id='propertyEditor';box.className='section';box.innerHTML='<div class="empty">Select a layer to edit it.</div>';layerCard.appendChild(box)}
function drawProps(){const e=$('#propertyEditor');if(!e)return;const l=layers.find(x=>x.id===selectedLayer);if(!l){e.innerHTML='<div class="empty">Select a layer to edit it.</div>';return}const c=cfgOf(l);e.innerHTML=`<h3>Properties</h3><div style="display:grid;gap:8px"><label>Name<input id="pName" value="${esc(l.name)}"></label>${['text','countdown'].includes(l.type)?`<label>Text<textarea id="pText">${esc(c.text||'')}</textarea></label>`:''}<div class="two"><label>Text colour<input id="pColor" type="color" value="${esc(c.color||'#ffffff')}"></label><label>Background<input id="pBg" type="color" value="${esc(c.background&&c.background.startsWith('#')?c.background:'#000000')}"></label></div><div class="two"><label>Font size<input id="pFont" type="number" min="8" max="240" value="${c.font_size||32}"></label><label>Opacity<input id="pOpacity" type="number" min="0.05" max="1" step="0.05" value="${l.opacity}"></label></div><div class="two"><label>X %<input id="pX" type="number" step="0.1" value="${l.x}"></label><label>Y %<input id="pY" type="number" step="0.1" value="${l.y}"></label><label>Width %<input id="pW" type="number" step="0.1" value="${l.w}"></label><label>Height %<input id="pH" type="number" step="0.1" value="${l.h}"></label></div><button class="action" id="pSave">Save changes</button></div>`;$('#pSave').onclick=async()=>{const nc={...c,color:$('#pColor').value,background:$('#pBg').value,font_size:+$('#pFont').value};if($('#pText'))nc.text=$('#pText').value;await api('/api/layers/'+l.id,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({name:$('#pName').value,x:+$('#pX').value,y:+$('#pY').value,w:+$('#pW').value,h:+$('#pH').value,opacity:+$('#pOpacity').value,config:nc})});toast('Layer saved');openLayout(currentLayout)}}
const originalRenderLayers=renderLayers;renderLayers=function(){originalRenderLayers();drawProps();const rev=[...layers].reverse();$$('#layerList .layer').forEach((el,i)=>{el.style.cursor='pointer';el.onclick=e=>{if(e.target.closest('button'))return;selectedLayer=rev[i]?.id;renderCanvas();renderLayers()}})};

// Start a single predictable refresh loop.
stableLoadDisplays(true);setInterval(()=>stableLoadDisplays(false),15000);
const oldGo=go;go=function(p){oldGo(p);if(p==='dashboard'||p==='displays')setTimeout(()=>stableLoadDisplays(true),50)};
'''

@app.get('/admin-v2.js')
def admin_v32_js():
    raw = BASE.JS_FILE.read_text()
    # Remove the legacy self-starting display refresh so only the stable manager owns the rows.
    raw = raw.replace("const h=location.hash.replace('#','');go(pages.includes(h)?h:'dashboard');loadDisplays();setInterval(loadDisplays,15000);", "const h=location.hash.replace('#','');go(pages.includes(h)?h:'dashboard');")
    return Response(raw + STABLE_PATCH, media_type='application/javascript')
