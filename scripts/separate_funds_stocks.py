from pathlib import Path
import pandas as pd
import re

CSV = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio/per_row_detailed.csv')
OUT_STOCKS = CSV.parent / 'stocks_list.csv'
OUT_FUNDS = CSV.parent / 'funds_list.csv'

if not CSV.exists():
    raise SystemExit('Missing per_row_detailed.csv')

df = pd.read_csv(CSV)
df.columns = [c.strip() for c in df.columns]

if 'Fund/stock' not in df.columns:
    raise SystemExit('Missing Fund/stock column')

# ensure latest value/cost present
if '__current_value' not in df.columns or '__cost_basis' not in df.columns:
    raise SystemExit('Missing aggregated columns')

# aggregate by Fund/stock
agg = df.groupby('Fund/stock')[['__current_value','__cost_basis']].sum().reset_index()
agg = agg.rename(columns={'__current_value':'current','__cost_basis':'cost'})
agg['pnl'] = agg['current'] - agg['cost']

# guess type: ticker-like if token is uppercase and short
def guess_type(name):
    if pd.isna(name):
        return 'Unknown'
    s = str(name).strip()
    # treat names like 'BTC', 'VOO', 'MCD', 'PG', 'NVO' as ticker-like
    if re.fullmatch(r'[A-Z0-9]{1,6}', s):
        return 'Ticker'
    # names containing parentheses or spaces or lowercase -> Fund/Name
    if '(' in s or ' ' in s or any(c.islower() for c in s):
        return 'Fund/Name'
    # default: Fund/Name
    return 'Fund/Name'

agg['type'] = agg['Fund/stock'].apply(guess_type)

stocks = agg[agg['type']=='Ticker'].sort_values('current', ascending=False)
funds = agg[agg['type']!='Ticker'].sort_values('current', ascending=False)

stocks.to_csv(OUT_STOCKS, index=False, encoding='utf-8-sig')
funds.to_csv(OUT_FUNDS, index=False, encoding='utf-8-sig')

print('Wrote', OUT_STOCKS)
print('Wrote', OUT_FUNDS)
print('\nTop stocks:')
print(stocks.head(50).to_string(index=False))
print('\nTop funds/names:')
print(funds.head(50).to_string(index=False))
