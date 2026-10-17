"""US FDA - import refusals via the FDA Data Dashboard API (free key required)."""
import os, json, hashlib
from common import http, clean, since_date

URL = 'https://api-datadashboard.fda.gov/v1/import_refusals'
FOOD_INDUSTRY_MAX = 41           # FDA industry codes 02-41 are food; 54 = vitamins/minerals
EXTRA_INDUSTRY = {54}


# The FDA documentation lists status 400 with the message "Success." as its success code (checked 17 Oct 2026);
# 401 = not authorised, 412 = no results, 413/414 = invalid filter name/value, 415 = more than 5000 rows.
OK_CODES = {'400', '200', 'None'}


class NoKey(Exception):
    pass


def row_to_record(r):
    try:
        ind = int(str(r.get('IndustryCode', '')).strip() or 0)
    except ValueError:
        ind = 0
    if not (2 <= ind <= FOOD_INDUSTRY_MAX or ind in EXTRA_INDUSTRY):
        return None
    date = str(r.get('RefusalDate') or '')[:10]
    if not date:
        return None
    prod = clean(r.get('ProductCodeDescription') or r.get('ProductCategory') or '')
    charges = clean(r.get('RefusalCharges') or '')
    key = '|'.join([str(r.get('ShipmentID', '')), date, prod, charges, str(r.get('FEINumber', ''))])
    return {'id': 'US-' + hashlib.md5(key.encode()).hexdigest()[:12], 'mk': 'US', 'date': date,
            'product': prod, 'pcat': clean(r.get('ProductCategory') or r.get('IndustryCodeDescription') or ''),
            'hazard': charges, 'risk': 0, 'ref': str(r.get('ShipmentID') or ''),
            'desc': clean(f'{prod}. {charges}', 130)}


def fetch():
    user, key = os.environ.get('FDA_API_USER'), os.environ.get('FDA_API_KEY')
    if not (user and key):
        raise NoKey('FDA_API_USER / FDA_API_KEY not set')
    since = since_date('us').isoformat()
    headers = {'Content-Type': 'application/json', 'Authorization-User': user, 'Authorization-Key': key}
    out, start, page = [], 1, 5000
    while True:
        body = {'columns': [], 'filters': {'CountryCode': ['IN'], 'RefusalDateFrom': [since]},
                'sort': 'RefusalDate', 'sortorder': 'desc', 'start': start, 'rows': page}
        resp = json.loads(http(URL, data=json.dumps(body).encode(), headers=headers, timeout=120))
        code = str(resp.get('statuscode'))
        if code == '412':                                  # "No results found" is a normal answer
            break
        if code not in OK_CODES:
            raise RuntimeError(f"FDA API: {code} {resp.get('message')} {resp.get('invalid_filters') or resp.get('invalid_columns') or ''}".strip())
        rows = resp.get('result') or []
        for r in rows:
            rec = row_to_record(r)
            if rec:
                out.append(rec)
        n = int(resp.get('resultcount') or len(rows))
        if n < page or not rows:
            break
        start += n
    return out
