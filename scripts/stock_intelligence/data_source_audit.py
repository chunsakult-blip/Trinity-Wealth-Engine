from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "audits"
    / "nick_v3_data_source_audit.json"
)


SIGNATURES = {

    "yahoo_finance": [
        "yfinance",
        "yf.Ticker",
        "finance.yahoo.com",
        "query1.finance.yahoo.com",
    ],

    "fred": [
        "fred.stlouisfed.org",
        "api.stlouisfed.org",
        "FredReader",
    ],

    "sec": [
        "sec.gov",
        "data.sec.gov",
        "edgar",
    ],

    "nasdaq_trader": [
        "nasdaqtrader.com",
        "nasdaqlisted.txt",
        "otherlisted.txt",
    ],

    "polygon": [
        "polygon.io",
        "polygon",
    ],

    "finnhub": [
        "finnhub.io",
        "finnhub",
    ],

    "fmp": [
        "financialmodelingprep.com",
        "fmp",
    ],

    "alpha_vantage": [
        "alphavantage.co",
        "alpha_vantage",
    ],

    "stooq": [
        "stooq.com",
        "stooq",
    ],

    "rss": [
        "rss",
        "feedparser",
        "feeds.finance",
    ],
}


FIELD_HINTS = {

    "revenue": [
        "revenue",
        "total revenue",
    ],

    "gross_profit": [
        "gross profit",
    ],

    "operating_income": [
        "operating income",
    ],

    "net_income": [
        "net income",
    ],

    "eps": [
        "eps",
        "earnings per share",
    ],

    "free_cash_flow": [
        "free cash flow",
        "free_cash_flow",
    ],

    "operating_cash_flow": [
        "operating cash flow",
        "operating_cash_flow",
    ],

    "capital_expenditure": [
        "capital expenditure",
        "capital_expenditure",
        "capex",
    ],

    "cash": [
        "cash cash equivalents",
        "cash and cash equivalents",
        "total cash",
    ],

    "debt": [
        "total debt",
        "debt",
    ],

    "assets": [
        "total assets",
    ],

    "equity": [
        "stockholders equity",
        "total equity",
        "equity",
    ],

    "shares": [
        "ordinary shares number",
        "share issued",
        "shares outstanding",
    ],

    "price": [
        ".history(",
        "close",
        "open",
        "high",
        "low",
    ],

    "volume": [
        "volume",
    ],

    "market_cap": [
        "market cap",
        "market_cap",
    ],

    "growth": [
        "calculate_growth",
        "growth",
    ],

    "margin": [
        "gross_margin",
        "operating_margin",
        "profit_margin",
    ],

    "roe": [
        "roe",
    ],

    "roa": [
        "roa",
    ],

    "roic": [
        "roic",
    ],

    "roic": [
        "roic",
    ],

    "net_debt": [
        "net_debt",
    ],

    "debt_to_equity": [
        "debt_to_equity",
    ],

    "valuation": [
        "valuation",
        "pe_ratio",
        "price_to_sales",
        "price_to_book",
        "ev_ebitda",
        "enterprise_value",
    ],

    "news": [
        "news",
        "headline",
        "article",
        "rss",
    ],

    "sec_filings": [
        "10-k",
        "10-q",
        "8-k",
        "filing",
        "edgar",
    ],

    "macro": [
        "macro",
        "interest rate",
        "inflation",
        "cpi",
        "gdp",
        "unemployment",
        "fed",
        "fred",
    ],
}


IGNORED_PATH_PARTS = (
    "\\.venv\\",
    "\\venv\\",
    "\\__pycache__\\",
    "\\site-packages\\",
    "\\_atlas_backup_",
    "\\_backup_",
)

