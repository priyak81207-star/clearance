"""Offline tests: each parser is run on a small sample shaped like the real source."""
import io, os, sys, unittest, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import fetch_uk, fetch_au, fetch_jp, fetch_fda, fetch_rasff, fetch_news
from categorize import categorize, reasons_from

UK_CSV = """DateBNRaised,Country,Commodity,NetWeight,ProductCategory,ProductName,ControlledByLegislationYOrN,TypeOfConsignment,HazardCategory,TypeOfFailure,ReasonForFailure
01/04/2026,Trinidad and Tobago,,1196 kg,Prepared dishes and snacks,Cheese Regular,No,POAO,Chemical contamination,Food additives,Physical
01/04/2026,India,12024200,4017.16 kg,Other food product / mixed,Roasted Peanuts,Yes,FNAO,Documentary checks  ,Documentary checks,Documentary
01/04/2026,India,09092100,500 kg,Herbs and spices,Coriander Powder,Yes,FNAO,Mycotoxins,Aflatoxin,Aflatoxin B1 above limit
"""
AU_HTML = """<table><tr><th>Date of fail</th><th>Product description</th><th>Country of origin</th><th>Producer name</th><th>Test applied / reason for fail</th><th>Results / Units</th></tr>
<tr><td>3/10/2025</td><td>Poha (flattened rice)</td><td>India</td><td>X Ltd</td><td>Arsenic (total)</td><td>21 mg/kg</td></tr>
<tr><td>3/10/2025</td><td>Fresh lychee</td><td>China</td><td>Y</td><td>Cypermethrin</td><td>0.1</td></tr></table>"""
RASFF = {"notifications": [
    {"notifId": 869134, "reference": "2026.1", "subject": "Ethylene oxide in sesame seeds from India", "ecValidationDate": "2026-09-02T10:00:00", "riskDecision": "serious", "hazards": [{"hazard": "ethylene oxide"}]},
    {"notifId": 869135, "reference": "2026.2", "subject": "Salmonella in tahini from Lebanon", "ecValidationDate": "2026-09-02T10:00:00"}], "totalNotifications": 2}
FDA_ROW = {"IndustryCode": 28, "RefusalDate": "2026-09-03", "ProductCodeDescription": "Cumin seed, whole", "RefusalCharges": "FILTHY, SALMONELLA", "ShipmentID": "ABC-123-4", "FEINumber": 1}
RSS = b"""<rss><channel><item><title>FDA detains Indian cumin over salmonella - Reuters</title><link>http://x/1</link><pubDate>Mon, 05 Oct 2026 08:00:00 GMT</pubDate><source>Reuters</source></item></channel></rss>"""


class T(unittest.TestCase):
    def test_uk(self):
        r = fetch_uk.parse_csv(UK_CSV)
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0]['date'], '2026-04-01')
        self.assertEqual(categorize(r[1]['product']), 'coriander')
        self.assertIn('mycotoxin', reasons_from(r[1]['hazard']))
        self.assertEqual(reasons_from(r[0]['hazard']), ['docs'])

    def test_au(self):
        r = fetch_au.parse_page(AU_HTML)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['date'], '2025-10-03')
        self.assertEqual(categorize(r[0]['product']), 'rice')
        self.assertEqual(reasons_from(r[0]['hazard']), ['chemical'])
        self.assertEqual(fetch_au.slug_month('.../failing-food-reports/oct-2025'), (2025, 10))
        self.assertEqual(fetch_au.slug_month('.../failing-food-reports/december2024'), (2024, 12))

    def test_jp(self):
        import openpyxl
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(['輸入食品等違反事例'])
        ws.append(['通知年月日', '食品等の品名', '原産国', '違反条文', '違反内容', '措置'])
        ws.append(['令和8年4月15日', 'ターメリック', 'インド', '第13条第3項', '残留農薬基準違反 クロルピリホス', '積戻し'])
        ws.append(['令和8年4月16日', '冷凍えび', 'ベトナム', '第6条', '動物用医薬品', '廃棄'])
        bio = io.BytesIO(); wb.save(bio)
        rows = next(fetch_jp.sheets(bio.getvalue(), 'x.xlsx'))
        r = fetch_jp.parse_rows(rows)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['date'], '2026-04-15')
        self.assertEqual(categorize(r[0]['product']), 'turmeric')
        self.assertEqual(reasons_from(r[0]['hazard']), ['pesticide'])
        self.assertEqual(fetch_jp.jp_date('平成30年1月2日'), '2018-01-02')

    def test_fda(self):
        r = fetch_fda.row_to_record(FDA_ROW)
        self.assertEqual(categorize(r['product']), 'cumin')
        self.assertIn('microbial', reasons_from(r['hazard']))
        self.assertIsNone(fetch_fda.row_to_record({**FDA_ROW, 'IndustryCode': 60}))

    def test_rasff(self):
        items = fetch_rasff.find_list(RASFF)
        recs = [x for x in (fetch_rasff.to_record(i) for i in items) if x]
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]['risk'], 1)
        self.assertEqual(recs[0]['ref'], '869134')

    def test_news(self):
        it = fetch_news.parse_feed(RSS)[0]
        n = fetch_news.tag(it)
        self.assertEqual(n['c'], 'cumin'); self.assertEqual(n['a'], 1); self.assertIn('US', n['m'])
        self.assertEqual(n['d'], '2026-10-05'); self.assertEqual(n['t'], 'FDA detains Indian cumin over salmonella')


if __name__ == '__main__':
    unittest.main()
