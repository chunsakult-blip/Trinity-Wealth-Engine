from pathlib import Path
import csv
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
MP = ROOT / 'My portfolio'
JULY = MP / 'july_2026_holdings.csv'

def candidates(sym):
    syms = [sym]
    if not sym.endswith('.BK'):
        syms.append(sym + '.BK')
    syms.append(sym + '-USD')
    syms.append(sym + 'USD')
    if sym.upper() == 'BTC':
        syms.insert(0, 'BTC-USD')
    return syms

def get_price(sym):
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

def get_usdthb():
    p, _ = get_price('USDTHB=X')
    return p

def main():
    if not JULY.exists():
        print('Missing', JULY)
        return

    usdthb = get_usdthb() or 35.0

    rows = []
    with JULY.open(encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            typ = r.get('type','')
            if typ != 'Ticker':
                continue
            name = r.get('Fund/stock')
            rows.append(name)

    print('Ticker | YF_Symbol | Price | Currency | Price_THB')
    for name in rows:
        found = False
        for c in candidates(name):
            price, cur = get_price(c)
            if price and price>0:
                if (cur and cur.upper()=='THB') or c.endswith('.BK'):
                    pthb = price
                else:
                    pthb = price * usdthb if usdthb else None
                cur_display = cur if cur else ('THB' if c.endswith('.BK') else 'USD')
                pthb_display = f"{pthb:,.2f}" if pthb else ''
                print(f"{name} | {c} | {price:.6f} | {cur_display} | {pthb_display}")
                found = True
                break
        if not found:
            print(f"{name} |  |  |  | ")

if __name__ == '__main__':
    main()
