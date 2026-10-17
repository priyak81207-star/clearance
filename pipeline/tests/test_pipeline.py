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
    {"notifId": 869134, "reference": "2026.1", "subject": "Ethylene oxide in sesame seeds from India", "ecValidationDate": "02-09-2026 10:00:00",
     "notificationClassification": {"id": 305, "description": "border rejection notification"}, "riskDecision": {"id": 1, "description": "serious"},
     "productCategory": {"id": 2, "description": "nuts, nut products and seeds"}, "originCountries": [{"organizationName": "India", "isoCode": "IN"}]},
    {"notifId": 869136, "reference": "2026.3", "subject": "Salmonella in cumin from India", "ecValidationDate": "02-09-2026 11:00:00",
     "notificationClassification": {"id": 301, "description": "alert notification"}, "riskDecision": {"id": 1, "description": "serious"},
     "originCountries": [{"organizationName": "India", "isoCode": "IN"}]},
    {"notifId": 869135, "reference": "2026.2", "subject": "Salmonella in tahini from Lebanon", "ecValidationDate": "02-09-2026 10:00:00",
     "notificationClassification": {"id": 305, "description": "border rejection notification"},
     "originCountries": [{"organizationName": "Lebanon", "isoCode": "LB"}]}], "totalPages": 1, "totalElements": 3}
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

    def test_fda_status_codes(self):
        """FDA reports success as statuscode 400 'Success.' (live check 17 Oct 2026); 412 = no results; 401 = bad key."""
        import json, os
        real_http = fetch_fda.http
        os.environ['FDA_API_USER'], os.environ['FDA_API_KEY'] = 'u@example.org', 'test-key'
        try:
            reply = lambda d: (lambda *a, **k: json.dumps(d).encode())
            fetch_fda.http = reply({'statuscode': 400, 'message': 'Success.', 'resultcount': 1, 'result': [FDA_ROW]})
            self.assertEqual(len(fetch_fda.fetch()), 1)
            fetch_fda.http = reply({'statuscode': 412, 'message': 'No results found.'})
            self.assertEqual(fetch_fda.fetch(), [])
            fetch_fda.http = reply({'statuscode': 401, 'message': 'Not Authorized.'})
            with self.assertRaises(RuntimeError):
                fetch_fda.fetch()
        finally:
            fetch_fda.http = real_http
            os.environ.pop('FDA_API_USER', None); os.environ.pop('FDA_API_KEY', None)

    def test_rasff(self):
        items = fetch_rasff.find_list(RASFF)
        recs = [x for x in (fetch_rasff.to_record(i) for i in items) if x]
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]['risk'], 1)
        self.assertEqual(recs[0]['ref'], '869134')
        self.assertEqual(recs[0]['date'], '2026-09-02')       # dd-mm-yyyy as sent by the live site
        self.assertEqual(recs[0]['pcat'], 'nuts, nut products and seeds')

    def test_jp_live_layout(self):
        # layout seen on the live MHLW file (2026-10-17): title row, then header with full-width-space padding
        import datetime as dt
        rows = [['輸入食品等の食品衛生法違反事例\n（2026年度分）'] + [None] * 11,
                ['品\u3000\u3000名', '条文', '製造者', 'シッパー', '生産国', '不適格内容', '担当検疫所', '輸入者名', '原因', '措置状況', '備考', '公表日'],
                ['ターメリック粉', '第13条第２項', 'X', '', 'インド', '成分規格不適合（アフラトキシン）', '横浜', 'Y', None, '廃棄', '自主検査', dt.datetime(2026, 4, 6)],
                ['揚げ豆類', '第13条第２項', 'Z', '', 'ミャンマー', '使用基準不適合', '成田空港', 'W', None, '廃棄', '自主検査', dt.datetime(2026, 4, 6)]]
        r = fetch_jp.parse_rows(rows)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['date'], '2026-04-06')
        self.assertEqual(categorize(r[0]['product']), 'turmeric')

    def test_au_live_header(self):
        html = ("<table><tr><th>Date of fail</th><th>Product description</th><th>County of origin</th><th>Producer Name</th>"
                "<th>Test applied / reason for fail</th><th>Results / Units</th><th>Reference criteria</th><th>Food category</th></tr>"
                "<tr><td>7/08/2026</td><td>Tapioca chips</td><td>India</td><td>M/S. X</td><td>Hydrocyanic acid detected in excess</td><td>110 mg/kg</td><td>FSC 1.4.1</td><td>Risk</td></tr>"
                "<tr><td>6/08/2026</td><td>Cooked prawn meat</td><td>Vietnam</td><td>Y</td><td>Fluoroquinolones</td><td>0.002</td><td>FSC 1.4.2</td><td>Risk</td></tr></table>")
        r = fetch_au.parse_page(html)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['date'], '2026-08-07')

    def test_news(self):
        it = fetch_news.parse_feed(RSS)[0]
        n = fetch_news.tag(it)
        self.assertEqual(n['c'], 'cumin'); self.assertEqual(n['a'], 1); self.assertIn('US', n['m'])
        self.assertEqual(n['d'], '2026-10-05'); self.assertEqual(n['t'], 'FDA detains Indian cumin over salmonella')


if __name__ == '__main__':
    unittest.main()
