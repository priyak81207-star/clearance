"""EU RASFF Window - public notification search (unofficial JSON endpoint used by the website)."""
import json, hashlib, re, datetime as dt
from common import http, clean, is_india, since_date

URL = 'https://webgate.ec.europa.eu/rasff-window/backend/public/notification/search/consolidated/'
HEAD = {'Content-Type': 'application/json', 'Accept': 'application/json',
        'Origin': 'https://webgate.ec.europa.eu', 'Referer': 'https://webgate.ec.europa.eu/rasff-window/screen/search'}


def first(d, *names, default=''):
    for n in names:
        if isinstance(d, dict) and d.get(n) not in (None, ''):
            return d[n]
    return default


def to_date(v):
    if isinstance(v, (int, float)) and v > 1e9:
        return dt.datetime.utcfromtimestamp(v / 1000 if v > 1e11 else v).date().isoformat()
    s = str(v or '')
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s) or None
    if m: return m[0]
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s)
    return f'{m[3]}-{m[2]}-{m[1]}' if m else ''


def find_list(obj):
    """Locate the list of notification dicts in an unknown response shape."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and 'subject' in obj[0]:
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = find_list(v)
            if r is not None: return r
    return None


def risk_of(item):
    t = str(first(item, 'riskDecision', 'risk', 'riskDecisionDescription', default='')).lower()
    if 'not serious' in t: return 3
    if 'potentially' in t or 'potential' in t: return 2
    if 'serious' in t: return 1
    return 0


def to_record(it):
    subject = clean(first(it, 'subject', 'title'))
    origin = ' '.join(str(first(it, k)) for k in ('originCountry', 'origin', 'originCountries', 'countryOrigin'))
    if not (is_india(subject) or is_india(origin)):
        return None
    date = to_date(first(it, 'ecValidationDate', 'validationDate', 'notificationDate', 'date', 'ecValidDate'))
    if not date: return None
    nid = str(first(it, 'notifId', 'id', 'notificationId'))
    ref = str(first(it, 'reference', 'notificationReference'))
    haz = ' | '.join(str(first(h, 'hazard', 'name', default=h) if isinstance(h, dict) else h) for h in (first(it, 'hazards', default=[]) or []))
    return {'id': 'EU-' + (nid or hashlib.md5((subject + date).encode()).hexdigest()[:12]), 'mk': 'EU', 'date': date,
            'product': subject, 'pcat': str(first(it, 'productCategory', default='')), 'hazard': haz or subject,
            'risk': risk_of(it), 'ref': nid or ref, 'desc': clean(subject, 130)}


def fetch():
    since = since_date('eu')
    out, page = [], 1
    while page <= 200:
        body = {'parameters': {'pageNumber': page, 'itemsPerPage': 100, 'sortProperty': 'ecValidationDate', 'sortDirection': 'DESC'},
                'notificationReference': None, 'subjects': None, 'ecValidDateFrom': since.isoformat() + 'T00:00:00.000Z',
                'ecValidDateTo': None, 'notifyingCountry': None, 'originCountry': None, 'distributionCountry': None,
                'notificationType': None, 'notificationStatus': None, 'notificationClassification': None,
                'notificationBasis': None, 'actionTaken': None, 'hazardCategory': None, 'productCategory': None, 'riskDecision': None}
        resp = json.loads(http(URL, data=json.dumps(body).encode(), headers=HEAD, timeout=120))
        items = find_list(resp)
        if items is None:
            raise RuntimeError('RASFF response had an unexpected shape; top-level keys: ' + str(list(resp)[:8] if isinstance(resp, dict) else type(resp)))
        if not items:
            break
        for it in items:
            rec = to_record(it)
            if rec: out.append(rec)
        if len(items) < 100:
            break
        page += 1
    return out