IGNORED_FILES = {
    "data_source_audit.py",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize(text: str) -> str:
    return (
        text
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def classify_sources(text: str) -> list[str]:

    lowered = text.lower()
    found = []

    for source, signatures in SIGNATURES.items():

        for signature in signatures:

            if signature.lower() in lowered:
                found.append(source)
                break

    return sorted(set(found))


def classify_fields(text: str) -> list[str]:

    lowered = normalize(text)
    found = []

    for field, hints in FIELD_HINTS.items():

        for hint in hints:

            if normalize(hint) in lowered:
                found.append(field)
                break

    return sorted(set(found))


def extract_urls(text: str) -> list[str]:

    urls = re.findall(
        r'https?://[^\s"\')]+',
        text,
        flags=re.IGNORECASE,
    )

    cleaned = []

    for url in urls:

        url = url.rstrip(
            ".,;)]}>"
        )

        if url not in cleaned:
            cleaned.append(url)

    return cleaned


def safe_relative(path: Path) -> str:

    try:
        return str(
            path.relative_to(PROJECT_ROOT)
        )

    except ValueError:
        return str(path)


def should_skip(path: Path) -> bool:

    if path.name.lower() in {
        name.lower()
        for name in IGNORED_FILES
    }:
        return True

    path_string = str(path).lower()

    return any(
        blocked in path_string
        for blocked in IGNORED_PATH_PARTS
    )


def scan_python_files():

    files = sorted(
        PROJECT_ROOT.rglob("*.py")
    )

    results = []

    for path in files:

        if should_skip(path):
            continue

        try:

            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

        except Exception as exc:

            results.append(
                {
                    "file": safe_relative(path),
                    "read_error": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                }
            )

            continue

        sources = classify_sources(text)
        fields = classify_fields(text)
        urls = extract_urls(text)

        source_lines = defaultdict(list)

        lines = text.splitlines()

        for line_number, line in enumerate(
            lines,
            start=1,
        ):

            line_sources = classify_sources(
                line
            )

            for source in line_sources:

                source_lines[source].append(
                    line_number
                )

        if (
            sources
            or fields
            or urls
        ):

            results.append(
                {
                    "file": safe_relative(path),
                    "sources": sources,
                    "fields": fields,
                    "urls": urls,
                    "source_lines": dict(
                        source_lines
                    ),
                }
            )

    return results


def build_report():

    files = scan_python_files()

    source_files = defaultdict(list)
    field_files = defaultdict(list)
    all_urls = []

    for item in files:

        file_name = item["file"]

        for source in item.get(
            "sources",
            [],
        ):

            source_files[source].append(
                file_name
            )

        for field in item.get(
            "fields",
            [],
        ):

            field_files[field].append(
                file_name
            )

        for url in item.get(
            "urls",
            [],
        ):

            if url not in all_urls:
                all_urls.append(url)

    source_files = {
        key: sorted(set(value))
        for key, value in source_files.items()
    }

    field_files = {
        key: sorted(set(value))
        for key, value in field_files.items()
    }

    return {

        "audit": {
            "name": "NICK V3 DATA SOURCE AUDIT",
            "version": "2.0",
            "generated_at": utc_now(),
        },

        "project": {
            "root": str(PROJECT_ROOT),
            "python_files_scanned": len(files),
            "excluded_backups": True,
            "excluded_audit_engine": True,
        },

        "detected_sources": source_files,

        "detected_fields": field_files,

        "external_urls": sorted(
            all_urls
        ),

        "architecture_target": {

            "universe": {
                "primary": "nasdaq_trader",
            },

            "fundamentals": {
                "primary": "sec",
                "secondary": "yahoo_finance",
            },

            "market": {
                "primary": "yahoo_finance",
                "secondary": "polygon",
                "fallback": "stooq",
            },

            "valuation": {
                "primary": "derived",
                "secondary": "yahoo_finance",
            },

            "news": {
                "primary": "rss",
                "secondary": "finnhub",
            },

            "macro": {
                "primary": "fred",
            },
        },
    }


def print_report(report):

    print("")
    print("=" * 90)
    print("NICK V3 — DATA SOURCE AUDIT V2")
    print("=" * 90)
    print("")

    print(
        "Python files scanned :",
        report["project"]["python_files_scanned"],
    )

    print(
        "Backup directories excluded :",
        report["project"]["excluded_backups"],
    )

    print(
        "Audit engine excluded :",
        report["project"]["excluded_audit_engine"],
    )

    print("")
    print(
        "---------------- DETECTED SOURCES ----------------"
    )

    sources = report["detected_sources"]

    for source, files in sorted(
        sources.items()
    ):

        print(
            f"{source:<20} : "
            f"{len(files):>4} file(s)"
        )

    print("")
    print(
        "---------------- TARGET ARCHITECTURE ----------------"
    )

    for domain, config in report[
        "architecture_target"
    ].items():

        print(
            f"{domain:<15} : {config}"
        )

    print("")
    print("=" * 90)
    print("AUDIT COMPLETE")
    print("=" * 90)
    print("")


def main():

    report = build_report()

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print_report(report)

    print(
        "Report:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()
