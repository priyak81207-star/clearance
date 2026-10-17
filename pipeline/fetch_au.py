"""Australia DAFF - Imported Food Inspection Scheme monthly failing food reports (HTML tables)."""
import re, hashlib
from html.parser import HTMLParser
from common import http_text, parse_date, clean, is_india, since_date

INDEX = 'https://www.agriculture.gov.au/biosecurity-trade/import/goods/food/inspection-testing/failing-food-reports'
MON = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            h = dict(attrs).get('href') or ''
            if '/failing-food-reports/' in h:
                self.hrefs.append(h)


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables = []; self._t = None; self._r = None; self._c = None
    def handle_starttag(self, tag, attrs):
        if tag == 'table': self._t = []
        elif tag == 'tr' and self._t is not None: self._r = []
        elif tag in ('td', 'th') and self._r is not None: self._c = []
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._c is not None and self._r is not None:
            self._r.append(clean(''.join(self._c))); self._c = None
        elif tag == 'tr' and self._r is not None and self._t is not None:
            if self._r: self._t.append(self._r)
            self._r = None
        elif tag == 'table' and self._t is not None:
            self.tables.append(self._t); self._t = None
    def handle_data(self, d):
        if self._c is not None: self._c.append(d)


def slug_month(slug):
    m = re.search(r'([a-z]{3,9})[-_]?(20\d\d)\s*$', slug.lower().rstrip('/'))
    if not m or m[1][:3] not in MON:
        return None
    return int(m[2]), MON[m[1][:3]]


def parse_page(html):
    p = Tables(); p.feed(html)
    out = []
    for t in p.tables:
        if not t: continue
        head = [h.lower() for h in t[0]]
        def col(*keys):
            for i, h in enumerate(head):
                if any(k in h for k in keys): return i
            return None
        ci, cp, cc, cr, cres = col('date'), col('product'), col('country'), col('test', 'reason'), col('result')
        if cp is None or cc is None: continue
        for row in t[1:]:
            if len(row) <= max(x for x in (ci, cp, cc, cr or 0) if x is not None): continue
            if not is_india(row[cc]): continue
            date = parse_date(row[ci]) if ci is not None else ''
            if not date: continue
            product, reason = row[cp], (row[cr] if cr is not None else '')
            res = row[cres] if cres is not None and cres < len(row) else ''
            key = '|'.join([date, product, reason, res, ' '.join(row)])
            out.append({'id': 'AU-' + hashlib.md5(key.encode()).hexdigest()[:12], 'mk': 'AU', 'date': date,
                        'product': product, 'hazard': reason, 'risk': 0, 'ref': '',
                        'desc': clean(f'{product}. {reason}' + (f' ({res})' if res else ''), 130)})
    return out


def fetch():
    since = since_date('au')
    lk = Links(); lk.feed(http_text(INDEX))
    seen, recs, tried, ok = set(), [], 0, 0
    for h in lk.hrefs:
        url = h if h.startswith('http') else 'https://www.agriculture.gov.au' + h
        if url in seen: continue
        seen.add(url)
        ym = slug_month(url)
        if not ym or ym < (since.year, since.month): continue
        tried += 1
        try:
            recs += parse_page(http_text(url)); ok += 1
        except Exception as e:
            print('au: skip', url, e)
    if tried and not ok:
        raise RuntimeError('none of the %d monthly report pages could be read' % tried)
    if not lk.hrefs:
        raise RuntimeError('no monthly report links found on the DAFF index page (layout may have changed)')
    return recs
