from pathlib import Path
import pandas as pd

CSV = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio/portfolio_summary.csv')
OUT = CSV.parent / 'per_row_detailed.csv'

if not CSV.exists():
    raise SystemExit('Missing portfolio_summary.csv')

df = pd.read_csv(CSV)
df.columns = [c.strip() for c in df.columns]

# identify value and cost columns
value_cols = [c for c in df.columns if c.startswith('Value(THB)')]
cost_cols = [c for c in df.columns if c.startswith('investment (THB)')]

# ensure numeric
for c in value_cols + cost_cols + ['__current_value','__cost_basis']:
    if c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        except Exception:
            pass

# compute per-row pnl from aggregated columns if available
if '__current_value' in df.columns and '__cost_basis' in df.columns:
    df['__pnl'] = df['__current_value'] - df['__cost_basis']
else:
    # compute from sums of value and cost cols
    df['__pnl'] = df[value_cols].fillna(0).sum(axis=1) - df[cost_cols].fillna(0).sum(axis=1)

# select columns to output
base_cols = ['Asset Class', 'Fund/stock', 'Unnamed: 7', 'Application']
out_cols = [c for c in base_cols if c in df.columns]
out_cols += value_cols + cost_cols + ['__current_value', '__cost_basis', '__pnl']

out_df = df[out_cols]
out_df.to_csv(OUT, index=False, encoding='utf-8-sig')
print('Wrote', OUT)
print(out_df.to_string(index=False))
