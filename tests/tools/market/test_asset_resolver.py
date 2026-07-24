"""Unit tests สำหรับ tools/market/asset_resolver.py"""
from unittest.mock import patch
import pytest
from tools.market.asset_resolver import (
    AssetClass,
    ResolvedAsset,
    resolve_asset,
    verify_asset_metadata,
    _VERIFY_CACHE,
)


def test_resolve_set_symbols_and_bk_suffix():
    # PTT in curated registry
    res_ptt = resolve_asset("PTT")
    assert res_ptt.asset_class == AssetClass.STOCK_TH
    assert res_ptt.provider_symbol == "PTT.BK"
    assert res_ptt.market == "TH"
    assert res_ptt.eligible_for_financial_autopsy is True

    # PTT.BK directly
    res_bk = resolve_asset("PTT.BK")
    assert res_bk.asset_class == AssetClass.STOCK_TH
    assert res_bk.provider_symbol == "PTT.BK"
    assert res_bk.eligible_for_financial_autopsy is True

    # DELTA
    res_delta = resolve_asset("DELTA")
    assert res_delta.asset_class == AssetClass.STOCK_TH
    assert res_delta.provider_symbol == "DELTA.BK"


def test_resolve_us_equities_and_aliases():
    # NVDA
    res_nvda = resolve_asset("NVDA")
    assert res_nvda.asset_class == AssetClass.STOCK_US
    assert res_nvda.provider_symbol == "NVDA"
    assert res_nvda.market == "US"
    assert res_nvda.eligible_for_financial_autopsy is True

    # BRK.B alias
    res_brk = resolve_asset("BRK.B")
    assert res_brk.asset_class == AssetClass.STOCK_US
    assert res_brk.provider_symbol == "BRK-B"
    assert res_brk.eligible_for_financial_autopsy is True


def test_resolve_etf():
    # QQQ
    res_qqq = resolve_asset("QQQ")
    assert res_qqq.asset_class == AssetClass.ETF
    assert res_qqq.provider_symbol == "QQQ"
    assert res_qqq.eligible_for_financial_autopsy is False


def test_resolve_commodities_and_indices_aliases():
    # OIL -> CL=F
    res_oil = resolve_asset("Oil")
    assert res_oil.asset_class == AssetClass.COMMODITY
    assert res_oil.provider_symbol == "CL=F"
    assert res_oil.eligible_for_financial_autopsy is False

    # SPX -> ^GSPC
    res_spx = resolve_asset("SPX")
    assert res_spx.asset_class == AssetClass.INDEX
    assert res_spx.provider_symbol == "^GSPC"
    assert res_spx.eligible_for_financial_autopsy is False

    # BTC
    res_btc = resolve_asset("BTC")
    assert res_btc.asset_class == AssetClass.CRYPTO
    assert res_btc.provider_symbol == "BTC-USD"
    assert res_btc.eligible_for_financial_autopsy is False


def test_resolve_offline_fallback():
    # UNKNOWN symbol in offline fallback
    res = resolve_asset("UNKNOWN_SYM_XYZ", market_hint="US", offline_fallback=True)
    assert res.asset_class == AssetClass.OTHER
    assert res.provider_symbol == "UNKNOWN_SYM_XYZ"
    assert res.market == "US"
    assert res.confidence == "low"
    assert res.eligible_for_financial_autopsy is False


@patch("tools.market.asset_resolver._fetch_yf_info_blocking")
def test_verify_asset_metadata_success(mock_fetch):
    _VERIFY_CACHE.clear()
    mock_fetch.return_value = {"quoteType": "EQUITY", "exchange": "NYQ", "symbol": "NEWCO"}
    res = verify_asset_metadata("NEWCO")
    assert res is not None
    assert res.asset_class == AssetClass.STOCK_US
    assert res.provider_symbol == "NEWCO"
    assert res.eligible_for_financial_autopsy is True

    # Test caching
    res_cached = verify_asset_metadata("NEWCO")
    assert res_cached == res
    assert mock_fetch.call_count == 1  # Called only once due to cache


@patch("tools.market.asset_resolver._fetch_yf_info_blocking")
def test_verify_asset_metadata_error_or_timeout(mock_fetch):
    from concurrent.futures import TimeoutError as FuturesTimeoutError
    _VERIFY_CACHE.clear()
    mock_fetch.side_effect = Exception("Network error")
    res = verify_asset_metadata("FAILCO")
    assert res is None

    _VERIFY_CACHE.clear()
    mock_fetch.side_effect = FuturesTimeoutError("Timed out")
    res2 = verify_asset_metadata("TIMEOUTCO")
    assert res2 is None
