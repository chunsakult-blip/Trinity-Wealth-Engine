from __future__ import annotations

import ast
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "audits"
    / "nick_v3_production_provider_audit.json"
)


# ======================================================================
# EXCLUSIONS
# ======================================================================

EXCLUDED_PARTS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "site-packages",
    "tests",
    "test",
}

EXCLUDED_PREFIXES = (
    "_ATLAS_BACKUP_",
    "_backup_",
    "backup_",
)


# ======================================================================
# PROVIDER SIGNATURES
# ======================================================================

PROVIDER_MODULES = {
    "yahoo_finance": {
        "yfinance",
        "yahooquery",
    },

    "sec": {
        "sec",
    },

    "fred": {
        "fredapi",
    },

    "nasdaq_trader": {
        "urllib",
        "httpx",
        "requests",
    },

    "alpha_vantage": {
        "alpha_vantage",
    },

    "finnhub": {
        "finnhub",
    },

    "fmp": {
        "fmp",
    },

    "polygon": {
        "polygon",
    },

    "stooq": {
        "stooq",
    },
}


URL_SIGNATURES = {
    "nasdaq_trader": [
        "nasdaqtrader.com",
    ],

    "yahoo_finance": [
        "finance.yahoo.com",
        "query1.finance.yahoo.com",
        "feeds.finance.yahoo.com",
    ],

    "fred": [
        "api.stlouisfed.org",
        "fred.stlouisfed.org",
    ],

    "sec": [
        "sec.gov",
        "data.sec.gov",
    ],

    "alpha_vantage": [
        "alphavantage.co",
    ],

    "finnhub": [
        "finnhub.io",
    ],

    "fmp": [
        "financialmodelingprep.com",
    ],

    "polygon": [
        "polygon.io",
    ],

    "stooq": [
        "stooq.com",
    ],
}


# ======================================================================
# HELPERS
# ======================================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def relative(path: Path) -> str:

    try:
        return str(
            path.relative_to(PROJECT_ROOT)
        )

    except ValueError:
        return str(path)


def is_production_file(path: Path) -> bool:

    parts = {
        part.lower()
        for part in path.parts
    }

    if parts & EXCLUDED_PARTS:
        return False

    for part in path.parts:

        for prefix in EXCLUDED_PREFIXES:

            if part.startswith(prefix):
                return False

    return True


def provider_from_module(module: str):

    module = module.lower().strip()

    for provider, modules in PROVIDER_MODULES.items():

        for signature in modules:

            if (
                module == signature
                or module.startswith(
                    signature + "."
                )
            ):
                return provider

    return None


def provider_from_url(url: str):

    lowered = url.lower()

    for provider, signatures in URL_SIGNATURES.items():

        for signature in signatures:

            if signature in lowered:
                return provider

    return None


def extract_constant_urls(tree):

    urls = []

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Constant,
        ):

            value = node.value

            if not isinstance(
                value,
                str,
            ):
                continue

            if (
                value.startswith(
                    "http://"
                )
                or value.startswith(
                    "https://"
                )
            ):

                urls.append(value)

    return sorted(
        set(urls)
    )


# ======================================================================
# AST ANALYSIS
# ======================================================================

