// ===== AT Canvas v0.4.0 Google Calendar =====
async function loadGoogleCalendar(){
  const status=$('#googleStatus'), list=$('#googleCalendarList'), preview=$('#googleEventPreview');
  if(!status) return;
  status.textContent='Checking Google connection…';
  try{
    const s=await api('/api/google/status');
    const cfg=s.configured?'Configured':'Not configured';
    const conn=s.connected?'Connected':'Not connected';
    status.innerHTML=`<strong>${cfg}</strong> · ${conn}<br><span class="muted">Redirect URI: ${esc(s.redirect_uri||'not set')}</span>`;
    const connect=$('#googleConnect'); if(connect){connect.disabled=!s.configured;connect.textContent=s.connected?'Reconnect Google':'Connect Google'}
    const disconnect=$('#googleDisconnect'); if(disconnect) disconnect.hidden=!s.connected;
    if(!s.connected){if(list)list.innerHTML='<div class="empty">Connect Google to choose calendars.</div>';if(preview)preview.innerHTML='<div class="empty">No Google events yet.</div>';return}
    const cals=await api('/api/google/calendars');
    if(list){
      list.innerHTML=cals.length?'':'<div class="empty">No calendars returned by Google.</div>';
      cals.forEach(c=>{const r=document.createElement('label');r.className='row';r.style.cursor='pointer';r.innerHTML=`<span><strong>${esc(c.summary)}</strong>${c.primary?' <span class="muted">· Primary</span>':''}<div class="muted">${esc(c.id)}</div></span><input type="checkbox" data-gcal-id="${esc(c.id)}" ${c.selected?'checked':''} style="width:auto">`;list.appendChild(r)});
      const save=$('#googleSaveCalendars'); if(save)save.hidden=false;
    }
    await loadGooglePreview();
  }catch(e){status.textContent='Google error: '+e.message;if(list)list.innerHTML='';if(preview)preview.innerHTML=''}
}

async function loadGooglePreview(){
  const p=$('#googleEventPreview'); if(!p)return;
  p.innerHTML='<div class="muted">Loading upcoming events…</div>';
  try{const j=await api('/api/google/events?days=14&limit=12');if(!j.events.length){p.innerHTML='<div class="empty">No upcoming events in the selected calendars.</div>';return}p.innerHTML=j.events.map(e=>{const when=e.all_day?new Date(e.start+'T00:00:00').toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'}):new Date(e.start).toLocaleString('en-GB',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});return `<div class="row"><div><strong>${esc(e.summary||'(No title)')}</strong><div class="muted">${esc(e.calendar_name||'Calendar')} · ${esc(when)}</div></div></div>`}).join('')}catch(e){p.innerHTML=`<div class="status">${esc(e.message)}</div>`}
}

const gsetup=$('#googleSetup');
if(gsetup) gsetup.onclick=async()=>{
  let s={};try{s=await api('/api/google/status')}catch{}
  modal('Google Calendar setup',`<label>Google Client ID<input name="client_id" value="${esc(s.client_id||'')}" required placeholder="...apps.googleusercontent.com"></label><label>Google Client Secret<input name="client_secret" type="password" placeholder="${s.has_secret?'Leave blank to keep current secret':'Client secret'}"></label><label>OAuth Redirect URI<input name="redirect_uri" value="${esc(s.redirect_uri||location.origin+'/api/google/oauth/callback')}" required></label><div class="status">Add this exact Redirect URI to the OAuth Web Application in Google Cloud Console.</div><button type="submit" class="action">Save Google settings</button>`,async f=>{await api('/api/google/config',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({client_id:f.get('client_id'),client_secret:f.get('client_secret'),redirect_uri:f.get('redirect_uri')})});toast('Google settings saved');await loadGoogleCalendar()})
};

const gconnect=$('#googleConnect');
if(gconnect) gconnect.onclick=async()=>{try{const j=await api('/api/google/auth/start');const w=window.open(j.url,'atcanvas-google','width=720,height=820');if(!w)location.href=j.url}catch(e){toast(e.message,true)}};
const gdisconnect=$('#googleDisconnect');
if(gdisconnect) gdisconnect.onclick=async()=>{if(!confirm('Disconnect Google Calendar from AT Canvas?'))return;await api('/api/google/disconnect',{method:'POST'});toast('Google disconnected');loadGoogleCalendar()};
const gsave=$('#googleSaveCalendars');
if(gsave) gsave.onclick=async()=>{const ids=$$('[data-gcal-id]:checked').map(x=>x.dataset.gcalId);await api('/api/google/calendars/selection',{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({calendar_ids:ids})});toast('Calendar selection saved');await loadGoogleCalendar()};
const grefresh=$('#googleRefreshEvents');if(grefresh)grefresh.onclick=()=>loadGooglePreview();
window.addEventListener('message',e=>{if(e.data==='atcanvas-google-connected'){toast('Google connected');loadGoogleCalendar()}});
const calNav=document.querySelector('[data-page="calendars"]');if(calNav)calNav.addEventListener('click',()=>setTimeout(loadGoogleCalendar,30));
if(location.hash==='#calendars')setTimeout(loadGoogleCalendar,80);
