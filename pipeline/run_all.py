"""Run every fetcher (each isolated), then rebuild the site data. Safe to run daily."""
import os, sys, traceback, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HEALTH, SITE_DATA, load_json, save_json, merge_source, load_source, today
import fetch_rasff, fetch_fda, fetch_uk, fetch_au, fetch_jp, fetch_news
import build

JOBS = [('eu', fetch_rasff), ('us', fetch_fda), ('uk', fetch_uk), ('au', fetch_au), ('jp', fetch_jp)]


def main():
    health = load_json(HEALTH, {})
    for name, mod in JOBS:
        h = health.get(name, {})
        try:
            recs = mod.fetch()
            if not recs and not load_source(name)['records']:
                raise RuntimeError('first run returned no India records; the source layout may have changed')
            total, added = merge_source(name, recs)
            h.update({'status': 'ok', 'last_ok': dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M'), 'fetched': len(recs), 'added': added, 'error': ''})
            print(f'{name}: ok, {len(recs)} fetched, {added} new, {total} stored')
        except getattr(mod, 'NoKey', ()) as e:
            h.update({'status': 'needs_key', 'error': str(e)})
            print(f'{name}: skipped ({e})')
        except Exception as e:  # keep previous data, record the problem
            h.update({'status': 'error', 'error': str(e)[:400]})
            print(f'{name}: FAILED {e}')
            traceback.print_exc()
        health[name] = h
    try:
        items, ok, total = fetch_news.fetch()
        save_json(SITE_DATA + '/news.json', {'updated': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), 'items': items})
        health['news'] = {'status': 'ok', 'last_ok': dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M'), 'feeds_ok': ok, 'feeds': total, 'items': len(items), 'error': ''}
        print(f'news: ok, {len(items)} items from {ok}/{total} feeds')
    except Exception as e:
        health['news'] = {**health.get('news', {}), 'status': 'error', 'error': str(e)[:400]}
        print('news: FAILED', e)
    save_json(HEALTH, health, indent=1)
    build.build()


if __name__ == '__main__':
    main()
