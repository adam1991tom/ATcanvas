import json
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException

from .. import db as dbmod

router = APIRouter()


def _http_json(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as exc:
        raise HTTPException(502, f'Weather service error: {exc}')


def _wx_text(code):
    try:
        c = int(code)
    except Exception:
        c = -1
    if c == 0: return 'Clear sky'
    if c in (1, 2): return 'Partly cloudy'
    if c == 3: return 'Overcast'
    if c in (45, 48): return 'Fog'
    if c in (51, 53, 55, 56, 57): return 'Drizzle'
    if c in (61, 63, 65, 66, 67): return 'Rain'
    if c in (71, 73, 75, 77): return 'Snow'
    if c in (80, 81, 82): return 'Rain showers'
    if c in (85, 86): return 'Snow showers'
    if c in (95, 96, 99): return 'Thunderstorm'
    return 'Weather'


def _wx_icon(code, is_day=True):
    try:
        c = int(code)
    except Exception:
        c = -1
    if c == 0: return '☀️' if is_day else '\U0001F319'
    if c in (1, 2): return '\U0001F324️' if is_day else '☁️'
    if c == 3: return '☁️'
    if c in (45, 48): return '\U0001F32B️'
    if c in (51, 53, 55, 56, 57): return '\U0001F326️'
    if c in (61, 63, 65, 66, 67, 80, 81, 82): return '\U0001F327️'
    if c in (71, 73, 75, 77, 85, 86): return '\U0001F328️'
    if c in (95, 96, 99): return '⛈️'
    return '\U0001F321️'


@router.get('/api/widget/weather/{layer_id}')
def weather_widget_data(layer_id: int):
    with dbmod.get_db() as c:
        row = c.execute('SELECT * FROM layers WHERE id=?', (layer_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Layer not found')
    if row['type'] != 'weather':
        raise HTTPException(400, 'Layer is not a weather widget')
    try:
        cfg = json.loads(row['config'] or '{}')
    except Exception:
        cfg = {}
    location = str(cfg.get('location') or '').strip()
    if not location:
        raise HTTPException(400, 'Set a location in this widget\'s settings')

    def _geocode(name):
        result = _http_json('https://geocoding-api.open-meteo.com/v1/search?' + urllib.parse.urlencode({
            'name': name, 'count': 1, 'language': 'en', 'format': 'json',
        }))
        return result.get('results') or []

    # Open-Meteo's geocoder only matches plain place names, not "City, Country" -
    # fall back to just the first comma-separated part so a natural "London, UK"
    # style entry still resolves instead of silently failing.
    hits = _geocode(location)
    if not hits and ',' in location:
        hits = _geocode(location.split(',')[0].strip())
    if not hits:
        raise HTTPException(404, 'Location not found')
    place = hits[0]
    fahrenheit = cfg.get('units') == 'f'
    params = {
        'latitude': place['latitude'], 'longitude': place['longitude'], 'timezone': 'auto',
        'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,is_day',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
        'forecast_days': 5,
    }
    if fahrenheit:
        params['temperature_unit'] = 'fahrenheit'
    wx = _http_json('https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(params))
    cur = wx.get('current') or {}
    daily = wx.get('daily') or {}
    days = []
    for i, d in enumerate(daily.get('time') or []):
        code = (daily.get('weather_code') or [None])[i] if i < len(daily.get('weather_code') or []) else None
        days.append({
            'date': d, 'icon': _wx_icon(code, True), 'condition': _wx_text(code),
            'max': (daily.get('temperature_2m_max') or [None])[i] if i < len(daily.get('temperature_2m_max') or []) else None,
            'min': (daily.get('temperature_2m_min') or [None])[i] if i < len(daily.get('temperature_2m_min') or []) else None,
        })
    return {
        'place': ', '.join(x for x in [place.get('name'), place.get('admin1'), place.get('country')] if x),
        'temp': cur.get('temperature_2m'), 'feels_like': cur.get('apparent_temperature'),
        'humidity': cur.get('relative_humidity_2m'), 'wind': cur.get('wind_speed_10m'),
        'icon': _wx_icon(cur.get('weather_code'), bool(cur.get('is_day', 1))),
        'condition': _wx_text(cur.get('weather_code')),
        'units': '°F' if fahrenheit else '°C',
        'days': days,
    }
