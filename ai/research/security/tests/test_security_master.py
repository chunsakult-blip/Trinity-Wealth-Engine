from ai.research.security import (
    SecurityMaster,
    SecurityMasterRecord,
)


def sample_universe():
    return [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "exchange": "NASDAQ",
            "cik": 320193,
            "country": "US",
        },
        {
            "ticker": "BRK.B",
            "company_name": "Berkshire Hathaway Inc.",
            "exchange": "NYSE",
            "cik": 1067983,
            "country": "US",
        },
        {
            "ticker": "TESTW",
            "company_name": "Example Warrant",
            "exchange": "NASDAQ",
            "cik": 123456,
            "country": "US",
        },
        {
            "ticker": "TESTP",
            "company_name": "Example Preferred",
            "exchange": "NYSE",
            "cik": 123457,
            "country": "US",
        },
        {
            "ticker": "TESTF",
            "company_name": "Example ETF Fund",
            "exchange": "NYSE",
            "cik": 123458,
            "country": "US",
        },
        {
            "ticker": "O",
            "company_name": "Realty Income Corporation REIT",
            "exchange": "NYSE",
            "cik": 726728,
            "country": "US",
        },
    ]


def test_record_contract():
    records = SecurityMaster().build(sample_universe())

    assert records

    expected = {
        "security_id",
        "ticker",
        "company_name",
        "exchange",
        "cik",
        "country",
        "instrument_type",
        "classification_confidence",
        "investable_equity",
        "classification_reason",
        "source",
        "source_url",
        "identity_confidence",
        "identifiers",
        "evidence",
        "data_quality",
    }

    assert expected.issubset(records[0].keys())


def test_common_equity_is_investable():
    records = SecurityMaster().build(sample_universe())

    aapl = next(
        record
        for record in records
        if record["ticker"] == "AAPL"
    )

    assert aapl["instrument_type"] == "COMMON_EQUITY"
    assert aapl["investable_equity"] is True
    assert aapl["classification_confidence"] == "medium"
    assert aapl["identity_confidence"] == "high"
    assert aapl["data_quality"] == "good"


def test_special_instruments_are_excluded():
    records = SecurityMaster().build(sample_universe())

    warrant = next(
        record
        for record in records
        if record["ticker"] == "TESTW"
    )

    preferred = next(
        record
        for record in records
        if record["ticker"] == "TESTP"
    )

    fund = next(
        record
        for record in records
        if record["ticker"] == "TESTF"
    )

    assert warrant["investable_equity"] is False
    assert warrant["instrument_type"] == "WARRANT"

    assert preferred["investable_equity"] is False
    assert preferred["instrument_type"] == "PREFERRED_EQUITY"

    assert fund["investable_equity"] is False
    assert fund["instrument_type"] == "FUND_OR_ETF"


def test_reit_remains_investable():
    records = SecurityMaster().build(sample_universe())

    reit = next(
        record
        for record in records
        if record["ticker"] == "O"
    )

    assert reit["instrument_type"] == "REIT"
    assert reit["investable_equity"] is True


def test_security_id_is_deterministic():
    records = SecurityMaster().build(sample_universe())

    aapl = next(
        record
        for record in records
        if record["ticker"] == "AAPL"
    )

    assert (
        aapl["security_id"]
        == "US:NASDAQ:CIK0000320193:AAPL"
    )


def test_investable_only():
    master = SecurityMaster()

    records = master.build(sample_universe())

    investable = master.investable_only(records)

    tickers = {
        record["ticker"]
        for record in investable
    }

    assert "AAPL" in tickers
    assert "BRK.B" in tickers
    assert "O" in tickers

    assert "TESTW" not in tickers
    assert "TESTP" not in tickers
    assert "TESTF" not in tickers


def test_summary():
    master = SecurityMaster()

    records = master.build(sample_universe())

    summary = master.summarize(records)

    assert summary["total"] == 6
    assert summary["investable_equity"] == 3
    assert summary["non_investable"] == 3

    assert (
        summary["instrument_counts"]["COMMON_EQUITY"]
        == 2
    )

    assert (
        summary["instrument_counts"]["REIT"]
        == 1
    )


def test_invalid_records_are_skipped():
    master = SecurityMaster()

    records = master.build(
        [
            {
                "ticker": "",
                "company_name": "Invalid",
                "exchange": "NASDAQ",
                "cik": 123,
            },
            {
                "ticker": "VALID",
                "company_name": "Valid Company",
                "exchange": "NASDAQ",
                "cik": 456,
            },
        ]
    )

    assert len(records) == 1
    assert records[0]["ticker"] == "VALID"


def test_record_dataclass_export():
    master = SecurityMaster()

    records = master.build(
        [
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "exchange": "NASDAQ",
                "cik": 320193,
            }
        ]
    )

    record = SecurityMasterRecord(
        **records[0]
    )

    exported = record.to_dict()

    assert exported["ticker"] == "AAPL"
    assert exported["cik"] == 320193
    assert exported["source"] == "SEC"

