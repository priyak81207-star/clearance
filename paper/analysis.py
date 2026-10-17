"""Analysis for the count-vs-rate ranking paper. Reads data.json (frozen 2026-08 snapshot).
Writes results.json. Seeded; rerunning gives identical numbers."""
import json, os, sys
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'data.json')
OUT = os.path.join(HERE, 'results.json')
rng = np.random.default_rng(20261017)
B = 10000

d = json.load(open(SRC))
cats = {c['id']: c for c in d['cats']}

# sanity: monthly arrays sum to raw counts
for c in d['cats']:
    s = c['stats']
    assert sum(s['monthly']['eu']) == s['eu'], c['id']
    assert sum(s['monthly']['us']) == s['us'], c['id']

def val(c, m):
    t = c['trade'].get(m)
    return None if not t else t.get('val')

def build(window=24, markets=('eu', 'us')):
    """Return list of (id, count_in_window, annual_value_USDm) for products with a value in every requested market."""
    rows = []
    for c in d['cats']:
        vs = [val(c, m) for m in markets]
        if any(v is None for v in vs):
            continue
        cnt = sum(sum(c['stats']['monthly'][m][-window:]) for m in markets)
        rows.append((c['id'], cnt, sum(vs)))
    return rows

def rate(cnt, v, window):
    return (cnt / (window / 12.0)) / v * 100.0   # annualised rejections per US$100M of annual exports

def rank_desc(x):
    return stats.rankdata(-np.asarray(x, float), method='average')

def agreement(counts, rates):
    rho, _ = stats.spearmanr(counts, rates)
    tau, _ = stats.kendalltau(counts, rates)
    return rho, tau

R = {}

# ---------- main set: 11 products with EU+US values, 24 months ----------
rows = build(24)
ids = [r[0] for r in rows]; n = len(ids)
cnt = np.array([r[1] for r in rows], float)
vv = np.array([r[2] for r in rows], float)
rt = np.array([rate(r[1], r[2], 24) for r in rows])
rc, rr = rank_desc(cnt), rank_desc(rt)
rho, tau = agreement(cnt, rt)
R['main'] = dict(n=n, ids=ids, count=cnt.tolist(), value=vv.tolist(), rate=rt.tolist(),
                 rank_count=rc.tolist(), rank_rate=rr.tolist(), rho=rho, tau=tau)

# exact-ish permutation p-value (two-sided) for rho = 0
perm = np.empty(B)
for i in range(B):
    perm[i] = stats.spearmanr(cnt, rng.permutation(rt))[0]
R['main']['perm_p_two_sided'] = float((np.sum(np.abs(perm) >= abs(rho)) + 1) / (B + 1))

# bootstrap over products
bs = []
for _ in range(B):
    idx = rng.integers(0, n, n)
    if len(set(cnt[idx])) < 2 or len(set(rt[idx])) < 2:
        continue
    bs.append(stats.spearmanr(cnt[idx], rt[idx])[0])
bs = np.array(bs)
R['main']['boot_ci95'] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
R['main']['boot_n_valid'] = int(len(bs))
R['main']['boot_p_rho_ge_0.5'] = float(np.mean(bs >= 0.5))

# top-k overlap vs hypergeometric
def topk(k):
    a = set(np.argsort(rc, kind='stable')[:k]); b = set(np.argsort(rr, kind='stable')[:k])
    ov = len(a & b)
    # P(overlap >= ov) under random
    p = stats.hypergeom.sf(ov - 1, n, k, k)
    return dict(k=k, overlap=ov, only_count=[ids[i] for i in a - b], only_rate=[ids[i] for i in b - a],
                both=[ids[i] for i in a & b], expected=k * k / n, p_ge=float(p))
R['main']['top3'] = topk(3); R['main']['top5'] = topk(5)
R['main']['mean_abs_rank_shift'] = float(np.mean(np.abs(rc - rr)))
R['main']['max_shift'] = sorted([(ids[i], float(rc[i]), float(rr[i]), float(abs(rc[i] - rr[i]))) for i in range(n)],
                                key=lambda t: -t[3])[:4]

# ---------- denominator effect ----------
rho_cv, p_cv = stats.spearmanr(cnt, vv)
rho_rv, p_rv = stats.spearmanr(rt, vv)
R['denominator'] = dict(rho_count_value=rho_cv, p_count_value=p_cv, rho_rate_value=rho_rv, p_rate_value=p_rv)
lc, lv, lr = np.log(cnt), np.log(vv), np.log(rt)
# log(rate) = log(count) - log(value) + const ; share of variance
R['denominator']['var_log_count'] = float(np.var(lc, ddof=1))
R['denominator']['var_log_value'] = float(np.var(lv, ddof=1))
R['denominator']['var_log_rate'] = float(np.var(lr, ddof=1))
R['denominator']['cov_log_count_value'] = float(np.cov(lc, lv, ddof=1)[0, 1])
R['denominator']['r_log_count_log_value'] = float(np.corrcoef(lc, lv)[0, 1])
slope = stats.linregress(lv, lc)
R['denominator']['slope_logcount_on_logvalue'] = float(slope.slope)
R['denominator']['slope_ci95'] = [float(slope.slope - 2.262 * slope.stderr), float(slope.slope + 2.262 * slope.stderr)]  # t(9)
R['denominator']['slope_p'] = float(slope.pvalue)
R['denominator']['r2'] = float(slope.rvalue ** 2)

