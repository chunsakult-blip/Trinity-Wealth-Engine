"""Typed Fixtures for Golden-Path Testing"""
from typing import Literal

from schemas.briefing_book_schemas import (
    SourceRecord,
    InvestigativeBriefingBookDraft,
    BriefingEvidenceBundle,
    ScenarioRecord,
    AssetImpactRecord,
    EvidenceItem,
    MacroAutopsySnapshot,
    FinancialAutopsySnapshotRef,
    VisualEvidenceDirective,
    NotebookLMPromptRecord,
)
from schemas.market_data_schemas import MacroObservation

def make_valid_source(source_id: str = "src-1", group: str = "group_1") -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        original_title=f"Sample Title for {source_id}",
        publisher="Valid Publisher",
        published_at="2026-07-20",
        host="test.com",
        ingested_at="2026-07-24T10:00:00",
        url=f"https://test.com/{source_id}",
        independence_key=group,
        verification_status="verified",
    )

def make_valid_macro_observation(category: Literal["inflation", "rates", "energy", "equity", "sector", "commodity", "fx", "yield", "other"] = "inflation") -> MacroObservation:
    sid = f"MOCK_SERIES_{category.upper()}"
    return MacroObservation(
        series_id=sid,
        category=category,
        label=f"Mock {category}",
        value=100.0,
        unit="Index",
        observed_at="2026-07-23",
        provider="Mock Provider",
    )

def make_valid_financial_snapshot() -> FinancialAutopsySnapshotRef:
    return FinancialAutopsySnapshotRef(
        symbol="AAPL",
        status="success",
        currency="USD",
        source="Mock Source",
        periods=[{"fiscal_period_end": "2026-12-31"}],
        market_cap="3T",
        revenue="400B",
        net_income="100B",
        fcf="100B",
        total_debt="100B",
        health_notes="Healthy",
    )

def make_valid_briefing_draft() -> InvestigativeBriefingBookDraft:
    return InvestigativeBriefingBookDraft(
        title="Golden Path Draft",
        executive_summary="This is a valid golden path draft with value 100.0 [E01].",
        causality_scenarios=[
            ScenarioRecord(
                scenario_id="SCENARIO_1",
                name="Base Scenario",
                description="Everything stays the same.",
                probability_pct=30.0,
                trigger_conditions=["No news > 100"],
                falsification_triggers=["Any news > 200"],
                evidence_ids=["E01"],
                threshold_basis="Historical average",
            ),
            ScenarioRecord(
                scenario_id="SCENARIO_2",
                name="Upside",
                description="Things go well.",
                probability_pct=40.0,
                trigger_conditions=["Good news > 100"],
                falsification_triggers=["Bad news > 200"],
                evidence_ids=["E02"],
                threshold_basis="Historical average",
            ),
            ScenarioRecord(
                scenario_id="SCENARIO_3",
                name="Downside",
                description="Things go poorly.",
                probability_pct=30.0,
                trigger_conditions=["Bad news > 100"],
                falsification_triggers=["Good news > 200"],
                evidence_ids=["E03"],
                threshold_basis="Historical average",
            ),
        ],
        asset_impacts=[
            AssetImpactRecord(
                symbol_or_name="AAPL",
                impact_type="direct_upside",
                reasoning="Strong earnings.",
                risk_factors=["Supply chain"],
                invalidation_conditions=["Recession"],
                evidence_ids=["E01"],
            )
        ],
        bull_case="Bullish because...",
        bear_case="Bearish because...",
        falsification_triggers=["Yield curve inversion"],
        act1_script="Act 1 Script",
        act2_script="Act 2 Script",
        act3_script="Act 3 Script",
        visual_directives=[
            VisualEvidenceDirective(
                visual_id="V01", act="Act I", title="Chart 1", chart_type="Line",
                series_keys=["AAPL"], date_range="2026-07-01 ถึง 2026-07-21", sources=["Yahoo"], annotation="Text",
                evidence_ids=["E01"], data_mode="provider_series"
            ),
            VisualEvidenceDirective(
                visual_id="V02", act="Act II", title="Chart 2", chart_type="Table",
                series_keys=["EVIDENCE_TABLE"], date_range="2026-07-01 ถึง 2026-07-21", sources=["Report"], annotation="Text",
                evidence_ids=["E02"], data_mode="evidence_table"
            ),
            VisualEvidenceDirective(
                visual_id="V03", act="Act III", title="Chart 3", chart_type="Line",
                series_keys=["MSFT"], date_range="2026-07-01 ถึง 2026-07-21", sources=["Yahoo"], annotation="Text",
                evidence_ids=["E03"], data_mode="provider_series"
            ),
        ],
        notebooklm_prompts=[
            NotebookLMPromptRecord(prompt_id="P01", prompt_type="BLIND_SPOT", question_or_prompt="Q1", expected_output_format="F1"),
            NotebookLMPromptRecord(prompt_id="P02", prompt_type="SOCRATIC", question_or_prompt="Q2", expected_output_format="F2"),
            NotebookLMPromptRecord(prompt_id="P03", prompt_type="FEYNMAN", question_or_prompt="Q3", expected_output_format="F3"),
            NotebookLMPromptRecord(prompt_id="P04", prompt_type="RESEARCH", question_or_prompt="Q4", expected_output_format="F4"),
            NotebookLMPromptRecord(prompt_id="P05", prompt_type="RESEARCH", question_or_prompt="Q5", expected_output_format="F5"),
        ],
    )

def make_valid_evidence_bundle(mode: Literal["macro", "stock", "mixed"] = "macro") -> BriefingEvidenceBundle:
    return BriefingEvidenceBundle(
        pitch_id="pitch-golden-path",
        investigation_mode=mode,
        sources=[make_valid_source("src-1", "group_1"), make_valid_source("src-2", "group_2")],
        evidence_items=[
            EvidenceItem(
                evidence_id="E01",
                source_ids=["src-1"],
                claim="Claim 1 100.0",
                classification="verified_fact",
                value=100.0,
            ),
            EvidenceItem(
                evidence_id="E02",
                source_ids=["src-2"],
                claim="Claim 2",
                classification="verified_fact",
            ),
            EvidenceItem(
                evidence_id="E03",
                source_ids=["src-1"],
                claim="Claim 3",
                classification="verified_fact",
            ),
        ],
        macro_snapshot=MacroAutopsySnapshot(
            observations=[
                make_valid_macro_observation("inflation"),
                make_valid_macro_observation("rates"),
            ],
            is_complete=True,
            unavailable_reasons=[],
        ) if mode in {"macro", "mixed"} else None,
        financial_snapshots=[
            make_valid_financial_snapshot()
        ] if mode in {"stock", "mixed"} else [],
    )
