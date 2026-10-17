"""News watch: Google News RSS searches + optional extra feeds, tagged by product and market."""
import re, hashlib, urllib.parse, email.utils, datetime as dt
import xml.etree.ElementTree as ET
from common import http, clean, load_json, CONFIG, today, SITE_DATA, save_json
from categorize import categorize

QUERIES = [
    'India export rejection spices', 'Indian food consignments rejected RASFF', 'FDA import alert India food',
    'India food export ban suspended imports pesticide', 'Indian spices recall aflatoxin salmonella ethylene oxide',
    'Indian rice export consignments rejected', 'Indian shrimp seafood antibiotics import refusal',
    'Spices Board APEDA MPEDA export compliance alert', 'FSSAI export rejection', 'India mango export ban Japan US',
    'Indian tea coffee export MRL rejection', 'Indian honey export adulteration rejected',
    'India food exports rejected Japan China Australia Hong Kong UAE Saudi Bangladesh Nepal Singapore',
    'Indian basmati rice export Iran Saudi UAE ban', 'Indian groundnut sesame aflatoxin rejection',
]
MARKETS = [('EU', r'\bEU\b|Europe|RASFF|Brussels|Germany|Netherlands|France|Italy|Spain|Belgium'), ('US', r'\bUS\b|\bU\.S\.|America|\bFDA\b|United States'),
           ('UK', r'\bUK\b|Britain|British|\bFSA\b'), ('AU', r'Australia'), ('JP', r'Japan'), ('CN', r'China|Chinese'), ('HK', r'Hong Kong'),
           ('AE', r'\bUAE\b|Dubai|Abu Dhabi|Emirates'), ('SA', r'Saudi'), ('BD', r'Bangladesh'), ('NP', r'Nepal'), ('SG', r'Singapore'),
           ('CA', r'Canada|Canadian'), ('IR', r'\bIran'), ('OTHER', r'^$')]
SEVERE = re.compile(r'\bban(ned|s)?\b|suspend|reject|detain|recall|import alert|withdraw|halt|crackdown|adulterat|contaminat|warning|refus|revok|block|alert|seiz|destroy|returned', re.I)


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter('item'):
        g = lambda t: (it.find(t).text if it.find(t) is not None and it.find(t).text else '')
        src = it.find('source')
        items.append({'title': g('title'), 'link': g('link'), 'pub': g('pubDate'), 'source': (src.text if src is not None and src.text else '')})
    for it in root.iter('{http://www.w3.org/2005/Atom}entry'):
        ln = it.find('{http://www.w3.org/2005/Atom}link')
        t = it.find('{http://www.w3.org/2005/Atom}title'); u = it.find('{http://www.w3.org/2005/Atom}updated')
        items.append({'title': t.text if t is not None else '', 'link': ln.get('href') if ln is not None else '', 'pub': u.text if u is not None else '', 'source': ''})
    return items


def to_iso(s):
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except Exception:
        m = re.match(r'(\d{4}-\d{2}-\d{2})', s or '')
        return m[1] if m else ''


def tag(item, default_source=''):
    title = clean(re.sub(r'\s+-\s+[^-]+$', '', item['title']))
    src = item['source'] or (re.search(r'\s-\s([^-]+)$', item['title']) or [None, default_source])[1]
    cat = categorize(title)
    markets = [m for m, rx in MARKETS if m != 'OTHER' and re.search(rx, title, re.I)]
    return {'t': title, 'u': item['link'], 'd': to_iso(item['pub']), 's': clean(src), 'c': None if cat == 'food_other' else cat,
            'm': markets, 'a': 1 if SEVERE.search(title) else 0}


def fetch(max_age_days=120, keep=400):
    cur = load_json(SITE_DATA + '/news.json', {'items': []})['items']
    seen = {hashlib.md5(re.sub(r'\W+', '', i['t'].lower())[:80].encode()).hexdigest(): i for i in cur}
    errors = 0
    feeds = [('https://news.google.com/rss/search?q=' + urllib.parse.quote(q + ' when:60d') + '&hl=en-IN&gl=IN&ceid=IN:en', None) for q in QUERIES]
    for f in (load_json(CONFIG + '/feeds.json', []) or []):
        feeds.append((f['url'], re.compile(f.get('filter', 'india'), re.I)))
    for url, filt in feeds:
        try:
            for it in parse_feed(http(url, timeout=40, retries=2)):
                if not it['title'] or (filt and not filt.search(it['title'])):
                    continue
                n = tag(it)
                if not n['d']:
                    continue
                k = hashlib.md5(re.sub(r'\W+', '', n['t'].lower())[:80].encode()).hexdigest()
                seen.setdefault(k, n)
        except Exception as e:
            errors += 1
            print('news: feed failed', url[:80], e)
    if errors == len(feeds):
        raise RuntimeError('all news feeds failed')
    cutoff = (today() - dt.timedelta(days=max_age_days)).isoformat()
    items = sorted((i for i in seen.values() if i['d'] >= cutoff), key=lambda i: i['d'], reverse=True)[:keep]
    return items, len(feeds) - errors, len(feeds)
