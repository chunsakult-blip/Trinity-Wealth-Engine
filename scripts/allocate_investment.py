from pathlib import Path
import pandas as pd

CSV = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio/portfolio_summary.csv')
OUT = CSV.parent / 'allocation_recommendation.csv'
AVAILABLE = 798351.0

if not CSV.exists():
    raise SystemExit(f'File not found: {CSV}')

df = pd.read_csv(CSV)
# normalize columns
cols = [c.strip() for c in df.columns]
df.columns = cols

cur_col = '__current_value'
# detect a target column from several possible names used in the sheet
target_candidates = ['มูลค่าเป้า (บาท) Y2026', 'มูลค่าเป้า (บาท)', 'เป้า 2026', 'เป้า2026']
target_col = None
for t in target_candidates:
    if t in df.columns:
        target_col = t
        break
asset_col = 'Asset Class'

if asset_col not in df.columns:
    raise SystemExit('Missing Asset Class column')

# group
grp_current = df.groupby(asset_col)[cur_col].sum()
# pick target as first non-null target per asset class (or 0 if not present)
if target_col is None:
    grp_target = df.groupby(asset_col).apply(lambda g: 0.0)
    grp_target.index = grp_target.index.droplevel(0)
else:
    grp_target = df.groupby(asset_col)[target_col].first()

grp_current = grp_current.fillna(0).astype(float)
grp_target = grp_target.fillna(0).astype(float)

alloc = pd.DataFrame({'current': grp_current, 'target': grp_target})
alloc['deficit'] = (alloc['target'] - alloc['current']).clip(lower=0)

deficit_sum = alloc['deficit'].sum()
if deficit_sum <= 0:
    alloc['alloc_share'] = 0.0
    alloc['recommended_invest'] = 0.0
else:
    alloc['alloc_share'] = alloc['deficit'] / deficit_sum
    alloc['recommended_invest'] = (alloc['alloc_share'] * AVAILABLE)

alloc['post_invest_value'] = alloc['current'] + alloc['recommended_invest']

# round for presentation
out = alloc[['current','target','deficit','recommended_invest','post_invest_value']].round(2)

out.to_csv(OUT, encoding='utf-8-sig')
print('Wrote', OUT)
print(out.to_string())
print('\nAvailable to invest:', AVAILABLE)
