"""EU RASFF Window - public notification search (the JSON endpoint the RASFF website itself uses).

Checked against the live site on 2026-10-17:
  * the address ends in /en/
  * dates are written dd-MM-yyyy HH:mm:ss (ISO dates give HTTP 400)
  * a search can not filter by origin country, so every notification in the window is read and the
    India ones are kept here
  * only border rejections are kept, to match the frozen dataset (318 India border rejections,
    29 Aug 2024 - 27 Aug 2026). Alerts and information notifications are not rejections.
"""
import json, hashlib, re, datetime as dt
from common import http, clean, since_date

URL = 'https://webgate.ec.europa.eu/rasff-window/backend/public/notification/search/consolidated/en/'
HEAD = {'Content-Type': 'application/json', 'Accept': 'application/json',
        'Origin': 'https://webgate.ec.europa.eu', 'Referer': 'https://webgate.ec.europa.eu/rasff-window/screen/search'}
PAGE = 100


def first(d, *names, default=''):
    for n in names:
        if isinstance(d, dict) and d.get(n) not in (None, ''):
            return d[n]
    return default


def desc(v):
    """RASFF sends many fields as {"id":..,"description":..}; return the text."""
    if isinstance(v, dict):
        return str(first(v, 'description', 'organizationName', 'name', default=''))
    return str(v or '')


def to_date(v):
    if isinstance(v, (int, float)) and v > 1e9:
        return dt.datetime.utcfromtimestamp(v / 1000 if v > 1e11 else v).date().isoformat()
    s = str(v or '')
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return m[0]
    m = re.match(r'(\d{2})[/-](\d{2})[/-](\d{4})', s)      # dd-mm-yyyy (the live format) or dd/mm/yyyy
    return f'{m[3]}-{m[2]}-{m[1]}' if m else ''


def find_list(obj):
    """Locate the list of notification dicts in the response."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and 'subject' in obj[0]:
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = find_list(v)
            if r is not None:
                return r
    return None


def risk_of(item):
    t = desc(first(item, 'riskDecision', 'risk', default='')).lower()
    if 'not serious' in t:
        return 3
    if 'potential' in t:
        return 2
    if 'serious' in t:
        return 1
    return 0


def from_india(it):
    origins = first(it, 'originCountries', default=[])
    if isinstance(origins, list) and origins:
        return any(isinstance(c, dict) and (c.get('isoCode') == 'IN' or desc(c).lower() == 'india') for c in origins)
    return False


def is_rejection(it):
    cls = desc(first(it, 'notificationClassification', default='')).lower()
    return 'border rejection' in cls


def to_record(it):
    if not from_india(it) or not is_rejection(it):
        return None
    subject = clean(first(it, 'subject', 'title'))
    date = to_date(first(it, 'ecValidationDate', 'validationDate', 'notificationDate', 'date'))
    if not date:
        return None
    nid = str(first(it, 'notifId', 'id', 'notificationId'))
    ref = str(first(it, 'reference', 'notificationReference'))
    return {'id': 'EU-' + (nid or hashlib.md5((subject + date).encode()).hexdigest()[:12]), 'mk': 'EU', 'date': date,
            'product': subject, 'pcat': desc(first(it, 'productCategory', default='')), 'hazard': subject,
            'risk': risk_of(it), 'ref': nid or ref, 'desc': clean(subject, 130)}


def body_for(page, since):
    return {'parameters': {'pageNumber': page, 'itemsPerPage': PAGE, 'sortProperty': 'ecValidationDate', 'sortDirection': 'DESC'},
            'notificationReference': None, 'subject': None,
            'ecValidDateFrom': since.strftime('%d-%m-%Y') + ' 00:00:00',
            'ecValidDateTo': None, 'notifyingCountry': None, 'originCountry': None, 'distributionCountry': None,
            'notificationType': None, 'notificationStatus': None, 'notificationClassification': None,
            'notificationBasis': None, 'actionTaken': None, 'hazardCategory': None, 'productCategory': None, 'riskDecision': None}


def fetch():
    since = since_date('eu')
    out, page, pages = [], 1, 1
    while page <= pages and page <= 250:
        resp = json.loads(http(URL, data=json.dumps(body_for(page, since)).encode(), headers=HEAD, timeout=120))
        items = find_list(resp)
        if items is None:
            if isinstance(resp, dict) and not resp.get('notifications'):
                break                                   # an empty window is a normal answer
            raise RuntimeError('RASFF response had an unexpected shape; top-level keys: ' + str(list(resp)[:8] if isinstance(resp, dict) else type(resp)))
        pages = int(resp.get('totalPages') or 1) if isinstance(resp, dict) else 1
        for it in items:
            rec = to_record(it)
            if rec:
                out.append(rec)
        page += 1
    return out
