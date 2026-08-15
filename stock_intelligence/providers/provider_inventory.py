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
    / "nick_v3_provider_inventory.json"
)


# ======================================================================
# PROVIDER DEFINITIONS
# ======================================================================

PROVIDERS = {

    "yahoo_finance": {
        "domain": "market/fundamentals",
        "authority": "primary+secondary",
        "registry_status": "CANONICAL",
        "imports": (
            "yfinance",
            "yahooquery",
        ),
        "signatures": (
            "finance.yahoo.com",
            "query1.finance.yahoo.com",
            "query2.finance.yahoo.com",
            "yf.Ticker",
            "yf.download",
            "yfinance.Ticker",
        ),
    },

    "sec": {
        "domain": "fundamentals",
        "authority": "primary",
        "registry_status": "CANONICAL",
        "imports": (
            "sec",
            "sec_edgar",
            "sec_edgar_downloader",
        ),
        "signatures": (
            "sec.gov",
            "data.sec.gov",
            "www.sec.gov",
            "companyfacts",
            "submissions",
            "sec_companyfacts",
        ),
    },

    "nasdaq_trader": {
        "domain": "universe",
        "authority": "primary",
        "registry_status": "CANONICAL",
        "imports": (),
        "signatures": (
            "nasdaqtrader.com",
            "nasdaqlisted.txt",
            "otherlisted.txt",
        ),
    },

    "polygon": {
        "domain": "market",
        "authority": "secondary",
        "registry_status": "CANONICAL",
        "imports": (
            "polygon",
            "polygon-api-client",
        ),
        "signatures": (
            "polygon.io",
            "api.polygon.io",
            "polygon.rest",
            "polygon.client",
        ),
    },

    "stooq": {
        "domain": "market",
        "authority": "fallback",
        "registry_status": "CANONICAL",
        "imports": (),
        "signatures": (
            "stooq.com",
        ),
    },

    "fred": {
        "domain": "macro",
        "authority": "primary",
        "registry_status": "CANONICAL",
        "imports": (
            "fredapi",
            "pandas_datareader",
        ),
        "signatures": (
            "fred.stlouisfed.org",
            "api.stlouisfed.org",
            "FredReader",
        ),
    },

    "rss": {
        "domain": "news",
        "authority": "primary",
        "registry_status": "CANONICAL",
        "imports": (
            "feedparser",
        ),
        "signatures": (
            "feedparser.parse",
            "feeds.finance",
            ".rss",
            "/rss",
            "rss.xml",
        ),
    },

    "finnhub": {
        "domain": "news",
        "authority": "secondary",
        "registry_status": "CANONICAL",
        "imports": (
            "finnhub",
        ),
        "signatures": (
            "finnhub.io",
            "finnhub.Client",
        ),
    },

    "fmp": {
        "domain": "unknown",
        "authority": "unassigned",
        "registry_status": "REVIEW_REQUIRED",
        "imports": (
            "fmp",
            "financialmodelingprep",
        ),
        "signatures": (
            "financialmodelingprep.com",
            "financialmodelingprep",
            "fmpcloud",
        ),
    },

    "alpha_vantage": {
        "domain": "unknown",
        "authority": "unassigned",
        "registry_status": "REVIEW_REQUIRED",
        "imports": (
            "alpha_vantage",
        ),
        "signatures": (
            "alphavantage.co",
            "alpha_vantage",
            "AlphaVantage",
        ),
    },
}


# ======================================================================
# PATH GOVERNANCE
# ======================================================================

EXCLUDED_EXACT_DIRS = {
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".git",
    "node_modules",
    "backup",
    "backups",
    "tests",
    "test",
}


EXCLUDED_PATH_MARKERS = (
    "_atlas_backup_",
    "atlas_backup",
    "_backup_",
    "backup_before_",
    "/backup/",
    "\\backup\\",
    "/backups/",
    "\\backups\\",
    "/tests/",
    "\\tests\\",
)


GOVERNANCE_FILES = {
    "data_source_audit.py",
    "production_provider_audit.py",
    "provider_inventory.py",
    "source_registry.py",
}


