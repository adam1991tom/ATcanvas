"""Display-page rendering. Widget types register themselves here with a plain
decorator instead of the old codebase's chain of modules each monkeypatching
the previous one's render function - adding a widget type later is just a new
@widget('name') function, nothing upstream needs to change."""
import html
import json

WIDGET_RENDERERS = {}


def widget(type_name):
    def deco(fn):
        WIDGET_RENDERERS[type_name] = fn
        return fn
    return deco


def layer_config(layer):
    try:
        return json.loads(layer['config'] or '{}')
    except Exception:
        return {}


def style_for(layer, config):
    color = config.get('color', '#ffffff')
    background = config.get('background', 'transparent')
    font = max(8, min(240, int(config.get('font_size', 32) or 32)))
    radius = max(0, min(100, int(config.get('radius', 0) or 0)))
    padding = max(0, min(100, int(config.get('padding', 12) or 12)))
    align = config.get('align', 'left')
    if align not in ('left', 'center', 'right'):
        align = 'left'
    return (
        f"left:{layer['x']}%;top:{layer['y']}%;width:{layer['w']}%;height:{layer['h']}%;"
        f"z-index:{layer['z']};opacity:{layer['opacity']};color:{color};background:{background};"
        f"font-size:{font}px;border-radius:{radius}px;padding:{padding}px;text-align:{align};"
    )


@widget('text')
def render_text(layer, config):
    content = html.escape(str(config.get('text', 'Double-click to edit this text')))
    return content, ''


@widget('clock')
def render_clock(layer, config):
    lid = layer['id']
    fmt12 = config.get('clock_format') == '12'
    seconds = bool(config.get('seconds'))
    show_date = bool(config.get('show_date'))
    content = f'<div class="at-clock" id="clock-{lid}"></div>'
    script = f"""(()=>{{const el=document.getElementById('clock-{lid}');function tick(){{
const d=new Date();
const opts={{hour:'2-digit',minute:'2-digit',hour12:{str(fmt12).lower()}}};
if({str(seconds).lower()})opts.second='2-digit';
const t=d.toLocaleTimeString('en-GB',opts);
const date={str(show_date).lower()}?'<div style="font-size:.45em;opacity:.75;margin-top:.2em">'+d.toLocaleDateString('en-GB',{{weekday:'long',day:'numeric',month:'long',year:'numeric'}})+'</div>':'';
el.innerHTML='<div>'+t+'</div>'+date}}tick();setInterval(tick,1000)}})();"""
    return content, script


def render_layer_html(layer):
    if not layer['visible']:
        return ''
    config = layer_config(layer)
    renderer = WIDGET_RENDERERS.get(layer['type'])
    if renderer:
        content, script = renderer(layer, config)
    else:
        content, script = html.escape(str(layer['name'])), ''
    wrapped = f'<div class="layer {html.escape(layer["type"])}" style="{style_for(layer, config)}">{content}</div>'
    if script:
        wrapped += f'<script>{script}</script>'
    return wrapped


def render_layout(layout, layers, templates):
    widgets_html = ''.join(render_layer_html(l) for l in layers)
    return templates.get_template('display_page.html').render(layout=layout, widgets_html=widgets_html)
