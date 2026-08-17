from pathlib import Path
import csv
import math
import yfinance as yf
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
MP = ROOT / 'My portfolio'
JULY = MP / 'july_2026_holdings.csv'

def try_get_close(ticker, date):
    try:
        tk = yf.Ticker(ticker)
        start = date.strftime('%Y-%m-%d')
        end = (date + timedelta(days=1)).strftime('%Y-%m-%d')
        hist = tk.history(start=start, end=end)
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception:
        return None
    return None

def get_current_price(ticker):
    try:
        tk = yf.Ticker(ticker)
        fi = tk.fast_info
        last = getattr(fi, 'last_price', None)
        if last is not None:
            return float(last)
        hist = tk.history(period='1d')
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception:
        return None
    return None

def candidates(sym):
    # try common variants
    syms = [sym]
    if not sym.endswith('.BK'):
        syms.append(sym + '.BK')
    if not sym.endswith('-USD') and not sym.endswith('USD'):
        syms.append(sym + '-USD')
        syms.append(sym + 'USD')
    # special for BTC
    if sym.upper() == 'BTC':
        syms = ['BTC-USD'] + syms
    return syms

def find_close_for_july(sym):
    # try 2026-07-31 back to 2026-07-27
    base = datetime(2026,7,31)
    for d in range(0,5):
        date_dt = base - timedelta(days=d)
        for c in candidates(sym):
            val = try_get_close(c, date_dt)
            if val is not None and val > 0:
                return val, c, date_dt.strftime('%Y-%m-%d')
    return None, None, None

def main():
    if not JULY.exists():
        print('Missing', JULY)
        return
    rows = []
    with JULY.open(encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = r['Fund/stock']
            typ = r.get('type','')
            if typ != 'Ticker':
                continue
            last_value = float(r.get('latest_value',0) or 0)
            rows.append((name, last_value))

    out_rows = []
    total_est = 0.0
    # fetch USDTHB rate
    try:
        fx = None
        fx = get_current_price('USDTHB=X')
    except Exception:
        fx = None
    for name, last_value in rows:
        close, used_sym, date = find_close_for_july(name)
        current = None
        used_current_sym = None
        if used_sym:
            current = get_current_price(used_sym)
            used_current_sym = used_sym
        else:
            # try simple candidates for current
            for c in candidates(name):
                current = get_current_price(c)
                if current:
                    used_current_sym = c
                    break

        if close and close>0 and current and current>0:
            # determine currency: if used_sym ends with .BK it's THB, otherwise assume USD and convert
            curr_price = current
            if used_current_sym and used_current_sym.endswith('.BK'):
                curr_price_thb = curr_price
            else:
                curr_price_thb = curr_price * fx if fx else None

            # convert close to THB similarly
            close_thb = close if used_sym and used_sym.endswith('.BK') else (close * fx if fx else None)

            if close_thb and close_thb>0 and curr_price_thb and curr_price_thb>0:
                units = last_value / close_thb
                est_current_value = units * curr_price_thb
            else:
                units = math.nan
                est_current_value = math.nan
        else:
            units = math.nan
            est_current_value = math.nan

        out_rows.append((name, last_value, close, date, used_current_sym, current, units, est_current_value))
        if est_current_value and not math.isnan(est_current_value):
            total_est += est_current_value

    # print
    print('Ticker | July Value | July Close | Close Date | Current Sym | Current Price | Est Units | Est Current Value')
    for r in out_rows:
        print(f"{r[0]:10} | {r[1]:12,.2f} | {r[2] if r[2] else '':10} | {r[3] or '':10} | {r[4] or '':12} | {r[5] if r[5] else '':12} | {r[6]:10,.6f} | {r[7]:12,.2f}")

    print('\nEstimated Tickers Current Total: {0:,.2f} THB'.format(total_est))

if __name__ == '__main__':
    main()
