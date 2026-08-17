from pathlib import Path
import sys
import json

EXCEL_PATH = Path(r'D:/AI test/Investment/Project1/Trinity-Wealth-Engine/My portfolio/target investment.xlsx')

# Try to import pandas, install if missing
try:
    import pandas as pd
except Exception:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "openpyxl"]) 
    import pandas as pd

# Ensure openpyxl is available for Excel reading
try:
    import openpyxl  # noqa: F401
except Exception:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"]) 
    import openpyxl

if not EXCEL_PATH.exists():
    print(json.dumps({"error": f"File not found: {EXCEL_PATH}"}))
    sys.exit(1)

try:
    # Read without header to detect where the real header row is (file uses stacked/offset headers)
    raw = pd.read_excel(EXCEL_PATH, header=None)
    header_row = None
    header_keys = ["asset class", "value(thb)", "value", "asset", "portfolio %", "investment (thb)"]
    for i in range(min(10, len(raw))):
        row = raw.iloc[i].tolist()
        row_vals = ["" if pd.isna(x) else str(x).lower() for x in row]
        if any(any(k in v for v in row_vals if v and v != 'nan') for k in header_keys):
            header_row = i
            break

    if header_row is not None:
        df = pd.read_excel(EXCEL_PATH, header=header_row)
    else:
        df = pd.read_excel(EXCEL_PATH)
except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)

# Basic info
info = {
    "path": str(EXCEL_PATH),
    "shape": df.shape,
    "columns": list(df.columns),
    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
}

# Show sample rows
info["sample_rows"] = df.head(10).fillna("").to_dict(orient="records")

# Identify likely numeric columns for value/cost/quantity
col_map = {c.lower(): c for c in df.columns}

candidates = {"value": None, "cost": None, "qty": None, "ticker": None, "asset_class": None}
for name, col in col_map.items():
    if any(k in name for k in ["market value", "market_value", "marketvalue", "value", "market val"]):
        candidates["value"] = col
    if any(k in name for k in ["cost", "cost basis", "cost_per", "cost_per_share", "cost_basis"]):
        candidates["cost"] = col
    if any(k in name for k in ["qty", "quantity", "shares"]):
        candidates["qty"] = col
    if any(k in name for k in ["ticker", "symbol", "isin"]):
        candidates["ticker"] = col
    if any(k in name for k in ["asset class", "asset_class", "assetclass", "class"]):
        candidates["asset_class"] = col

metrics = {}
# Compute totals if possible
try:
    if candidates["value"] and pd.api.types.is_numeric_dtype(df[candidates["value"]]):
        total_value = float(df[candidates["value"]].sum())
        metrics["total_market_value"] = total_value
    if candidates["cost"] and pd.api.types.is_numeric_dtype(df[candidates["cost"]]):
        total_cost = float(df[candidates["cost"]].sum())
        metrics["total_cost_basis"] = total_cost
    if "total_market_value" in metrics and "total_cost_basis" in metrics:
        metrics["unrealized_pl"] = metrics["total_market_value"] - metrics["total_cost_basis"]
        metrics["unrealized_pl_pct"] = (metrics["unrealized_pl"] / metrics["total_cost_basis"] * 100) if metrics["total_cost_basis"] != 0 else None
except Exception as e:
    metrics["error"] = str(e)

# Aggregate across multiple Value(THB) / investment (THB) columns if present
value_cols = [c for c in df.columns if str(c).lower().startswith('value(thb)')]
cost_cols = [c for c in df.columns if str(c).lower().startswith('investment (thb)')]

if value_cols:
    df['__current_value'] = df[value_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1, numeric_only=True)
if cost_cols:
    df['__cost_basis'] = df[cost_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1, numeric_only=True)

if '__current_value' in df.columns:
    metrics['total_current_value'] = float(df['__current_value'].sum(skipna=True))
if '__cost_basis' in df.columns:
    metrics['total_cost_basis_sum'] = float(df['__cost_basis'].sum(skipna=True))
if '__current_value' in df.columns and '__cost_basis' in df.columns:
    metrics['total_unrealized_pl'] = metrics['total_current_value'] - metrics['total_cost_basis_sum']

# Allocation by Asset Class using current value
alloc = None
if 'Asset Class' in df.columns and '__current_value' in df.columns:
    try:
        alloc_series = df.groupby('Asset Class')['__current_value'].sum().sort_values(ascending=False)
        alloc = alloc_series.to_dict()
        # Add percent
        total_val = alloc_series.sum()
        alloc = {k: {'value': float(v), 'pct': float(v/total_val) if total_val else None} for k, v in alloc.items()}
    except Exception:
        alloc = None

    # Also include allocation list for clearer ordering
    try:
        alloc_list = []
        for k, v in alloc_series.sort_values(ascending=False).items():
            alloc_list.append({'asset_class': k, 'value': float(v), 'pct': float(v/alloc_series.sum()) if alloc_series.sum() else None})
    except Exception:
        alloc_list = None
else:
    alloc_list = None

# Allocation by asset class
alloc = None
if candidates["asset_class"] and ("total_market_value" in metrics):
    try:
        grp = df.groupby(candidates["asset_class"])[candidates["value"]].sum().sort_values(ascending=False)
        alloc = grp.to_dict()
    except Exception:
        alloc = None

output = {"info": info, "candidates": candidates, "metrics": metrics, "allocation": alloc, "allocation_list": alloc_list}
print(json.dumps(output, ensure_ascii=False, indent=2, default=str))

# Write per-row summary CSV for verification
OUT_CSV = EXCEL_PATH.parent / 'portfolio_summary.csv'
try:
    summary_cols = list(df.columns) + []
    if '__current_value' in df.columns:
        df['__current_value'] = df['__current_value'].fillna(0)
    if '__cost_basis' in df.columns:
        df['__cost_basis'] = df['__cost_basis'].fillna(0)
    df.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    print(json.dumps({"summary_csv": str(OUT_CSV)}))
except Exception as e:
    print(json.dumps({"csv_error": str(e)}))
