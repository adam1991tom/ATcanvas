
// ===== AT Canvas v0.3.5 browser-only display endpoints =====
window.loadDisplays = async function(force=false){
  try{
    const [ds,ls,ss,media]=await Promise.all([api('/api/displays'),api('/api/layouts'),api('/api/schedules'),api('/api/media')]);
    $('#mDisplays').textContent=ds.length;
    $('#mOnline').textContent=ds.length;
    $('#mLayouts').textContent=ls.length;
    $('#mMedia').textContent=media.length;
    for(const target of ['#dashDisplays','#displayManager']){
      const root=$(target); if(!root) continue; root.innerHTML='';
      if(!ds.length){root.innerHTML='<div class="empty">No display URLs yet. Create one above, then open it fullscreen in any browser.</div>';continue}
      for(const d of ds){
        const row=document.createElement('div'); row.className='display';
        const lo='<option value="">No layout</option>'+ls.map(l=>`<option value="${l.id}" ${Number(d.layout_id)===Number(l.id)?'selected':''}>${esc(l.name)}</option>`).join('');
        const so='<option value="">No schedule</option>'+ss.map(s=>`<option value="${s.id}" ${Number(d.schedule_id)===Number(s.id)?'selected':''}>${esc(s.name)}</option>`).join('');
        row.innerHTML=`<div style="min-width:250px;flex:1"><div><span class="dot"></span><strong>${esc(d.name)}</strong></div><div class="muted" style="margin-top:5px">Browser display URL · ${esc(d.layout_name||d.current_layout||'No layout')}</div><div class="muted" style="word-break:break-all;margin-top:5px">${esc(d.display_url)}</div><div class="muted" data-state>${d.active_schedule?`Schedule active: ${esc(d.active_schedule.action)}`:'Ready to open in a browser'}</div></div><div style="display:flex;gap:8px;align-items:end;flex-wrap:wrap;justify-content:flex-end"><label class="muted">Layout<select data-layout>${lo}</select></label><label class="muted">Schedule<select data-schedule>${so}</select></label><div class="actions"><button class="action" data-save disabled>Save Changes</button><button class="secondary" data-open>Open Display</button><button class="secondary" data-copy>Copy URL</button><button class="secondary" data-test>Test Screen</button><button class="danger" data-delete>Delete</button></div></div>`;
        root.appendChild(row);
        const state=row.querySelector('[data-state]');
        const lsel=row.querySelector('[data-layout]');
        const ssel=row.querySelector('[data-schedule]');
        const save=row.querySelector('[data-save]');
        let dirty=false;
        const changed=()=>{dirty=true;save.disabled=false;save.textContent='Save Changes';state.textContent='Unsaved changes'};
        lsel.onchange=changed;
        ssel.onchange=changed;
        save.onclick=async()=>{
          if(!dirty)return;
          save.disabled=true; save.textContent='Saving…'; state.textContent='Saving changes…';
          try{
            if(lsel.value){await api(`/api/displays/${d.id}/output`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({test_mode:false,layout_id:+lsel.value})})}
            else{await api(`/api/displays/${d.id}/output`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({test_mode:true,layout_id:null})})}
            await api(`/api/displays/${d.id}/schedule`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({schedule_id:ssel.value?+ssel.value:null})});
            dirty=false; save.textContent='Saved ✓'; state.textContent='Changes saved ✓'; toast('Display changes saved');
            setTimeout(()=>loadDisplays(true),700);
          }catch(e){save.disabled=false;save.textContent='Save Changes';state.textContent='Save failed';toast(e.message,true)}
        };
        row.querySelector('[data-open]').onclick=()=>window.open(d.display_url,'_blank');
        row.querySelector('[data-copy]').onclick=async()=>{try{await navigator.clipboard.writeText(d.display_url);toast('Display URL copied')}catch{prompt('Copy this display URL:',d.display_url)}};
        row.querySelector('[data-test]').onclick=async()=>{await api(`/api/displays/${d.id}/output`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({test_mode:true,layout_id:null})});toast('Test screen enabled');loadDisplays(true)};
        row.querySelector('[data-delete]').onclick=async()=>{if(!confirm(`Delete display URL “${d.name}”?`))return;await api(`/api/display-endpoints/${d.id}`,{method:'DELETE'});toast('Display URL deleted');loadDisplays(true)};
      }
    }
    const ps=$('#pairSchedule'); if(ps){const cur=ps.value;ps.innerHTML='<option value="">No schedule</option>'+ss.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');ps.value=cur}
  }catch(e){toast('Display refresh failed: '+e.message,true)}
};

const pf=$('#pairForm');
if(pf) pf.onsubmit=async e=>{
  e.preventDefault(); const m=$('#pairMsg'); m.hidden=false; m.textContent='Creating URL…';
  try{
    const sid=$('#pairSchedule')?.value;
    const j=await api('/api/display-endpoints',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:$('#pairName').value,schedule_id:sid?+sid:null})});
    m.innerHTML=`Created ✓ <button type="button" class="secondary" id="newDisplayOpen">Open</button> <button type="button" class="secondary" id="newDisplayCopy">Copy URL</button><div class="muted" style="margin-top:7px;word-break:break-all">${esc(j.url)}</div>`;
    $('#newDisplayOpen').onclick=()=>window.open(j.url,'_blank');
    $('#newDisplayCopy').onclick=async()=>{try{await navigator.clipboard.writeText(j.url);toast('Display URL copied')}catch{prompt('Copy this display URL:',j.url)}};
    $('#pairName').value=''; await loadDisplays(true);
  }catch(err){m.textContent=err.message}
};

document.querySelectorAll('[data-cmd],[data-rotate]').forEach(x=>x.remove());
const dt=document.querySelector('#page-displays .top .muted'); if(dt) dt.textContent='Open these permanent URLs fullscreen on any browser-capable device.';
const up=document.querySelector('#page-updates .top .muted'); if(up) up.textContent='AT Canvas server release status.';

window.loadUpdateStatus = async function(){
  const e=$('#updateStatus'); e.textContent='Checking…';
  try{const j=await api('/api/updates/status');e.innerHTML=`<strong>Installed:</strong> v${esc(j.installed)}<br><strong>Server branch:</strong> ${esc(j.server?.commit||'unknown')} ${esc(j.server?.message||'')}<br><strong>Latest release:</strong> ${esc(j.release?.tag||'none')}`}
  catch(err){e.textContent=err.message}
};
// admin_v33.js bound #checkUpdates.onclick to its own (buggy, references x.screen) loadUpdateStatus
// before this file redefined window.loadUpdateStatus - rebind so the button uses the fixed version.
const cuBtn=document.getElementById('checkUpdates'); if(cuBtn) cuBtn.onclick=loadUpdateStatus;

setTimeout(()=>loadDisplays(true),50);
