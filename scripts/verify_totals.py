from pathlib import Path
import pandas as pd

BASE = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio')
SUMMARY = BASE / 'portfolio_summary.csv'
PER_INST = BASE / 'per_instrument_summary.csv'

if not SUMMARY.exists():
    raise SystemExit('Missing portfolio_summary.csv')

print('Reading', SUMMARY)
df = pd.read_csv(SUMMARY)
df.columns = [c.strip() for c in df.columns]

# sum of precomputed __current_value
pre_sum = float(df['__current_value'].sum()) if '__current_value' in df.columns else None
pre_cost = float(df['__cost_basis'].sum()) if '__cost_basis' in df.columns else None

# identify Value(THB) columns
value_cols = [c for c in df.columns if c.startswith('Value(THB)')]
cost_cols = [c for c in df.columns if c.startswith('investment (THB)')]

print('\nFound value columns:', value_cols)
print('Found cost columns:', cost_cols)

# print per-value-column sums
if value_cols:
    print('\nPer-value-column sums:')
    for c in value_cols:
        s = df[c].fillna(0).astype(float).sum()
        print(f"  {c}: {s}")

# per-row sum across value cols
if value_cols:
    per_row_vals = df[value_cols].fillna(0).astype(float).sum(axis=1)
    total_by_aggregating = per_row_vals.sum()
else:
    total_by_aggregating = None

# sum of rightmost value column (assume last in list)
if value_cols:
    rightmost = value_cols[-1]
    total_rightmost = df[rightmost].fillna(0).astype(float).sum()
else:
    rightmost = None
    total_rightmost = None

# sum per-instrument summary if exists
per_inst_sum = None
if PER_INST.exists():
    p = pd.read_csv(PER_INST)
    curcol = [c for c in p.columns if c.lower().startswith('current')]
    if curcol:
        per_inst_sum = float(p[curcol[0]].sum())


print('\nTotals:')
print('sum(__current_value)          =', pre_sum)
print('sum(__cost_basis)            =', pre_cost)
print('sum(all Value(THB) per-row)  =', total_by_aggregating)
print('rightmost value column', rightmost, 'sum =', total_rightmost)
print('sum(per_instrument current)  =', per_inst_sum)

# show rows where __current_value differs from sum of value cols
if value_cols and '__current_value' in df.columns:
    diff = df['__current_value'] - per_row_vals
    bad = df[diff.abs() > 1e-6]
    if not bad.empty:
        print('\nRows where __current_value != sum(Value columns):')
        print(bad[[col for col in ['Asset Class','Unnamed: 7','Fund/stock'] if col in df.columns][:3]+['__current_value']+value_cols].head(20).to_string(index=False))
    else:
        print('\nAll __current_value equal summed Value columns')

# list top 10 contributors by __current_value
print('\nTop 10 rows by __current_value:')
print(df.sort_values('__current_value', ascending=False)[['Asset Class','Unnamed: 7','__current_value']].head(10).to_string(index=False))

# final sanity: print counts and shapes
print('\nRow count:', len(df))

print('\nDone')