LEGACY_MARKERS = (
    "legacy",
    "deprecated",
    "obsolete",
    "archive",
    "archived",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative_path(path: Path) -> str:
    return str(
        path.relative_to(PROJECT_ROOT)
    )


def normalized_path(path: Path) -> str:
    return relative_path(path).replace(
        "\\",
        "/",
    ).lower()


def is_excluded_directory(path: Path) -> bool:

    parts = {
        part.lower()
        for part in path.relative_to(
            PROJECT_ROOT
        ).parts
    }

    if parts.intersection(
        EXCLUDED_EXACT_DIRS
    ):
        return True

    normalized = normalized_path(path)

    return any(
        marker in normalized
        for marker in EXCLUDED_PATH_MARKERS
    )


def is_governance_file(path: Path) -> bool:

    return (
        path.name.lower()
        in GOVERNANCE_FILES
    )


def is_legacy_path(path: Path) -> bool:

    normalized = normalized_path(path)

    return any(
        marker in normalized
        for marker in LEGACY_MARKERS
    )


# ======================================================================
# AST IMPORT DETECTION
# ======================================================================

def extract_imports(
    tree: ast.AST,
) -> set[str]:

    imports = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                imports.add(
                    alias.name
                    .split(".")[0]
                    .lower()
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            if node.module:

                imports.add(
                    node.module
                    .split(".")[0]
                    .lower()
                )

    return imports


def detect_import_providers(
    imports: set[str],
) -> set[str]:

    detected = set()

    for provider, config in (
        PROVIDERS.items()
    ):

        expected = {
            item.lower()
            for item in config[
                "imports"
            ]
        }

        if imports.intersection(
            expected
        ):

            detected.add(provider)

    return detected


# ======================================================================
# SIGNATURE DETECTION
# ======================================================================

def detect_signature_providers(
    text: str,
) -> set[str]:

    lowered = text.lower()

    detected = set()

    for provider, config in (
        PROVIDERS.items()
    ):

        for signature in config[
            "signatures"
        ]:

            if (
                signature.lower()
                in lowered
            ):

                detected.add(provider)
                break

    return detected


# ======================================================================
# HTTP/API DETECTION
# ======================================================================

def detect_http_usage(
    text: str,
) -> bool:

    lowered = text.lower()

    signatures = (
        "requests.get(",
        "requests.post(",
        "httpx.get(",
        "httpx.post(",
        "urllib.request",
        "session.get(",
        "session.post(",
        "client.get(",
        "client.post(",
    )

    return any(
        item in lowered
        for item in signatures
    )


# ======================================================================
# FILE CLASSIFICATION
# ======================================================================

def classify_file(
    path: Path,
) -> str:

    if is_governance_file(path):
        return "GOVERNANCE"

    if is_legacy_path(path):
        return "LEGACY"

    normalized = normalized_path(path)

    if (
        "/tests/" in normalized
        or normalized.startswith("tests/")
        or "/test/" in normalized
        or normalized.startswith("test/")
        or path.name.lower().startswith(
            "test_"
        )
        or path.name.lower().endswith(
            "_test.py"
        )
    ):
        return "TEST"

    parts = {
        part.lower()
        for part in path.relative_to(
            PROJECT_ROOT
        ).parts
    }

    if (
        "stock_intelligence"
        in parts
        or "tools"
        in parts
        or "core"
        in parts
        or "agents"
        in parts
        or "scripts"
        in parts
    ):
        return "PRODUCTION_CANDIDATE"

    if (
        "docs" in parts
        or "examples" in parts
    ):
        return "REFERENCE"

    return "UNKNOWN"


# ======================================================================
# FILE SCAN
# ======================================================================

def scan_file(
    path: Path,
) -> dict | None:

    try:

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except Exception:

        return None

    try:

        tree = ast.parse(text)

        imports = extract_imports(tree)

    except SyntaxError:

        imports = set()

    import_providers = (
        detect_import_providers(
            imports
        )
    )

    signature_providers = (
        detect_signature_providers(
            text
        )
    )

    providers = sorted(
        import_providers.union(
            signature_providers
        )
    )

    if not providers:
        return None

    return {
        "file": relative_path(path),

        "classification":
            classify_file(path),

        "providers":
            providers,

        "import_detected":
            sorted(import_providers),

        "signature_detected":
            sorted(signature_providers),

        "http_usage":
            detect_http_usage(text),
    }


def scan_project():

    results = []

    scanned = 0

    excluded = {
        "backup": 0,
        "tests": 0,
        "governance": 0,
        "other": 0,
    }

    for path in sorted(
        PROJECT_ROOT.rglob("*.py")
    ):

        normalized = normalized_path(
            path
        )

        if is_excluded_directory(path):

            if (
                "test" in normalized
            ):
                excluded["tests"] += 1

            else:
                excluded["backup"] += 1

            continue

        if is_governance_file(path):

            excluded[
                "governance"
            ] += 1

            continue

        scanned += 1

        result = scan_file(path)

        if result:
            results.append(result)

    return results, {
        "python_files_scanned":
            scanned,

        "excluded":
            excluded,
    }


# ======================================================================
# INVENTORY
# ======================================================================

def build_inventory(
    files: list[dict],
):

    inventory = {}

    for provider in sorted(
        PROVIDERS
    ):

        provider_files = [
            item
            for item in files
            if provider
            in item["providers"]
        ]

        production = [
            item
            for item in provider_files
            if item["classification"]
            == "PRODUCTION_CANDIDATE"
        ]

        legacy = [
            item
            for item in provider_files
            if item["classification"]
            == "LEGACY"
        ]

        reference = [
            item
            for item in provider_files
            if item["classification"]
            == "REFERENCE"
        ]

        imports = [
            item
            for item in production
            if provider
            in item["import_detected"]
        ]

        http = [
            item
            for item in production
            if item["http_usage"]
        ]

        if imports or http:

            usage_status = (
                "ACTIVE_CANDIDATE"
            )

        elif production:

            usage_status = (
                "SIGNATURE_ONLY"
            )

        elif legacy:

            usage_status = (
                "LEGACY_ONLY"
            )

        elif reference:

            usage_status = (
                "REFERENCE_ONLY"
            )

        else:

            usage_status = (
                "NO_PRODUCTION_IMPLEMENTATION"
            )

        config = PROVIDERS[
            provider
        ]

        inventory[provider] = {

            "domain":
                config["domain"],

            "authority":
                config["authority"],

            "registry_status":
                config["registry_status"],

            "usage_status":
                usage_status,

            "production_candidate_files":
                sorted(
                    item["file"]
                    for item in production
                ),

            "actual_import_files":
                sorted(
                    item["file"]
                    for item in imports
                ),

            "http_usage_files":
                sorted(
                    item["file"]
                    for item in http
                ),

            "legacy_files":
                sorted(
                    item["file"]
                    for item in legacy
                ),

            "reference_files":
                sorted(
                    item["file"]
                    for item in reference
                ),

            "file_count":
                len(provider_files),
        }

    return inventory


# ======================================================================
# ARCHITECTURE GAPS
# ======================================================================

def build_architecture_gaps(
    inventory,
):

    gaps = []

    sec = inventory.get(
        "sec",
        {},
    )

    if (
        sec.get(
            "usage_status"
        )
        == "NO_PRODUCTION_IMPLEMENTATION"
    ):

        gaps.append(
            {
                "severity": "HIGH",
                "provider": "sec",
                "domain": "fundamentals",
                "expected_role":
                    "PRIMARY",
                "finding":
                    "SEC is canonical in registry but has no production implementation.",
                "action":
                    "Build canonical SEC adapter before large-scale fundamental ingestion.",
            }
        )

    for provider in (
        "polygon",
        "stooq",
        "finnhub",
    ):

        data = inventory.get(
            provider,
            {},
        )

        if (
            data.get(
                "usage_status"
            )
            == "NO_PRODUCTION_IMPLEMENTATION"
        ):

            gaps.append(
                {
                    "severity": "INFO",
                    "provider": provider,
                    "domain":
                        data.get(
                            "domain"
                        ),
                    "expected_role":
                        data.get(
                            "authority"
                        ),
                    "finding":
                        "Canonical registry role exists but no production implementation was detected.",
                    "action":
                        "Implement only if required by fallback/cross-check policy.",
                }
            )

    return gaps


# ======================================================================
# REPORT
# ======================================================================

def build_report():

    files, project = (
        scan_project()
    )

    inventory = build_inventory(
        files
    )

    gaps = (
        build_architecture_gaps(
            inventory
        )
    )

    return {

        "inventory": {

            "name":
                "NICK V3 HARDENED PROVIDER INVENTORY",

            "version":
                "1.2",

            "generated_at":
                utc_now(),
        },

        "governance": {

            "tests_excluded":
                True,

            "backups_excluded":
                True,

            "governance_files_excluded":
                True,

            "self_inventory_excluded":
                True,

            "api_calls_executed":
                False,

            "stock_ingestion_executed":
                False,
        },

        "project":
            project,

        "providers":
            inventory,

        "architecture_gaps":
            gaps,
    }


# ======================================================================
# PRINT
# ======================================================================

def print_report(
    report,
):

    print("")
    print("=" * 100)
    print(
        "NICK V3 — HARDENED PROVIDER INVENTORY V1.2"
    )
    print("=" * 100)
    print("")

    project = report[
        "project"
    ]

    print(
        "Python files scanned :",
        project[
            "python_files_scanned"
        ],
    )

    print(
        "Tests excluded       :",
        report[
            "governance"
        ][
            "tests_excluded"
        ],
    )

    print(
        "Backups excluded     :",
        report[
            "governance"
        ][
            "backups_excluded"
        ],
    )

    print(
        "Governance excluded  :",
        report[
            "governance"
        ][
            "governance_files_excluded"
        ],
    )

    print("")

    print(
        "---------------- PROVIDER STATUS ----------------"
    )

    for provider, data in (
        report[
            "providers"
        ].items()
    ):

        print(
            f"{provider:<20} "
            f"{data['usage_status']:<32} "
            f"{data['file_count']:>3} file(s)"
        )

    print("")

    print(
        "---------------- ARCHITECTURE GAPS ----------------"
    )

    gaps = report[
        "architecture_gaps"
    ]

    if not gaps:

        print(
            "NONE"
        )

    else:

        for gap in gaps:

            print(
                f"[{gap['severity']}] "
                f"{gap['provider']}"
            )

            print(
                f"  domain : "
                f"{gap['domain']}"
            )

            print(
                f"  role   : "
                f"{gap['expected_role']}"
            )

            print(
                f"  finding: "
                f"{gap['finding']}"
            )

            print(
                f"  action : "
                f"{gap['action']}"
            )

            print("")

    print(
        "---------------- REVIEW ----------------"
    )

    for provider in (
        "fmp",
        "alpha_vantage",
    ):

        data = report[
            "providers"
        ][provider]

        print(
            f"{provider:<20}"
            f"{data['usage_status']}"
        )

    print("")

    print("=" * 100)
    print(
        "HARDENED INVENTORY COMPLETE"
    )
    print("=" * 100)
    print("")


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

    print(
        "Report:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()
