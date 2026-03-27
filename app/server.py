#!/usr/bin/env python3
"""Arztsuche Outreach — Flask Backend"""

import os, json, time, random, base64, logging, requests
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timezone

import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
app = Flask(__name__, 
    static_folder=_os.path.join(_BASE, 'static'),
    template_folder=_os.path.join(_BASE, 'templates'))
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

PORT = int(os.environ.get('PORT', 5055))
CLAUDE_KEY = os.environ.get('CLAUDE_API_KEY', '')

# ── Fachgebiet Codes ──────────────────────────────────────────
FACH_CODES = {
    'Allgemeinmedizin': '01', 'Innere Medizin': '03', 'Urologie': '21',
    'Nephrologie': '09', 'Kardiologie': '07', 'Neurologie': '13',
    'Orthopädie': '20', 'Gynäkologie': '05', 'Pädiatrie': '04',
    'Psychiatrie': '12', 'Dermatologie': '17', 'Augenheilkunde': '14',
    'HNO': '18', 'Chirurgie': '02', 'Radiologie': '24',
    'Onkologie': '06', 'Gastroenterologie': '08', 'Pneumologie': '10',
    'Endokrinologie': '11', 'Rheumatologie': '19'
}

# ── Session Cache ─────────────────────────────────────────────
_session = {'cookies': None, 'ts': 0}

def get_116117_session():
    if _session['cookies'] and (time.time() - _session['ts']) < 1500:
        return _session['cookies']
    log.info('Acquiring 116117 session...')
    r = requests.get('https://arztsuche.116117.de/', headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'de-DE,de;q=0.9',
    }, timeout=15, allow_redirects=True)
    _session['cookies'] = r.cookies.get_dict()
    _session['ts'] = time.time()
    log.info(f'Session: {list(_session["cookies"].keys())}')
    return _session['cookies']

def make_req_val():
    ms = 3000000 + random.randint(0, 300000)
    return base64.b64encode(str(ms).encode()).decode()

# ── Geocoding Cache ───────────────────────────────────────────
_geo = {}

def geocode_plz(plz):
    if plz in _geo: return _geo[plz]
    try:
        r1 = requests.get(f'https://openplzapi.org/de/Localities?postalCode={plz}&page=1&pageSize=1',
            headers={'Accept': 'application/json'}, timeout=8)
        locs = r1.json()
        if not locs: return None
        city = locs[0].get('name', '')
        r2 = requests.get('https://nominatim.openstreetmap.org/search',
            params={'q': f'{plz} {city} Deutschland', 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'ArztsucheHA/1.0'}, timeout=8)
        geo = r2.json()
        if not geo: return None
        _geo[plz] = {'lat': float(geo[0]['lat']), 'lon': float(geo[0]['lon']), 'city': city}
        return _geo[plz]
    except Exception as e:
        log.error(f'Geocoding {plz}: {e}')
        return None

def search_116117(lat, lon, fgg):
    cookies = get_116117_session()
    payload = {'r': 900, 'locType': 'LATLON', 'lat': lat, 'lon': lon, 'plz': None,
        'osmId': None, 'osmType': None, 'locOrigin': 'BROWSER_AUTO',
        'searchTrigger': 'INITIAL', 'viaDeeplink': False,
        'filterSelections': [{'title': 'Fachgebiet Kategorie', 'fieldName': 'fgg', 'selectedCodes': [fgg]}]}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'de-DE,de;q=0.9',
        'Authorization': 'Basic YmRwczpma3I0OTNtdmdfZg==',
        'req-val': make_req_val(),
        'Origin': 'https://arztsuche.116117.de',
        'Referer': 'https://arztsuche.116117.de/',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin',
    }
    resp = requests.post('https://arztsuche.116117.de/api/data',
        json=payload, headers=headers, cookies=cookies, timeout=20)
    if resp.status_code == 500:
        _session['cookies'] = None
        cookies = get_116117_session()
        headers['req-val'] = make_req_val()
        resp = requests.post('https://arztsuche.116117.de/api/data',
            json=payload, headers=headers, cookies=cookies, timeout=20)
    resp.raise_for_status()
    return resp.json().get('arztPraxisDatas', [])

