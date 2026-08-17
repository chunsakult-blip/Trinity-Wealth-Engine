from pathlib import Path
import pandas as pd

CSV = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio/portfolio_summary.csv')
OUT = CSV.parent / 'per_instrument_summary.csv'

if not CSV.exists():
    raise SystemExit(f'File not found: {CSV}')

# Read
df = pd.read_csv(CSV)
# normalize
df.columns = [c.strip() for c in df.columns]

# possible ticker columns
candidates = ['Ticker','Symbol','Code','Unnamed: 7','Unnamed: 1','Unnamed:1','Unnamed:0','Application']
cols = df.columns.tolist()

ticker_col = None
for c in candidates:
    if c in cols:
        ticker_col = c
        break
# fallback: choose the first column after Asset Class that looks like short text
if not ticker_col:
    if 'Asset Class' in cols:
        idx = cols.index('Asset Class')
        if idx+1 < len(cols):
            ticker_col = cols[idx+1]

if not ticker_col:
    # last resort: use index
    df['__ticker_index'] = df.index.astype(str)
    ticker_col = '__ticker_index'

cur_col = '__current_value'
cost_col = '__cost_basis'

if cur_col not in df.columns or cost_col not in df.columns:
    raise SystemExit('Missing required value/cost columns in CSV')

# group by ticker and aggregate
agg = df.groupby(ticker_col)[[cur_col, cost_col]].sum()
agg = agg.rename(columns={cur_col: 'current', cost_col: 'cost'})
agg['pnl'] = agg['current'] - agg['cost']

agg = agg.reset_index()
agg.to_csv(OUT, index=False, encoding='utf-8-sig')
print('Wrote', OUT)
print(agg.head(20).to_string(index=False))
