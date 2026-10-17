"""End-to-end: copy the project to a temp dir, fake every download, run the whole pipeline."""
import os, shutil, sys, json, tempfile, unittest, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


class E2E(unittest.TestCase):
    def test_full_run(self):
        tmp = tempfile.mkdtemp()
        proj = os.path.join(tmp, 'p')
        shutil.copytree(ROOT, proj, ignore=shutil.ignore_patterns('__pycache__', '.git'))
        sys.path.insert(0, os.path.join(proj, 'pipeline'))
        for m in [m for m in list(sys.modules) if m in ('common', 'build', 'run_all', 'categorize') or m.startswith('fetch_')]:
            del sys.modules[m]
        import common, run_all, fetch_rasff, fetch_fda, fetch_uk, fetch_au, fetch_jp, fetch_news
        seed = json.load(open(os.path.join(proj, 'data', 'src', 'seed.json')))['records']
        eu_seed = next(r for r in seed if r['mk'] == 'EU')
        d0 = (common.today() - dt.timedelta(days=5)).isoformat()
        d_old = '2025-03-01'
        rec = lambda mk, i, product, hazard, date=d0, ref='': {'id': f'{mk}-{i}', 'mk': mk, 'date': date, 'product': product, 'hazard': hazard, 'risk': 0, 'ref': ref, 'desc': product + '. ' + hazard}
        fetch_rasff.fetch = lambda: [rec('EU', 1, 'Chlorpyrifos in okra from India', 'chlorpyrifos'), rec('EU', 2, 'Salmonella in cumin from India', 'salmonella', d_old, eu_seed['ref'])]
        fetch_fda.fetch = lambda: [rec('US', 1, 'Okra frozen', 'PESTICIDE'), rec('US', 2, 'Cumin seed', 'FILTHY', d_old)]
        fetch_uk.fetch = lambda: [rec('UK', 1, 'Coriander Powder', 'Aflatoxin'), rec('UK', 2, 'Roasted Peanuts', 'Documentary checks')]
        fetch_au.fetch = lambda: [rec('AU', 1, 'Poha (flattened rice)', 'Arsenic (total)')]
        fetch_jp.fetch = lambda: [rec('JP', 1, 'ターメリック', '残留農薬基準違反')]
        fetch_news.fetch = lambda: ([{'t': 'FDA detains Indian cumin', 'u': 'http://x', 'd': d0, 's': 'X', 'c': 'cumin', 'm': ['US'], 'a': 1}], 15, 17)
        run_all.main()
        recs = json.load(open(os.path.join(proj, 'site', 'data', 'records.json')))['rows']
        by = lambda mk: [r for r in recs if r[0] == mk]
        self.assertEqual(len(by('EU')), 318 + 1)          # duplicate of a seed record and an old 'cumin' row are skipped
        self.assertEqual(len(by('US')), 1201 + 1)         # the old cumin row is covered by the seed
        self.assertEqual([r[1] for r in by('UK')].sort() or sorted(r[1] for r in by('UK')), ['coriander', 'groundnut'])
        self.assertEqual(by('AU')[0][1], 'rice'); self.assertEqual(by('JP')[0][1], 'turmeric')
        self.assertIn('veg', [r[1] for r in by('EU')])
        self.assertIn(['docs'], [r[2] for r in by('UK')])
        meta = json.load(open(os.path.join(proj, 'site', 'data', 'meta.json')))
        self.assertEqual({m['id']: m['health'].get('status') for m in meta['markets']}, {'EU': 'ok', 'US': 'ok', 'UK': 'ok', 'AU': 'ok', 'JP': 'ok'})
        self.assertEqual(json.load(open(os.path.join(proj, 'site', 'data', 'news.json')))['items'][0]['c'], 'cumin')
        # a failing source keeps old data and reports the error
        def boom(): raise RuntimeError('site changed')
        fetch_jp.fetch = boom
        run_all.main()
        meta = json.load(open(os.path.join(proj, 'site', 'data', 'meta.json')))
        jp = next(m for m in meta['markets'] if m['id'] == 'JP')
        self.assertEqual(jp['health']['status'], 'error'); self.assertEqual(jp['count'], 1)
        shutil.rmtree(tmp)


if __name__ == '__main__':
    unittest.main()