def get_neighboring_plzs(plz):
    try:
        r = requests.get(f'https://openplzapi.org/de/Localities?postalCode={plz}&page=1&pageSize=1',
            headers={'Accept': 'application/json'}, timeout=8)
        locs = r.json()
        if not locs: raise Exception('No locality')
        loc = locs[0]
        result = []
        dk = loc.get('district', {}).get('key', '') if loc.get('district') else ''
        if dk:
            r2 = requests.get(f'https://openplzapi.org/de/Districts/{dk}/Localities?page=1&pageSize=50',
                headers={'Accept': 'application/json'}, timeout=8)
            result = [l['postalCode'] for l in r2.json() if l.get('postalCode') and l['postalCode'] != plz]
        prefix = plz[:3]
        r3 = requests.get(f'https://openplzapi.org/de/Localities?postalCode=^{prefix}&page=1&pageSize=50',
            headers={'Accept': 'application/json'}, timeout=8)
        result += [l['postalCode'] for l in r3.json() if l.get('postalCode') and l['postalCode'] != plz]
        seen = set(); out = []
        for p in result:
            if p not in seen: seen.add(p); out.append(p)
        return out[:12]
    except Exception as e:
        log.error(f'PLZ neighbors error: {e}')
        base = int(plz)
        return [str(base+i).zfill(5) for i in range(-7,8) if i != 0][:12]

def parse_doctor(item, fachbereich):
    parts = [x for x in [item.get('titel',''), item.get('vorname',''), item.get('name','')] if x]
    fach = fachbereich
    if item.get('fg'): fach = item['fg'][0].get('value', fachbereich)
    strasse = ' '.join(filter(None, [item.get('strasse',''), item.get('hausnummer','')]))
    hours = ''
    try:
        tsz = item.get('tsz', [])
        if tsz and tsz[0].get('typTsz'):
            slots = [s['z'] for t in tsz[0]['typTsz'] for s in t.get('sprechzeiten', [])]
            if slots: hours = 'Heute: ' + ', '.join(slots)
    except: pass
    return {
        'name': ' '.join(parts).strip(),
        'fachbereich': fach,
        'address': strasse,
        'plz': item.get('plz', ''),
        'city': item.get('ort', ''),
        'phone': item.get('tel', ''),
        'email': item.get('email', ''),
        'website': item.get('web', ''),
        'geoeffnet': item.get('geoeffnet', ''),
        'hours': hours,
        'source': '116117'
    }

# ── Gmail OAuth ───────────────────────────────────────────────
def get_gmail_token(client_id, client_secret, refresh_token):
    r = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': client_id, 'client_secret': client_secret,
        'refresh_token': refresh_token, 'grant_type': 'refresh_token'
    })
    return r.json().get('access_token')

def send_gmail(access_token, to, subject, body, sender_name, sender_email):
    import email.mime.text, email.mime.multipart
    msg = email.mime.multipart.MIMEMultipart()
    msg['To'] = to
    msg['Subject'] = subject
    msg['From'] = f'{sender_name} <{sender_email}>'
    msg.attach(email.mime.text.MIMEText(body, 'plain', 'utf-8'))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = requests.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        json={'raw': raw})
    return r.status_code == 200

def get_gmail_profile(access_token):
    r = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/profile',
        headers={'Authorization': f'Bearer {access_token}'})
    return r.json().get('emailAddress', '')

# ── Google Calendar ───────────────────────────────────────────
def create_gcal_event(access_token, name, phone, fach, addr, dt_iso):
    start = datetime.fromisoformat(dt_iso)
    end_dt = start.replace(minute=start.minute + 15) if start.minute <= 44 else start.replace(hour=start.hour+1, minute=start.minute-45)
    event = {
        'summary': f'📞 Anruf: {name}',
        'description': f'📞 {phone}\n🏥 {fach}\n📍 {addr}',
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Europe/Berlin'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Europe/Berlin'},
    }
    r = requests.post('https://www.googleapis.com/calendar/v3/calendars/primary/events',
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        json=event)
    return r.json()

