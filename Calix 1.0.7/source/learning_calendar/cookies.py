"""DPAPI snapshots, compatible with the v0.5 raw-cookie format."""
import base64
import json
from .secure_session import load_session, save_session

def campus_domain(domain):
    domain=str(domain).lstrip('.').lower()
    return domain=='bufs.ac.kr' or domain.endswith('.bufs.ac.kr')

def applies_to_canvas(domain):
    domain=str(domain).lstrip('.').lower()
    return domain in {'bufs.ac.kr','canvas.bufs.ac.kr'}

def canvas_session_available(rows):
    return any(applies_to_canvas(r.get('domain','')) and r.get('value') and
               'session' in r.get('name','').lower() for r in rows)

def cookie_record(cookie):
    from PySide6.QtNetwork import QNetworkCookie
    from PySide6.QtCore import QDateTime
    domain=cookie.domain().lstrip('.').lower()
    if not campus_domain(domain): return None
    if not cookie.isSessionCookie() and cookie.expirationDate()<QDateTime.currentDateTimeUtc(): return None
    return {'name':bytes(cookie.name()).decode('utf-8','replace'),
            'value':bytes(cookie.value()).decode('utf-8','replace'),
            'domain':cookie.domain(),'path':cookie.path() or '/', 'secure':cookie.isSecure(),
            'raw':base64.b64encode(bytes(cookie.toRawForm(QNetworkCookie.RawForm.Full))).decode('ascii')}

def read_cookies(path):
    from PySide6.QtNetwork import QNetworkCookie
    raw=load_session(path)
    if not raw: return []
    try:
        rows={}
        payload=json.loads(raw.decode('utf-8'))
        entries=payload.get('cookies',[]) if isinstance(payload,dict) else payload
        for encoded in entries:
            for cookie in QNetworkCookie.parseCookies(base64.b64decode(encoded)):
                rec=cookie_record(cookie)
                if rec: rows[(rec['domain'].lstrip('.'),rec['name'],rec['path'])]=rec
        return list(rows.values())
    except (ValueError,TypeError,KeyError): return []

def write_cookies(path, rows):
    save_session(path,json.dumps({'version':2,'cookies':[r['raw'] for r in rows]}).encode('utf-8'))
