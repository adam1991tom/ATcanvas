// AT Canvas calendar month-grid options
(() => {
  function enhance(root=document){
    const modal=(root.querySelector?.('#dv2Edit') || document.querySelector('#dv2Edit'));
    const view=modal?.querySelector('#dvCalView');
    if(!modal||!view||modal.dataset.atGridOptions==='1') return;
    modal.dataset.atGridOptions='1';

    const settings=modal.querySelector('[data-pane="settings"]');
    if(!settings) return;
    const layer=(typeof layers!=='undefined')?layers.find(x=>x.id===selectedLayer):null;
    let c={}; try{c=JSON.parse(layer?.config||'{}')}catch{}

    const box=document.createElement('div');
    box.id='atMonthGridOptions';
    box.style.marginTop='14px';
    box.innerHTML=`
      <div style="font-weight:800;margin:0 0 9px">Month Grid options</div>
      <div class="dv2-grid">
        <label class="dv2-field"><span>Grid range</span>
          <select id="dvGridRange">
            <option value="four_weeks" ${(c.grid_range||'four_weeks')==='four_weeks'?'selected':''}>4-week rolling view</option>
            <option value="full_month" ${c.grid_range==='full_month'?'selected':''}>Full calendar month</option>
          </select>
        </label>
      </div>
      <div class="dv2-checks" style="margin-top:10px">
        <label class="dv2-check"><input type="checkbox" id="dvFutureOnly" ${c.future_only!==false?'checked':''}> Future events only</label>
        <label class="dv2-check"><input type="checkbox" id="dvHighlightToday" ${c.highlight_today!==false?'checked':''}> Highlight current day</label>
      </div>`;
    settings.appendChild(box);

    const updateVisibility=()=>{box.style.display=view.value==='month_grid'?'block':'none'};
    view.addEventListener('change',updateVisibility); updateVisibility();

    const save=modal.querySelector('[data-save]');
    if(save && !save.dataset.atGridSave){
      save.dataset.atGridSave='1';
      save.addEventListener('click',()=>{
        if(!layer || view.value!=='month_grid') return;
        const vals={
          grid_range: modal.querySelector('#dvGridRange')?.value || 'four_weeks',
          future_only: !!modal.querySelector('#dvFutureOnly')?.checked,
          highlight_today: !!modal.querySelector('#dvHighlightToday')?.checked,
        };
        // The main Designer v2 save runs first asynchronously. Apply these extra
        // calendar options just afterwards, merged with the config already in memory.
        setTimeout(async()=>{
          try{
            let latest={};
            try{latest=JSON.parse(layer.config||'{}')}catch{}
            latest={...latest,...vals,view:'month_grid'};
            await api(`/api/layers/${layer.id}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({config:latest})});
            if(typeof currentLayout!=='undefined'&&currentLayout) await openLayout(currentLayout);
          }catch(e){console.warn('AT Canvas month-grid options save failed',e)}
        },350);
      });
    }
  }
  const obs=new MutationObserver(()=>enhance(document));
  obs.observe(document.body,{childList:true,subtree:true});
  setTimeout(()=>enhance(document),150);
})();