# ── Claude API ────────────────────────────────────────────────
def claude_generate(doctor, prompt, api_key):
    key = api_key or CLAUDE_KEY
    if not key: raise Exception('Kein Claude API Key')
    r = requests.post('https://api.anthropic.com/v1/messages',
        headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'},
        json={'model': 'claude-sonnet-4-20250514', 'max_tokens': 1000,
            'system': 'Du bist ein professioneller medizinischer Vertriebsassistent. Schreibe präzise, freundliche Outreach-E-Mails auf Deutsch. Gib NUR den E-Mail-Text zurück.',
            'messages': [{'role': 'user', 'content': prompt + '\n\n--- Arztdaten ---\n' + json.dumps(doctor, ensure_ascii=False, indent=2)}]},
        timeout=30)
    data = r.json()
    if data.get('error'): raise Exception(data['error']['message'])
    return data['content'][0]['text']

# ── Routes ────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(_os.path.join(_BASE, 'templates'), 'index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.json or {}
    plz = data.get('plz', '').strip()
    fachbereich = data.get('fachbereich', '')
    if not plz or not fachbereich:
        return jsonify({'error': 'PLZ und Fachbereich erforderlich'}), 400
    fgg = FACH_CODES.get(fachbereich, '01')
    plz_list = get_neighboring_plzs(plz)
    plz_list.insert(0, plz)
    plz_list = list(dict.fromkeys(plz_list))[:15]
    log.info(f'Searching {len(plz_list)} PLZs for {fachbereich} (fgg={fgg})')
    all_docs = []; seen = set()
    for p in plz_list:
        coords = geocode_plz(p)
        if not coords: continue
        try:
            items = search_116117(coords['lat'], coords['lon'], fgg)
            for item in items:
                doc = parse_doctor(item, fachbereich)
                key = (doc['name'] + doc['plz'] + doc['phone']).lower().replace(' ','')
                if key not in seen:
                    seen.add(key); all_docs.append(doc)
            time.sleep(0.3)
        except Exception as e:
            log.error(f'PLZ {p}: {e}')
    return jsonify({'doctors': all_docs, 'count': len(all_docs)})

@app.route('/api/claude', methods=['POST'])
def api_claude():
    data = request.json or {}
    try:
        text = claude_generate(data.get('doctor', {}), data.get('prompt', ''), data.get('apiKey', ''))
        return jsonify({'text': text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gmail/send', methods=['POST'])
def api_gmail_send():
    data = request.json or {}
    try:
        token = get_gmail_token(data['clientId'], data['clientSecret'], data['refreshToken'])
        sender_email = get_gmail_profile(token)
        results = []
        for job in data.get('jobs', []):
            ok = send_gmail(token, job['email'], job['subject'], job['body'],
                data.get('senderName', ''), sender_email)
            results.append({'email': job['email'], 'name': job['name'], 'success': ok})
            time.sleep(0.3)
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gmail/profile', methods=['POST'])
def api_gmail_profile():
    data = request.json or {}
    try:
        token = get_gmail_token(data['clientId'], data['clientSecret'], data['refreshToken'])
        email = get_gmail_profile(token)
        return jsonify({'email': email})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/create', methods=['POST'])
def api_calendar():
    data = request.json or {}
    try:
        token = get_gmail_token(data['clientId'], data['clientSecret'], data['refreshToken'])
        results = []
        for job in data.get('jobs', []):
            ev = create_gcal_event(token, job['name'], job.get('phone',''),
                job.get('fachbereich',''), job.get('address',''), job['dateTime'])
            results.append({'name': job['name'], 'success': 'id' in ev,
                'eventId': ev.get('id',''), 'error': ev.get('error',{}).get('message','')})
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fachbereiche')
def api_fachbereiche():
    return jsonify(list(FACH_CODES.keys()))

if __name__ == '__main__':
    log.info(f'Starting on port {PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=False)
