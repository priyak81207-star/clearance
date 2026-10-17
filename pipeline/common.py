"""Shared helpers for the Clearance data pipeline (standard library only)."""
import json, os, re, sys, time, urllib.request, urllib.error, datetime as dt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG = os.path.join(ROOT, 'config')
SRC = os.path.join(ROOT, 'data', 'src')
SITE_DATA = os.path.join(ROOT, 'site', 'data')
HEALTH = os.path.join(ROOT, 'data', 'health.json')
UA = 'Mozilla/5.0 (compatible; ClearanceBot/1.0; +https://github.com/)'
LOOKBACK_MONTHS = 26          # how far back a first run goes
OVERLAP_DAYS = 21             # re-read this many days on each update


def today():
    return dt.date.today()


def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, separators=(',', ':') if indent is None else None)
    os.replace(tmp, path)


def http(url, data=None, headers=None, timeout=60, retries=3):
    """GET (or POST when data is bytes) with retries. Returns bytes."""
    h = {'User-Agent': UA, 'Accept': '*/*'}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f'{url}: {last}')


def http_text(url, **kw):
    raw = http(url, **kw)
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def clean(s, n=None):
    s = re.sub(r'\s+', ' ', str(s or '')).strip()
    if n and len(s) > n:
        s = s[:n - 3].rstrip() + '...'
    return s


def parse_date(s):
    """Return ISO date string or '' for many common formats."""
    s = str(s or '').strip()
    if not s:
        return ''
    if isinstance(s, dt.date):
        return s.isoformat()
    m = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', s)
    if m:
        return f'{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}'
    m = re.match(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', s)   # dd/mm/yyyy (UK, AU)
    if m:
        return f'{int(m[3]):04d}-{int(m[2]):02d}-{int(m[1]):02d}'
    return ''


def load_source(name):
    return load_json(os.path.join(SRC, name + '.json'), {'source': name, 'fetched': '', 'records': []})


def merge_source(name, new_records, keep_months=40):
    """Merge new records into data/src/<name>.json by id; returns (total, added)."""
    cur = load_source(name)
    by = {r['id']: r for r in cur['records']}
    added = 0
    for r in new_records:
        if r['id'] not in by:
            added += 1
        by[r['id']] = r
    cutoff = (today() - dt.timedelta(days=keep_months * 30)).isoformat()
    recs = sorted((r for r in by.values() if r['date'] >= cutoff), key=lambda r: r['date'], reverse=True)
    save_json(os.path.join(SRC, name + '.json'), {'source': name, 'fetched': today().isoformat(), 'records': recs})
    return len(recs), added


def since_date(name):
    """Start date for the next fetch of a source (overlap window on later runs)."""
    cur = load_source(name)
    if cur['records']:
        newest = max(r['date'] for r in cur['records'])
        d = dt.date.fromisoformat(newest) - dt.timedelta(days=OVERLAP_DAYS)
        return max(d, today() - dt.timedelta(days=LOOKBACK_MONTHS * 31))
    return today() - dt.timedelta(days=LOOKBACK_MONTHS * 31)


def is_india(s):
    return bool(re.search(r'\bindia\b|インド|भारत', str(s or ''), re.I))
