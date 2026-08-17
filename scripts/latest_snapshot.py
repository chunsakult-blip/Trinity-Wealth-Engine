from pathlib import Path
import pandas as pd

CSV = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio/portfolio_summary.csv')
OUT = CSV.parent / 'latest_snapshot.csv'

if not CSV.exists():
    raise SystemExit('Missing portfolio_summary.csv')

df = pd.read_csv(CSV)
# normalize
df.columns = [c.strip() for c in df.columns]

# detect rightmost value and investment columns
value_cols = [c for c in df.columns if c.startswith('Value(THB)')]
cost_cols = [c for c in df.columns if c.startswith('investment (THB)')]
if not value_cols:
    raise SystemExit('No Value(THB) columns found')
right_value = value_cols[-1]
right_cost = cost_cols[-1] if cost_cols else None

# pick identifier column
id_col = None
for cand in ['Unnamed: 7','Fund/stock','Application','Unnamed: 1','Unnamed:0']:
    if cand in df.columns:
        id_col = cand
        break
if id_col is None:
    df['__id'] = df.index.astype(str)
    id_col = '__id'

# compute latest snapshot fields
df['latest_value'] = pd.to_numeric(df[right_value], errors='coerce').fillna(0.0)
if right_cost:
    df['latest_cost'] = pd.to_numeric(df[right_cost], errors='coerce').fillna(0.0)
else:
    # fallback to __cost_basis if present
    df['latest_cost'] = pd.to_numeric(df.get('__cost_basis', 0.0), errors='coerce').fillna(0.0)

# per-instrument aggregation by id_col
agg = df.groupby(id_col)[['latest_value','latest_cost']].sum().reset_index()
agg['pnl'] = agg['latest_value'] - agg['latest_cost']

# totals
totals = {
    'right_value_col': right_value,
    'right_cost_col': right_cost,
    'total_latest_value': float(agg['latest_value'].sum()),
    'total_latest_cost': float(agg['latest_cost'].sum()),
    'total_pnl': float(agg['pnl'].sum()),
}

agg.to_csv(OUT, index=False, encoding='utf-8-sig')
print('Wrote', OUT)
print('\nTotals:')
for k,v in totals.items():
    print(f'{k}: {v}')

print('\nTop 20 instruments:')
print(agg.sort_values('latest_value', ascending=False).head(20).to_string(index=False))