# ---------- Poisson noise simulation ----------
sim_rho = np.empty(B); top5_c = np.zeros(n); top5_r = np.zeros(n)
rank_c_all = np.empty((B, n)); rank_r_all = np.empty((B, n))
for b in range(B):
    c2 = rng.poisson(cnt)
    r2 = (c2 / 2.0) / vv * 100.0
    sim_rho[b] = stats.spearmanr(c2, r2)[0] if len(set(c2)) > 1 else np.nan
    rc2, rr2 = rank_desc(c2), rank_desc(r2)
    rank_c_all[b], rank_r_all[b] = rc2, rr2
    top5_c += rc2 <= 5; top5_r += rr2 <= 5
sim_rho = sim_rho[~np.isnan(sim_rho)]
R['poisson'] = dict(rho_mean=float(sim_rho.mean()), rho_ci95=[float(np.percentile(sim_rho, 2.5)), float(np.percentile(sim_rho, 97.5))],
                    p_rho_ge_0_5=float(np.mean(sim_rho >= 0.5)), p_rho_ge_0_8=float(np.mean(sim_rho >= 0.8)),
                    rank_rate_90=[[ids[i], float(np.percentile(rank_r_all[:, i], 5)), float(np.percentile(rank_r_all[:, i], 95))] for i in range(n)],
                    rank_count_90=[[ids[i], float(np.percentile(rank_c_all[:, i], 5)), float(np.percentile(rank_c_all[:, i], 95))] for i in range(n)],
                    p_top5_count={ids[i]: float(top5_c[i] / B) for i in range(n)},
                    p_top5_rate={ids[i]: float(top5_r[i] / B) for i in range(n)})

# ---------- sensitivity ----------
def rho_subset(mask):
    m = np.array(mask)
    return float(stats.spearmanr(cnt[m], rt[m])[0]), int(m.sum())
sens = {}
sens['drop_coriander'] = rho_subset([i != 'coriander' for i in ids])
sens['drop_coriander_fenugreek'] = rho_subset([i not in ('coriander', 'fenugreek') for i in ids])
loo = []
for k in range(n):
    m = [j != k for j in range(n)]
    loo.append((ids[k], float(stats.spearmanr(cnt[m], rt[m])[0])))
sens['leave_one_out'] = loo
sens['loo_range'] = [min(x[1] for x in loo), max(x[1] for x in loo)]
# 12-month window
r12 = build(12)
c12 = np.array([r[1] for r in r12], float); v12 = np.array([r[2] for r in r12], float)
rt12 = np.array([rate(r[1], r[2], 12) for r in r12])
ok = c12 > 0
sens['window_12m'] = dict(n=int(ok.sum()), rho=float(stats.spearmanr(c12[ok], rt12[ok])[0]),
                          zero_count=[r12[i][0] for i in range(len(r12)) if not ok[i]])
# first 12 months
first = []
for c in d['cats']:
    if val(c, 'eu') is None or val(c, 'us') is None: continue
    first.append((c['id'], sum(sum(c['stats']['monthly'][m][:12]) for m in ('eu', 'us')), val(c, 'eu') + val(c, 'us')))
cf = np.array([r[1] for r in first], float); vf = np.array([r[2] for r in first], float)
sens['window_first12m'] = dict(rho=float(stats.spearmanr(cf, cf / vf * 100)[0]))
# single market
for m in ('us', 'eu'):
    rm = build(24, (m,))
    cm = np.array([r[1] for r in rm], float); vm = np.array([r[2] for r in rm], float)
    rtm = np.array([rate(r[1], r[2], 24) for r in rm])
    rh, pp = stats.spearmanr(cm, rtm)
    sens[f'{m}_only'] = dict(n=len(rm), rho=float(rh), p=float(pp), ids=[r[0] for r in rm])
# drop coriander in single markets too
rm = [r for r in build(24, ('us',)) if r[0] != 'coriander']
cm = np.array([r[1] for r in rm], float); rtm = np.array([rate(r[1], r[2], 24) for r in rm])
sens['us_only_no_coriander'] = dict(n=len(rm), rho=float(stats.spearmanr(cm, rtm)[0]))
R['sensitivity'] = sens

# ---------- descriptive: all 15 categories ----------
R['all15'] = [dict(id=c['id'], eu=c['stats']['eu'], us=c['stats']['us'], total=c['stats']['total'],
                   val_eu=val(c, 'eu'), val_us=val(c, 'us')) for c in d['cats']]
R['totals'] = dict(eu=sum(c['stats']['eu'] for c in d['cats']), us=sum(c['stats']['us'] for c in d['cats']))
R['months'] = [d['months'][0], d['months'][-1]]

json.dump(R, open(OUT, 'w'), indent=1, default=float)
print(json.dumps(R['main'], indent=1, default=float)[:3500])
