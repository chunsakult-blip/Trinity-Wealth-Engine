from pathlib import Path
import pandas as pd

CSV = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio/per_row_detailed.csv')
if not CSV.exists():
    CSV = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio/portfolio_summary.csv')

df = pd.read_csv(CSV)
df.columns = [c.strip() for c in df.columns]

value_cols = [c for c in df.columns if c.startswith('Value(THB)')]
cost_cols = [c for c in df.columns if c.startswith('investment (THB)')]

cols = value_cols + cost_cols + ['__current_value','__cost_basis']
cols = [c for c in cols if c in df.columns]

print('Columns:', cols)
print(df[cols].to_string(index=False))
