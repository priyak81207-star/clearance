"""UK Food Standards Agency - Border Notifications (monthly CSV, open data)."""
import csv, io, re, hashlib, datetime as dt
from common import http_text, load_json, parse_date, clean, is_india, since_date, today

CKAN = 'https://data.gov.uk/api/action/package_show?id=6d74a70f-e25a-4d54-a2a6-325c7aa57d74'
BASE = 'https://fsaopendata.blob.core.windows.net/opendatacatalog/'
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']


def month_of(name):
    n = name.lower()
    for i, m in enumerate(MONTHS):
        if m in n or m[:3] in n:
            y = re.search(r'(20\d\d)', n)
            if y:
                return int(y[1]), i + 1
    return None


def list_files():
    urls = []
    try:
        pkg = load_json_text(http_text(CKAN))
        for r in pkg['result']['resources']:
            u = r.get('url', '')
            if u.lower().endswith('.csv'):
                urls.append(u)
    except Exception:
        pass
    if not urls:                       # fall back to guessing recent month names
        d = today()
        for k in range(0, 5):
            y, m = d.year, d.month - k
            while m < 1:
                m += 12; y -= 1
            urls.append(f'{BASE}{MONTHS[m-1].capitalize()}-{y}.csv')
    return urls


def load_json_text(s):
    import json
    return json.loads(s)


def parse_csv(text):
    rd = csv.DictReader(io.StringIO(text))
    out = []
    for row in rd:
        row = {(k or '').strip(): (v or '').strip() for k, v in row.items()}
        if not is_india(row.get('Country')):
            continue
        date = parse_date(row.get('DateBNRaised'))
        if not date:
            continue
        product = clean(row.get('ProductName'))
        hazard = ' | '.join(x for x in (row.get('HazardCategory'), row.get('TypeOfFailure'), row.get('ReasonForFailure')) if x)
        key = '|'.join([date, product, row.get('Commodity', ''), row.get('NetWeight', ''), hazard])
        out.append({'id': 'UK-' + hashlib.md5(key.encode()).hexdigest()[:12], 'mk': 'UK', 'date': date,
                    'product': product, 'pcat': row.get('ProductCategory', ''), 'hazard': hazard, 'risk': 0, 'ref': '',
                    'desc': clean(f"{product}. {row.get('HazardCategory', '')}: {row.get('ReasonForFailure') or row.get('TypeOfFailure', '')}", 130)})
    return out


def fetch():
    since = since_date('uk')
    sy, sm = since.year, since.month
    recs, tried, ok = [], 0, 0
    for u in list_files():
        ym = month_of(u.rsplit('/', 1)[-1])
        if ym and ym < (sy, sm):
            continue
        tried += 1
        try:
            recs += parse_csv(http_text(u)); ok += 1
        except Exception as e:  # one bad month should not stop the rest
            print('uk: skip', u, e)
    if tried and not ok:
        raise RuntimeError('none of the %d monthly CSV files could be downloaded' % tried)
    return recs
