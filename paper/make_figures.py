import json, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats

P = os.path.dirname(os.path.abspath(__file__)) + os.sep
R = json.load(open(P + 'results.json'))
m = R['main']
ids, cnt, val, rate = m['ids'], np.array(m['count']), np.array(m['value']), np.array(m['rate'])
rc, rr = np.array(m['rank_count']), np.array(m['rank_rate'])
NAME = dict(basmati='Basmati rice', rice='Rice (other)', sesame='Sesame', groundnut='Groundnut', pepper='Black pepper',
            chilli='Chilli', coriander='Coriander', cumin='Cumin', turmeric='Turmeric', fenugreek='Fenugreek', mango='Mango')

INK, MUTED, GRID = '#222222', '#6b6b6b', '#d9d9d9'
BLUE, ORANGE, GRAY = '#2a78d6', '#d95926', '#8a8a8a'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8.5, 'axes.edgecolor': GRID, 'text.color': INK,
                     'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED})

# ---------------- Figure 1: slope chart ----------------
def disp(rank, ids_):
    # tied ranks (3.5, 3.5) are drawn 0.5 apart so labels do not collide
    out = {}
    for i, r in zip(ids_, rank):
        out[i] = r
    ties = {}
    for i, r in out.items():
        ties.setdefault(r, []).append(i)
    for r, group in ties.items():
        if len(group) > 1:
            group.sort()
            for k, i in enumerate(group):
                out[i] = r + (k - (len(group) - 1) / 2) * 0.5
    return out

dl, dr = disp(rc, ids), disp(rr, ids)
fig, ax = plt.subplots(figsize=(6.4, 4.1), dpi=300)
for i, a, b in zip(ids, rc, rr):
    shift = b - a
    col = ORANGE if shift <= -4 else (BLUE if shift >= 4 else GRAY)
    lw = 1.8 if col != GRAY else 1.0
    ax.plot([0, 1], [dl[i], dr[i]], color=col, lw=lw, solid_capstyle='round', zorder=2 if col == GRAY else 3)
    ax.scatter([0, 1], [dl[i], dr[i]], s=22, color=col, edgecolor='white', linewidth=0.8, zorder=4)
    ax.text(-0.04, dl[i], f'{NAME[i]}', ha='right', va='center', fontsize=8.5, color=INK)
    ax.text(1.04, dr[i], f'{NAME[i]}', ha='left', va='center', fontsize=8.5, color=INK)
ax.set_xlim(-0.55, 1.55); ax.set_ylim(11.6, 0.4)
ax.set_xticks([0, 1]); ax.set_xticklabels(['Rank by raw count\n(24 months)', 'Rank by rate\n(per US$100M exports)'], fontsize=9, color=INK)
ax.xaxis.tick_top(); ax.tick_params(axis='x', length=0)
ax.set_yticks(range(1, 12)); ax.set_yticklabels([])
ax.tick_params(axis='y', length=0)
for s in ('left', 'right', 'bottom', 'top'):
    ax.spines[s].set_visible(False)
for k in range(1, 12):
    ax.axhline(k, color=GRID, lw=0.4, zorder=0)
# rank numbers in the middle margin
for k in range(1, 12):
    ax.text(0.5, k, '', fontsize=6)
# legend (manual, colour is never the only cue: labels + table)
ax.plot([], [], color=ORANGE, lw=1.8, label='moves up 4+ places by rate')
ax.plot([], [], color=BLUE, lw=1.8, label='moves down 4+ places by rate')
ax.plot([], [], color=GRAY, lw=1.0, label='moves less than 4 places')
ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.1), ncol=3, frameon=False, fontsize=7.5, handlelength=1.6)
fig.tight_layout()
fig.savefig(P + 'fig1_rank_slope.png', dpi=300, facecolor='white')
plt.close(fig)

# ---------------- Figure 2: log-log scatter ----------------
fig, ax = plt.subplots(figsize=(6.0, 4.0), dpi=300)
x = val; y = cnt
lx, ly = np.log(x), np.log(y)
sl = stats.linregress(lx, ly)
xs = np.linspace(lx.min() - 0.25, lx.max() + 0.25, 50)
ax.plot(np.exp(xs), np.exp(sl.intercept + sl.slope * xs), color=INK, lw=1.4, label=f'Fitted: slope {sl.slope:.2f} (95% CI {R["denominator"]["slope_ci95"][0]:.2f} to {R["denominator"]["slope_ci95"][1]:.2f})')
cx, cy = lx.mean(), ly.mean()
ax.plot(np.exp(xs), np.exp(cy + 1.0 * (xs - cx)), color=MUTED, lw=1.2, ls=(0, (4, 3)), label='If rejections were proportional to exports (slope 1)')
small = {'coriander', 'fenugreek'}
for i, xi, yi in zip(ids, x, y):
    col = ORANGE if i in small else BLUE
    ax.scatter([xi], [yi], s=34, color=col, edgecolor='white', linewidth=0.9, zorder=4)
off = dict(basmati=(-6, 6, 'right'), rice=(0, 8, 'center'), sesame=(7, -3, 'left'), groundnut=(7, -2, 'left'), pepper=(-6, 7, 'right'),
           chilli=(8, -2, 'left'), coriander=(7, 3, 'left'), cumin=(8, 9, 'left'), turmeric=(6, -9, 'left'), fenugreek=(-6, -9, 'right'), mango=(-7, -2, 'right'))
for i, xi, yi in zip(ids, x, y):
    dx, dy, ha = off[i]
    ax.annotate(NAME[i], (xi, yi), xytext=(dx, dy), textcoords='offset points', ha=ha, fontsize=8, color=INK)
ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xticks([10, 30, 100, 300]); ax.set_xticklabels(['10', '30', '100', '300']); ax.set_xlim(4.5, 900)
ax.set_yticks([20, 50, 100, 200]); ax.set_yticklabels(['20', '50', '100', '200']); ax.set_ylim(15, 300)
ax.minorticks_off()
ax.set_xlabel('Annual exports to the EU and US, FY2024-25 (US$ million, log scale)')
ax.set_ylabel('Border rejections, 24 months (log scale)')
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
ax.grid(color=GRID, lw=0.4)
ax.set_axisbelow(True)
ax.legend(loc='upper left', frameon=False, fontsize=7.5)
fig.tight_layout()
fig.savefig(P + 'fig2_count_vs_exports.png', dpi=300, facecolor='white')
plt.close(fig)

# extra numbers for the text
keep = np.array([i not in small for i in ids])
sl2 = stats.linregress(lx[keep], ly[keep])
print('slope all', sl.slope, 'slope w/o coriander+fenugreek', sl2.slope, 'p', sl2.pvalue, 'n', keep.sum())
print('rate range', rate.min(), rate.max(), 'ratio', rate.max() / rate.min())
print('value of coriander, fenugreek', val[ids.index('coriander')], val[ids.index('fenugreek')], 'share of total value', (val[ids.index('coriander')] + val[ids.index('fenugreek')]) / val.sum())
print('basmati share of count', cnt[ids.index('basmati')] / cnt.sum(), 'basmati share of value', val[ids.index('basmati')] / val.sum())
print('total count', cnt.sum(), 'total value', val.sum(), 'pooled rate', cnt.sum() / 2 / val.sum() * 100)
