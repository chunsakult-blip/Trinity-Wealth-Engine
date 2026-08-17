from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
MP = ROOT / 'My portfolio'
LATEST = MP / 'latest_snapshot.csv'
STOCKS = MP / 'stocks_list.csv'
FUNDS = MP / 'funds_list.csv'

def read_set(path):
    s = set()
    if not path.exists():
        return s
    with path.open(encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # use the first column as the identifier to be robust to header variations
        key = reader.fieldnames[0] if reader.fieldnames else 'Fund/stock'
        for r in reader:
            s.add(r.get(key))
    return s

def main():
    stocks = read_set(STOCKS)
    funds = read_set(FUNDS)

    if not LATEST.exists():
        print('Missing', LATEST)
        return

    rows = []
    with LATEST.open(encoding='utf-8') as f:
        reader = csv.DictReader(f)
        latest_key = reader.fieldnames[0] if reader.fieldnames else 'Fund/stock'
        for r in reader:
            try:
                v = float(r.get('latest_value', 0.0))
            except Exception:
                v = 0.0
            if v > 0:
                name = r.get(latest_key)
                typ = 'Unknown'
                if name in stocks:
                    typ = 'Ticker'
                elif name in funds:
                    typ = 'Fund/Name'
                rows.append((name, v, float(r.get('latest_cost', 0.0)), float(r.get('pnl', 0.0)), typ))

    rows.sort(key=lambda x: x[1], reverse=True)

    out = MP / 'july_2026_holdings.csv'
    with out.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Fund/stock','latest_value','latest_cost','pnl','type'])
        for r in rows:
            writer.writerow(r)

    print('Wrote', out)
    print()
    for r in rows:
        print(f"{r[0]:30} {r[1]:12,.2f}  cost {r[2]:12,.2f}  pnl {r[3]:12,.2f}  {r[4]}")

if __name__ == '__main__':
    main()