def analyze_file(path: Path):

    try:

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except Exception as exc:

        return {
            "file": relative(path),
            "read_error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    try:

        tree = ast.parse(
            text,
            filename=str(path),
        )

    except SyntaxError as exc:

        return {
            "file": relative(path),
            "syntax_error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    imports = []
    providers = set()
    urls = []
    url_providers = set()

    # --------------------------------------------------------------
    # IMPORTS
    # --------------------------------------------------------------

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                module = alias.name

                imports.append(module)

                provider = provider_from_module(
                    module
                )

                if provider:
                    providers.add(provider)

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            module = node.module or ""

            imports.append(module)

            provider = provider_from_module(
                module
            )

            if provider:
                providers.add(provider)

    # --------------------------------------------------------------
    # URLS
    # --------------------------------------------------------------

    urls = extract_constant_urls(
        tree
    )

    for url in urls:

        provider = provider_from_url(
            url
        )

        if provider:
            url_providers.add(
                provider
            )

    providers.update(
        url_providers
    )

    return {
        "file": relative(path),
        "providers": sorted(providers),
        "imports": sorted(set(imports)),
        "urls": urls,
        "url_providers": sorted(
            url_providers
        ),
    }


# ======================================================================
# SCAN
# ======================================================================

def scan():

    files = []

    for path in sorted(
        PROJECT_ROOT.rglob("*.py")
    ):

        if not is_production_file(
            path
        ):
            continue

        result = analyze_file(
            path
        )

        files.append(
            result
        )

    return files


# ======================================================================
# REPORT
# ======================================================================

def build_report():

    files = scan()

    provider_files = defaultdict(list)
    provider_urls = defaultdict(list)

    syntax_errors = []

    for item in files:

        if "syntax_error" in item:

            syntax_errors.append(item)
            continue

        for provider in item.get(
            "providers",
            [],
        ):

            provider_files[
                provider
            ].append(
                item["file"]
            )

        for provider in item.get(
            "url_providers",
            [],
        ):

            provider_urls[
                provider
            ].extend(
                item.get(
                    "urls",
                    [],
                )
            )

    provider_files = {
        provider: sorted(
            set(files)
        )
        for provider, files
        in provider_files.items()
    }

    provider_urls = {
        provider: sorted(
            set(urls)
        )
        for provider, urls
        in provider_urls.items()
    }

    # --------------------------------------------------------------
    # ARCHITECTURE STATUS
    # --------------------------------------------------------------

    production_provider_count = (
        len(provider_files)
    )

    yahoo_files = len(
        provider_files.get(
            "yahoo_finance",
            [],
        )
    )

    sec_files = len(
        provider_files.get(
            "sec",
            [],
        )
    )

    fred_files = len(
        provider_files.get(
            "fred",
            [],
        )
    )

    architecture_status = {
        "production_python_files": len(files),

        "production_provider_count":
            production_provider_count,

        "yahoo_finance_files":
            yahoo_files,

        "sec_files":
            sec_files,

        "fred_files":
            fred_files,

        "multi_provider_architecture":
            production_provider_count > 1,

        "requires_provider_registry":
            production_provider_count > 1,

        "requires_data_provenance":
            True,

        "requires_source_priority":
            True,
    }

    # --------------------------------------------------------------
    # TARGET
    # --------------------------------------------------------------

    target_architecture = {

        "universe": {
            "primary": "Nasdaq Trader",
            "role":
                "US listed equity discovery",
        },

        "fundamentals": {
            "primary": "SEC",
            "secondary": "Yahoo Finance",
            "role":
                "Auditable financial statements",
        },

        "market": {
            "primary": "Yahoo Finance",
            "secondary": None,
            "role":
                "Historical and current market data",
        },

        "macro": {
            "primary": "FRED",
            "secondary": None,
            "role":
                "Official macroeconomic series",
        },

        "news": {
            "primary": None,
            "secondary": None,
            "role":
                "Catalyst and event intelligence",
        },

        "valuation": {
            "primary": None,
            "secondary": None,
            "role":
                "Point-in-time valuation metrics",
        },

        "provenance": {
            "required": True,

            "minimum_fields": [
                "provider",
                "source_url",
                "retrieved_at",
                "ticker",
                "period_end",
                "field",
                "raw_value",
                "normalized_value",
            ],
        },
    }

    return {

        "audit": {
            "name":
                "NICK V3 PRODUCTION PROVIDER AUDIT",

            "version":
                "2.0",

            "generated_at":
                utc_now(),
        },

        "project": {
            "root":
                str(PROJECT_ROOT),

            "production_python_files":
                len(files),
        },

        "detected_production_providers":
            provider_files,

        "provider_urls":
            provider_urls,

        "architecture_status":
            architecture_status,

        "target_architecture":
            target_architecture,

        "syntax_errors":
            syntax_errors,

        "files":
            files,
    }


# ======================================================================
# PRINT
# ======================================================================

def print_report(report):

    print("")
    print("=" * 90)
    print(
        "NICK V3 — PRODUCTION PROVIDER AUDIT"
    )
    print("=" * 90)
    print("")

    project = report[
        "project"
    ]

    print(
        "Production Python files :",
        project[
            "production_python_files"
        ],
    )

    print("")

    print(
        "---------------- PRODUCTION PROVIDERS ----------------"
    )

    providers = report[
        "detected_production_providers"
    ]

    if not providers:

        print(
            "No production providers detected."
        )

    else:

        for provider, files in sorted(
            providers.items()
        ):

            print(
                f"{provider:<20} : "
                f"{len(files):>4} file(s)"
            )

    print("")

    print(
        "---------------- ARCHITECTURE STATUS ----------------"
    )

    status = report[
        "architecture_status"
    ]

    for key, value in status.items():

        print(
            f"{key:<35} : {value}"
        )

    print("")

    print(
        "---------------- PROVIDER FILES ----------------"
    )

    for provider, files in sorted(
        providers.items()
    ):

        print("")
        print(
            f"[{provider}]"
        )

        for file_name in files:

            print(
                f"  {file_name}"
            )

    print("")

    print(
        "---------------- SYNTAX ----------------"
    )

    errors = report[
        "syntax_errors"
    ]

    if not errors:

        print(
            "OK — no syntax errors."
        )

    else:

        for error in errors:

            print(
                error
            )

    print("")
    print("=" * 90)
    print("AUDIT COMPLETE")
    print("=" * 90)
    print("")
    print(
        "Report:",
        OUTPUT_PATH,
    )


# ======================================================================
# MAIN
# ======================================================================

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

    print_report(
        report
    )


if __name__ == "__main__":
    main()
