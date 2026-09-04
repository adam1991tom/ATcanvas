// AT Canvas Weather v2 settings
(() => {
  const q=s=>document.querySelector(s);
  const cfgOf=l=>{try{return JSON.parse(l?.config||'{}')}catch{return {}}};
  function enhance(){
    const modal=q('#dv2Edit'); if(!modal||modal.dataset.wx2) return;
    const layer=(typeof layers!=='undefined')?layers.find(x=>x.id===selectedLayer):null;
    if(!layer||layer.type!=='weather') return;
    modal.dataset.wx2='1'; const c=cfgOf(layer);
    const pane=modal.querySelector('[data-pane="settings"]'); if(!pane) return;
    const box=document.createElement('div'); box.innerHTML=`
      <h3 style="margin-top:18px">Weather layout</h3>
      <div class="dv2-grid">
        <label class="dv2-field"><span>Display style</span><select id="wx2Mode">
          <option value="full">Current + Forecast</option>
          <option value="strip">Compact forecast strip</option>
          <option value="current">Current conditions only</option>
        </select></label>
        <label class="dv2-field"><span>Temperature</span><select id="wx2Units"><option value="c">Celsius °C</option><option value="f">Fahrenheit °F</option></select></label>
        <label class="dv2-field"><span>Icon size</span><select id="wx2Icon"><option value="large">Large</option><option value="medium">Medium</option><option value="small">Small</option></select></label>
        <label class="dv2-field"><span>Show location</span><select id="wx2Location"><option value="yes">Show</option><option value="no">Hide</option></select></label>
      </div>
      <div class="dv2-checks" style="margin-top:14px">
        <label class="dv2-check"><input type="checkbox" id="wx2Feels"> Feels like</label>
        <label class="dv2-check"><input type="checkbox" id="wx2Chance"> Rain chance</label>
        <label class="dv2-check"><input type="checkbox" id="wx2HighLow"> Daily high / low</label>
        <label class="dv2-check"><input type="checkbox" id="wx2Condition"> Condition text</label>
      </div>`;
    pane.appendChild(box);
    q('#wx2Mode').value=c.weather_mode||'full'; q('#wx2Units').value=c.weather_units||'c'; q('#wx2Icon').value=c.icon_size||'large'; q('#wx2Location').value=c.show_weather_location===false?'no':'yes';
    q('#wx2Feels').checked=c.show_feels!==false; q('#wx2Chance').checked=c.show_rain_chance!==false; q('#wx2HighLow').checked=c.show_high_low!==false; q('#wx2Condition').checked=c.show_condition!==false;
    const save=modal.querySelector('[data-save]');
    save?.addEventListener('click',()=>{
      const merged={...c,
        weather_mode:q('#wx2Mode')?.value||'full', weather_units:q('#wx2Units')?.value||'c', icon_size:q('#wx2Icon')?.value||'large',
        show_weather_location:q('#wx2Location')?.value!=='no', show_feels:!!q('#wx2Feels')?.checked, show_rain_chance:!!q('#wx2Chance')?.checked,
        show_high_low:!!q('#wx2HighLow')?.checked, show_condition:!!q('#wx2Condition')?.checked,
        weather_source:q('#dvWeatherSource')?.value||c.weather_source||'openmeteo', location:q('#dvLocation')?.value||c.location||'',
        current:q('#dv_current')?.checked!==false, sun:q('#dv_sun')?.checked!==false, humidity:q('#dv_humidity')?.checked!==false,
        wind:q('#dv_wind')?.checked!==false, pressure:q('#dv_pressure')?.checked!==false, visibility:q('#dv_visibility')?.checked!==false,
        precip:q('#dv_precip')?.checked!==false, forecast:q('#dvForecast')?.value||c.forecast||'daily', forecast_days:+(q('#dvForecastDays')?.value||c.forecast_days||5),
        color:q('#dvColor')?.value||c.color||'#ffffff', background:q('#dvBg')?.value||c.background||'#000000', font_size:+(q('#dvFont')?.value||c.font_size||32),
        radius:+(q('#dvRadius')?.value||c.radius||0), padding:+(q('#dvPadding')?.value||c.padding||12), align:q('#dvAlign')?.value||c.align||'left'
      };
      setTimeout(()=>api(`/api/layers/${layer.id}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({config:merged})}).then(()=>openLayout(currentLayout)).catch(()=>{}),350);
    },true);
  }
  new MutationObserver(()=>enhance()).observe(document.body,{childList:true,subtree:true});
  setTimeout(enhance,200);
})();
