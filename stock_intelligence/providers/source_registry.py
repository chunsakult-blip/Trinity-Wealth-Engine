from __future__ import annotations

"""
NICK V3 — DATA SOURCE REGISTRY

Single source of truth for external market/intelligence providers.

This module does NOT perform network requests.
It only defines provider roles, authority and fallback priority.
"""

from dataclasses import dataclass
from enum import Enum


class SourceAuthority(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"
    DISCOVERY = "discovery"


@dataclass(frozen=True)
class DataSource:
    name: str
    authority: SourceAuthority
    role: str
    enabled: bool = True
    auditable: bool = True


# ======================================================================
# UNIVERSE
# ======================================================================

UNIVERSE_SOURCES = (
    DataSource(
        name="nasdaq_trader",
        authority=SourceAuthority.PRIMARY,
        role="US listed security discovery",
    ),
)


# ======================================================================
# FUNDAMENTALS
# ======================================================================

FUNDAMENTAL_SOURCES = (
    DataSource(
        name="sec",
        authority=SourceAuthority.PRIMARY,
        role="authoritative company filings and financial statements",
    ),
    DataSource(
        name="yahoo_finance",
        authority=SourceAuthority.SECONDARY,
        role="normalized financial statement fallback",
    ),
)


# ======================================================================
# MARKET DATA
# ======================================================================

MARKET_SOURCES = (
    DataSource(
        name="yahoo_finance",
        authority=SourceAuthority.PRIMARY,
        role="daily OHLCV market history",
    ),
    DataSource(
        name="polygon",
        authority=SourceAuthority.SECONDARY,
        role="market data cross-check / expansion source",
    ),
    DataSource(
        name="stooq",
        authority=SourceAuthority.FALLBACK,
        role="market history fallback",
    ),
)


# ======================================================================
# VALUATION
# ======================================================================

VALUATION_SOURCES = (
    DataSource(
        name="derived",
        authority=SourceAuthority.PRIMARY,
        role="deterministic valuation metrics derived from normalized data",
    ),
    DataSource(
        name="yahoo_finance",
        authority=SourceAuthority.SECONDARY,
        role="supplementary point-in-time valuation fields",
    ),
)


# ======================================================================
# NEWS
# ======================================================================

NEWS_SOURCES = (
    DataSource(
        name="rss",
        authority=SourceAuthority.PRIMARY,
        role="research and catalyst discovery",
    ),
    DataSource(
        name="finnhub",
        authority=SourceAuthority.SECONDARY,
        role="supplementary market/news intelligence",
    ),
)


# ======================================================================
# MACRO
# ======================================================================

MACRO_SOURCES = (
    DataSource(
        name="fred",
        authority=SourceAuthority.PRIMARY,
        role="US macroeconomic time series",
    ),
)


# ======================================================================
# MASTER REGISTRY
# ======================================================================

SOURCE_REGISTRY = {
    "universe": UNIVERSE_SOURCES,
    "fundamentals": FUNDAMENTAL_SOURCES,
    "market": MARKET_SOURCES,
    "valuation": VALUATION_SOURCES,
    "news": NEWS_SOURCES,
    "macro": MACRO_SOURCES,
}


def get_sources(domain: str) -> tuple[DataSource, ...]:
    return SOURCE_REGISTRY.get(domain, ())


def get_primary_source(domain: str) -> DataSource | None:
    sources = get_sources(domain)

    for source in sources:
        if (
            source.enabled
            and source.authority == SourceAuthority.PRIMARY
        ):
            return source

    return None


def validate_registry() -> list[str]:
    errors: list[str] = []

    for domain, sources in SOURCE_REGISTRY.items():

        enabled = [
            source
            for source in sources
            if source.enabled
        ]

        if not enabled:
            errors.append(
                f"{domain}: no enabled source"
            )
            continue

        primary_count = sum(
            1
            for source in enabled
            if source.authority == SourceAuthority.PRIMARY
        )

        if primary_count != 1:
            errors.append(
                f"{domain}: expected exactly one primary source, "
                f"found {primary_count}"
            )

    return errors


if __name__ == "__main__":

    print("")
    print("=" * 80)
    print("NICK V3 — SOURCE REGISTRY")
    print("=" * 80)
    print("")

    for domain, sources in SOURCE_REGISTRY.items():

        print(f"[{domain}]")

        for source in sources:

            print(
                f"  {source.name:<18} "
                f"{source.authority.value:<10} "
                f"{source.role}"
            )

        print("")

    errors = validate_registry()

    if errors:

        print("REGISTRY ERRORS")

        for error in errors:
            print(" -", error)

        raise SystemExit(1)

    print("REGISTRY STATUS: VALID")
    print("")
