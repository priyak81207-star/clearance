"""Merge all source files into the JSON the website reads (site/data/*)."""
import os, re, json, shutil, datetime as dt
from common import (ROOT, CONFIG, SRC, SITE_DATA, HEALTH, load_json, save_json, load_source, today, clean)
from categorize import categorize, reasons_from

SOURCES = ['seed', 'eu', 'us', 'uk', 'au', 'jp']
MARKETS = [('EU', 'European Union', 'यूरोपीय संघ'), ('US', 'United States', 'अमेरिका'), ('UK', 'United Kingdom', 'यूनाइटेड किंगडम'),
           ('AU', 'Australia', 'ऑस्ट्रेलिया'), ('JP', 'Japan', 'जापान')]
WINDOW_MONTHS = 26


def build(verbose=True):
    cats = load_json(CONFIG + '/categories.json')
    reasons = load_json(CONFIG + '/reasons.json')
    rids = {r['id'] for r in reasons}
    seed = load_source('seed')['records']
    seed_cats = {r['cat'] for r in seed}
    seed_refs = {(r['mk'], r['ref']) for r in seed if r.get('ref')}
    seed_cut = {}
    for r in seed:
        seed_cut[r['mk']] = max(seed_cut.get(r['mk'], ''), r['date'])
    cutoff = (today() - dt.timedelta(days=WINDOW_MONTHS * 31)).isoformat()
    rows, seen, per_src = [], set(), {}
    for name in SOURCES:
        src = load_source(name)
        n_in = 0
        for r in src['records']:
            if r['date'] < cutoff or r['id'] in seen:
                continue
            cat = r.get('cat')
            if not cat:
                cat = categorize((r.get('product') or '') + ' ' + (r.get('pcat') or '') + ' ' + r.get('desc', ''))
                # seed already holds every record of the 15 original categories for EU/US up to its cut-off date
                if name != 'seed' and r['mk'] in seed_cut and r['date'] <= seed_cut[r['mk']] and cat in seed_cats:
                    continue
                if name != 'seed' and r.get('ref') and (r['mk'], r['ref']) in seed_refs:
                    continue
            rs = [x for x in r.get('reasons', []) if x in rids] or reasons_from(r.get('hazard'), r.get('desc'))
            seen.add(r['id'])
            rows.append([r['mk'], cat, rs, r['date'], r.get('risk', 0), clean(r.get('desc'), 130), r.get('ref', ''), clean(r.get('product'), 70) if r['mk'] == 'JP' else ''])
            n_in += 1
        per_src[name] = n_in
    rows.sort(key=lambda x: x[3], reverse=True)
    save_json(SITE_DATA + '/records.json', {'fields': ['mk', 'cat', 'reasons', 'date', 'risk', 'desc', 'ref', 'product'], 'rows': rows})

    # categories (config + trade + reliability)
    save_json(SITE_DATA + '/categories.json', {'groups': [], **{k: v for k, v in load_json(CONFIG + '/categories.json').items()}})
    for f, out in (('reasons.json', 'reasons.json'), ('limits.json', 'limits.json'), ('fda_alerts.json', 'fda_alerts.json'), ('events.json', 'events.json')):
        p = CONFIG + '/' + f
        if os.path.exists(p):
            shutil.copyfile(p, SITE_DATA + '/' + out)

    health = load_json(HEALTH, {})
    newest = {}
    for r in rows:
        newest[r[0]] = max(newest.get(r[0], ''), r[3])
    meta = {'generated': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), 'today': today().isoformat(), 'window_months': 24,
            'markets': [{'id': i, 'en': e, 'hi': h, 'newest': newest.get(i, ''), 'count': sum(1 for r in rows if r[0] == i),
                         'health': health.get(i.lower(), {})} for i, e, h in MARKETS],
            'news': health.get('news', {}), 'total': len(rows)}
    save_json(SITE_DATA + '/meta.json', meta)
    if verbose:
        print('built', len(rows), 'records', per_src)
    return rows, meta


if __name__ == '__main__':
    build()
