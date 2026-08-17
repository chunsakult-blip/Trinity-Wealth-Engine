from pathlib import Path
import csv
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
MP = ROOT / 'My portfolio'
STOCKS = MP / 'stocks_list.csv'

def candidates(sym):
    syms = [sym]
    if not sym.endswith('.BK'):
        syms.append(sym + '.BK')
    # USD variants
    syms.append(sym + '-USD')
    syms.append(sym + 'USD')
    if sym.upper() == 'BTC':
        syms.insert(0, 'BTC-USD')
    return syms

def get_price_and_currency(sym):
    try:
        tk = yf.Ticker(sym)
        fi = getattr(tk, 'fast_info', None)
        price = None
        cur = None
        if fi is not None:
            last = getattr(fi, 'last_price', None)
            if last is not None:
                price = float(last)
            cur = getattr(fi, 'currency', None)
        if price is None:
            hist = tk.history(period='1d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
        return price, cur
    except Exception:
        return None, None

def get_usd_thb():
    p, _ = get_price_and_currency('USDTHB=X')
    return p

def main():
    if not STOCKS.exists():
        print('Missing', STOCKS)
        return
    usdthb = get_usd_thb() or 35.0

    rows = []
    with STOCKS.open(encoding='utf-8') as f:
        reader = csv.DictReader(f)
        key = reader.fieldnames[0] if reader.fieldnames else 'Fund/stock'
        for r in reader:
            name = r.get(key)
            if not name:
                continue
            # skip CASH-like
            if name.upper().startswith('CASH'):
                continue
            found = False
            for c in candidates(name):
                price, cur = get_price_and_currency(c)
                if price and price > 0:
                    # determine THB price
                    if (cur and cur.upper() == 'THB') or c.endswith('.BK'):
                        price_thb = price
                        currency = 'THB'
                    else:
                        price_thb = price * usdthb
                        currency = 'USD'
                    rows.append((name, c, price, currency, price_thb))
                    found = True
                    break
            if not found:
                rows.append((name, '', None, None, None))

    # print table
    print('Ticker | YF Sym | Price | Currency | Price (THB)')
    for r in rows:
        name, sym, price, cur, pthb = r
        if price is None:
            print(f"{name:12} | {'-':8} | {'-':12} | {'-':8} | {'-':12}")
        else:
            print(f"{name:12} | {sym:8} | {price:12,.6f} | {cur:8} | {pthb:12,.2f}")

if __name__ == '__main__':
    main()
