"""
ATLAS Intelligence Pipeline.

Execution chain:

ATLAS Request
    |
    v
Trinity Runner
    |
    v
Trinity Adapter
    |
    v
Research / Discovery
    |
    v
Financial Intelligence
    |
    v
Investment Decision
    |
    v
Evidence
    |
    v
Verification
    |
    v
Challenge
    |
    v
Reflection
    |
    v
Nick
"""

from __future__ import annotations

import uuid
from typing import Any

from ai.challenge.challenge_agent import (
    ChallengeAgent,
    DEFAULT_CHALLENGE_AGENT,
)
from ai.evidence.evidence_collector import (
    EvidenceCollector,
    DEFAULT_EVIDENCE_COLLECTOR,
)
from ai.integration.trinity_adapter import TrinityAdapter
from ai.integration.trinity_runner import (
    TrinityRunner,
    DEFAULT_TRINITY_RUNNER,
)
from ai.nick.nick import Nick
from ai.nick.portfolio_intelligence import (
    PortfolioCandidate,
    PortfolioIntelligence,
)
from ai.nick.portfolio_risk_guard import PortfolioRiskGuard
from ai.nick.portfolio_quality import PortfolioQualityEngine
from ai.research.investment.investment_bridge import InvestmentBridge
from ai.orchestration.research_orchestrator import ResearchOrchestrator
from ai.research.workers.us_stock_discovery_worker import (
    USStockDiscoveryWorker,
)
from ai.research.scout.us_stock_scout import USStockScout
from ai.research.financial.engine import FinancialIntelligenceEngine
from ai.research.investment.engine import InvestmentDecisionEngine

from ai.data.market.market_data_bridge import MarketDataBridge
from ai.reflection.reflection_agent import (
    ReflectionAgent,
    DEFAULT_REFLECTION_AGENT,
)
from ai.research.request import ResearchRequest
from ai.verification.fact_verifier import (
    FactVerifier,
    DEFAULT_FACT_VERIFIER,
)


class IntelligencePipeline:
    """
    Main ATLAS intelligence execution pipeline.

    ATLAS owns the intelligence lifecycle while Trinity remains
    the execution/research engine.

    Core graph:

        Trinity
            -> Research / Discovery
            -> Financial Intelligence
            -> Investment Decision
            -> Evidence
            -> Verification
            -> Challenge
            -> Reflection
            -> Nick
    """

    name = "ATLAS Intelligence Pipeline"

    def __init__(
        self,
        *,
        adapter: TrinityAdapter | None = None,
        runner: TrinityRunner | None = None,
        research: ResearchOrchestrator | None = None,
        financial: FinancialIntelligenceEngine | None = None,
        investment: InvestmentDecisionEngine | None = None,

        market_bridge: MarketDataBridge | None = None,
        evidence: EvidenceCollector | None = None,
        verifier: FactVerifier | None = None,
        challenger: ChallengeAgent | None = None,
        reflection: ReflectionAgent | None = None,
        nick: Nick | None = None,
        portfolio_intelligence: PortfolioIntelligence | None = None,
        portfolio_risk_guard: PortfolioRiskGuard | None = None,
        portfolio_quality_engine: PortfolioQualityEngine | None = None,
        investment_bridge: InvestmentBridge | None = None,
    ) -> None:

        self.runner = runner or DEFAULT_TRINITY_RUNNER
        self.adapter = adapter or TrinityAdapter()

        self.research = research or ResearchOrchestrator(
            workers=[
                USStockDiscoveryWorker(),
            ],
        )

        self.security_scout = USStockScout()

        self.financial = (
            financial
            or FinancialIntelligenceEngine()
        )

        self.investment = (
            investment
            or InvestmentDecisionEngine()
        )
        self.market_bridge = (
            market_bridge
            or MarketDataBridge()
        )

        self.evidence = (
            evidence
            or DEFAULT_EVIDENCE_COLLECTOR
        )

        self.verifier = (
            verifier
            or DEFAULT_FACT_VERIFIER
        )

        self.challenger = (
            challenger
            or DEFAULT_CHALLENGE_AGENT
        )

        self.reflection = (
            reflection
            or DEFAULT_REFLECTION_AGENT
        )

        self.nick = nick or Nick()
        self.portfolio_intelligence = (
            portfolio_intelligence
            or PortfolioIntelligence()
        )
        self.portfolio_risk_guard = (
            portfolio_risk_guard
            or PortfolioRiskGuard()
        )
        self.portfolio_quality_engine = (
            portfolio_quality_engine
            or PortfolioQualityEngine()
        )
        self.investment_bridge = (
            investment_bridge
            or InvestmentBridge()
        )

    def build_request(
        self,
        query: str,
        tickers: list[str] | None = None,
        research_type: str = "company",
        depth: str = "standard",
        as_of_date: str | None = None,
    ) -> ResearchRequest:

        return self.adapter.research_request(
            query=query,
            tickers=tickers,
            research_type=research_type,
            depth=depth,
            as_of_date=as_of_date,
        )

    @staticmethod
    def _has_explicit_company_target(
        request: ResearchRequest,
    ) -> bool:
        """
        Return True when the user explicitly supplied a company target.

        Explicit ticker requests must bypass full-market discovery.
        """

        tickers = getattr(request, "tickers", None)

        if not tickers:
            return False

        return any(
            isinstance(ticker, str)
            and ticker.strip()
            for ticker in tickers
        )

    def _resolve_company_direct(
        self,
        ticker: str,
    ) -> dict[str, Any] | None:
        """
        Resolve an explicitly requested ticker directly through
        the existing SEC-backed USStockScout infrastructure.

        Explicit ticker requests do not trigger full-market discovery.
        """

        if not isinstance(ticker, str):
            return None

        normalized = ticker.strip().upper()

        if not normalized:
            return None

        resolved = self.security_scout.resolve_ticker(
            normalized
        )

        if resolved is None:
            return None

        return resolved

    @staticmethod
    def _resolve_company(
        research_result: Any,
        request: ResearchRequest,
    ) -> dict[str, Any] | None:
        """
        Resolve one canonical company record for the
        Financial -> Investment bridge.

        Priority:
            1. Explicit ticker from request
            2. First investable SecurityMaster record

        This intentionally analyzes ONE company per pipeline
        execution. It prevents a normal pipeline request from
        triggering thousands of SEC requests.
        """

        data = getattr(
            research_result,
            "data",
            {},
        )

        investable = (
            data
            .get("investable_universe", {})
            .get("records", [])
        )

        if not isinstance(investable, list):
            return None

        requested_tickers = {
            ticker.upper()
            for ticker in request.tickers
        }

        if requested_tickers:

            for record in investable:

                if not isinstance(record, dict):
                    continue

                ticker = (
                    record.get("ticker")
                    or record.get("symbol")
                )

                if (
                    ticker
                    and str(ticker).upper()
                    in requested_tickers
                ):
                    return dict(record)

            return None

        for record in investable:

            if not isinstance(record, dict):
                continue

            cik = (
                record.get("cik")
                or record.get("cik_str")
                or record.get("cik_int")
            )

            if cik is not None:
                return dict(record)

        return None

    @staticmethod
    def _resolve_cik(
        record: dict[str, Any],
    ) -> int | None:

        value = (
            record.get("cik")
            or record.get("cik_str")
            or record.get("cik_int")
        )

        if value is None:
            return None

        try:
            return int(
                str(value)
                .replace("-", "")
                .strip()
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

    def run(
        self,
        *,
        query: str,
        tickers: list[str] | None = None,
        trinity_output: Any = None,
        research_type: str = "company",
        depth: str = "standard",
        as_of_date: str | None = None,
        thread_id: str | None = None,
        portfolio_candidates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:

        # ---------------------------------------------------------
        # 0. BUILD REQUEST
        # ---------------------------------------------------------

        request = self.build_request(
            query=query,
            tickers=tickers,
            research_type=research_type,
            depth=depth,
            as_of_date=as_of_date,
        )

        execution_thread_id = (
            thread_id
            or f"atlas-{uuid.uuid4().hex[:16]}"
        )

        import time
        _t0 = time.perf_counter()
        print("[ATLAS] START", flush=True)

        # ---------------------------------------------------------
        # 1. TRINITY EXECUTION
        # ---------------------------------------------------------

        if trinity_output is None:

            trinity_execution = self.runner.run(
                instruction=request.query,
                thread_id=execution_thread_id,
            )

            raw_trinity_output = trinity_execution

        else:

            trinity_execution = {
                "status": "external",
                "thread_id": execution_thread_id,
            }

            raw_trinity_output = trinity_output

        print(f"[ATLAS] TRINITY DONE {time.perf_counter()-_t0:.1f}s", flush=True)

        # ---------------------------------------------------------
        # 2. TRINITY -> ATLAS CONTRACT
        # ---------------------------------------------------------

        trinity_result = self.adapter.adapt(
            raw_trinity_output,
            query=request.query,
            tickers=request.tickers,
        )

        if trinity_execution:

            trinity_result.data.setdefault(
                "execution",
                trinity_execution,
            )

        print(f"[ATLAS] ADAPTER DONE {time.perf_counter()-_t0:.1f}s", flush=True)

        # ---------------------------------------------------------
        # 3. RESEARCH / COMPANY RESOLUTION
        # ---------------------------------------------------------
        #
        # Explicit ticker:
        #     DIRECT ROUTE
        #
        # No ticker:
        #     FULL DISCOVERY ROUTE
        #
        # This is the critical optimization boundary.
        # A request such as "Analyze AAPL" must NEVER scan the
        # complete US SecurityMaster universe just to discover AAPL.
        #

        explicit_target = self._has_explicit_company_target(
            request
        )

        if explicit_target:
            requested_ticker = (
                request.tickers[0].strip().upper()
            )

            direct_record = self._resolve_company_direct(
                requested_ticker
            )

            # Build a minimal research-compatible result.
            #
            # Financial identity resolution is performed below.
            research_result = self.research.execute(
                request,
                skip_discovery=True,
                direct_company=direct_record,
            )

        else:
            research_result = self.research.execute(
                request
            )

        print(f"[ATLAS] RESEARCH DONE {time.perf_counter()-_t0:.1f}s", flush=True)

        # ---------------------------------------------------------
        # 4. COMPANY -> FINANCIAL
        # ---------------------------------------------------------

        if explicit_target:
            company_record = self._resolve_company_direct(
                request.tickers[0]
            )
        else:
            company_record = self._resolve_company(
                research_result,
                request,
            )

        financial_result: dict[str, Any] = {
            "status": "not_run",
            "stage": "financial_intelligence",
            "reason": "No company candidate resolved.",
        }

        investment_result: dict[str, Any] = {
            "status": "not_run",
            "stage": "investment_decision",
            "reason": "Financial intelligence not available.",
        }

        if company_record is not None:

            cik = self._resolve_cik(
                company_record
            )

            ticker = (
                company_record.get("ticker")
                or company_record.get("symbol")
            )

            company_name = (
                company_record.get("company_name")
                or company_record.get("name")
                or company_record.get("title")
            )

            if cik is not None:

                try:

                    # -------------------------------------------------
                    # FINANCIAL ENGINE
                    # -------------------------------------------------

                    print(f"[ATLAS] FINANCIAL START {time.perf_counter()-_t0:.1f}s", flush=True)
                    financial_result = (
                        self.financial.analyze_company(
                            cik,
                            ticker=ticker,
                            company_name=company_name,
                            as_of_date=request.as_of_date,
                        )
                    )
                    print(f"[ATLAS] FINANCIAL DONE {time.perf_counter()-_t0:.1f}s", flush=True)

                    # -------------------------------------------------
                    # FINANCIAL -> INVESTMENT
                    # -------------------------------------------------

                    if (
                        financial_result.get("status")
                        == "success"
                    ):

                        metrics = (
                            financial_result.get(
                                "metrics",
                                {},
                            )
                        )

                        financial_quality = (
                            financial_result.get(
                                "quality",
                                {},
                            )
                        )

                        # -------------------------------------------------
                        # MARKET DATA ENRICHMENT
                        #
                        # FinancialIntelligenceEngine owns canonical
                        # financial fundamentals.
                        #
                        # MarketDataBridge adds current market fields
                        # required by InvestmentDecisionEngine.
                        #
                        # Market enrichment is additive and must not
                        # replace canonical financial values.
                        # -------------------------------------------------

                        try:
                            print(f"[ATLAS] MARKET START {time.perf_counter()-_t0:.1f}s", flush=True)
                            bridge_result = (
                                self.market_bridge.enrich(
                                    ticker=(
                                        financial_result.get(
                                            "ticker"
                                        )
                                        or ticker
                                    ),
                                    metrics=metrics,
                                )
                            )

                            enriched_metrics = (
                                bridge_result.get(
                                    "metrics",
                                    metrics,
                                )
                            )

                            print(f"[ATLAS] MARKET DONE {time.perf_counter()-_t0:.1f}s", flush=True)

                            if isinstance(
                                enriched_metrics,
                                dict,
                            ):
                                metrics = enriched_metrics
                            # Reassemble canonical financial metrics after market enrichment.
                            if isinstance(financial_result, dict):
                                financial_result["metrics"] = metrics

                        except Exception as market_exc:
                            # Market data is enrichment only.
                            # Financial analysis remains usable if the
                            # market provider is unavailable.

                            metrics = dict(metrics)

                            market_warning = (
                                "MarketDataBridge enrichment failed: "
                                f"{market_exc}"
                            )

                            financial_quality = dict(
                                financial_quality
                            )

                            warnings = list(
                                financial_quality.get(
                                    "warnings",
                                    [],
                                )
                                or []
                            )

                            warnings.append(
                                market_warning
                            )

                            financial_quality[
                                "warnings"
                            ] = warnings

                            # Synchronize the canonical financial result
                            # with the updated quality object.
                            #
                            # MarketDataBridge is enrichment-only, so a
                            # bridge failure must not invalidate financial
                            # analysis. However, the warning must remain
                            # visible at the canonical financial layer.
                            if isinstance(
                                financial_result,
                                dict,
                            ):
                                financial_result["quality"] = (
                                    financial_quality
                                )

                        print(f"[ATLAS] INVESTMENT START {time.perf_counter()-_t0:.1f}s", flush=True)
                        investment_result = (
                            self.investment.analyze(
                                metrics,
                                financial_quality=(
                                    financial_quality
                                ),
                                market_cap=(
                                    metrics.get(
                                        "market_cap"
                                    )
                                ),
                                enterprise_value=(
                                    metrics.get(
                                        "enterprise_value"
                                    )
                                ),
                                price=(
                                    metrics.get(
                                        "price"
                                    )
                                ),
                                ticker=(
                                    financial_result.get(
                                        "ticker"
                                    )
                                    or ticker
                                ),
                                company_name=(
                                    financial_result.get(
                                        "company_name"
                                    )
                                    or company_name
                                ),
                            )
                        )

                except Exception as exc:

                    financial_result = {
                        "status": "failure",
                        "stage": "financial_intelligence",
                        "cik": cik,
                        "ticker": ticker,
                        "company_name": company_name,
                        "error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                    }

                    investment_result = {
                        "status": "not_run",
                        "stage": "investment_decision",
                        "reason": (
                            "Financial intelligence failed."
                        ),
                    }

        # ---------------------------------------------------------
        # 5. EVIDENCE
        # ---------------------------------------------------------

        print(f"[ATLAS] EVIDENCE START {time.perf_counter()-_t0:.1f}s", flush=True)
        evidence_result = self.evidence.collect(
            trinity=trinity_result,
            research=research_result,
        )

        print(f"[ATLAS] EVIDENCE DONE {time.perf_counter()-_t0:.1f}s", flush=True)

        # ---------------------------------------------------------
        # 6. VERIFICATION
        # ---------------------------------------------------------

        print(f"[ATLAS] VERIFY START {time.perf_counter()-_t0:.1f}s", flush=True)
        verification_result = self.verifier.verify(
            research=research_result,
            evidence=evidence_result,
        )

        print(f"[ATLAS] VERIFY DONE {time.perf_counter()-_t0:.1f}s", flush=True)

        # ---------------------------------------------------------
        # 7. CHALLENGE
        # ---------------------------------------------------------

        print(f"[ATLAS] CHALLENGE START {time.perf_counter()-_t0:.1f}s", flush=True)
        challenge_result = self.challenger.challenge(
            research=research_result,
            verification=verification_result,
        )

        print(f"[ATLAS] CHALLENGE DONE {time.perf_counter()-_t0:.1f}s", flush=True)

        # ---------------------------------------------------------
        # 8. REFLECTION
        # ---------------------------------------------------------

        print(f"[ATLAS] REFLECTION START {time.perf_counter()-_t0:.1f}s", flush=True)
        reflection_result = self.reflection.reflect(
            research=research_result,
            verification=verification_result,
            challenge=challenge_result,
        )

        # ---------------------------------------------------------
        # 9. PORTFOLIO INTELLIGENCE
        # ---------------------------------------------------------
        #
        # Optional portfolio mode.
        #
        # Single-stock requests remain unchanged.
        # Portfolio candidates must already be supplied by an
        # upstream candidate pipeline / caller.
        # No full-market discovery is triggered here.
        # ---------------------------------------------------------

        portfolio_result: dict[str, Any] | None = None

        if portfolio_candidates:
            portfolio_inputs: list[PortfolioCandidate] = []

            for candidate in portfolio_candidates:
                if not isinstance(candidate, dict):
                    continue

                item = dict(candidate)

                # Reuse existing InvestmentBridge output when present.
                investment_score = item.get(
                    "investment_final_score"
                )

                investment_risk = item.get(
                    "investment_risk"
                )

                # Evaluate only when canonical investment signals
                # are not already present.
                if investment_score is None:
                    bridged = self.investment_bridge.evaluate(
                        item
                    )
                    item.update(bridged)

                    investment_score = item.get(
                        "investment_final_score"
                    )
                    investment_risk = item.get(
                        "investment_risk"
                    )

                ticker = (
                    item.get("investment_ticker")
                    or item.get("ticker")
                    or item.get("symbol")
                )

                if not ticker:
                    continue

                risk_score = 0.0

                if isinstance(investment_risk, dict):
                    risk_score = (
                        investment_risk.get("score")
                        or investment_risk.get("risk_score")
                        or 0.0
                    )

                try:
                    investment_score = float(
                        investment_score or 0.0
                    )
                except (TypeError, ValueError):
                    investment_score = 0.0

                try:
                    risk_score = float(
                        risk_score or 0.0
                    )
                except (TypeError, ValueError):
                    risk_score = 0.0

                conviction = item.get("conviction", 1.0)

                try:
                    conviction = float(conviction)
                except (TypeError, ValueError):
                    conviction = 1.0

                portfolio_inputs.append(
                    PortfolioCandidate(
                        ticker=str(ticker).strip().upper(),
                        score=investment_score,
                        risk_score=risk_score,
                        conviction=conviction,
                    )
                )

            allocation = self.portfolio_intelligence.allocate(
                portfolio_inputs
            )

            portfolio_result = {
                "status": "success",
                "candidate_count": len(portfolio_inputs),
                "positions": [
                    {
                        "ticker": position.ticker,
                        "score": position.score,
                        "risk_score": position.risk_score,
                        "allocation": position.allocation,
                        "risk_level": position.risk_level,
                    }
                    for position in allocation.positions
                ],
                "cash_weight": allocation.cash_weight,
                "total_invested": allocation.total_invested,
            }

            risk_check = self.portfolio_risk_guard.validate(
                portfolio_result
            )

            portfolio_result["risk_guard"] = {
                "status": risk_check.status,
                "approved": risk_check.approved,
                "cash_weight": risk_check.cash_weight,
                "total_invested": risk_check.total_invested,
                "risk_exposure": risk_check.risk_exposure,
                "reasons": list(risk_check.reasons),
                "checks": dict(risk_check.checks),
            }

            portfolio_result["status"] = (
                "approved"
                if risk_check.approved
                else "blocked"
            )

            portfolio_quality = self.portfolio_quality_engine.evaluate(
                portfolio_result
            )

            portfolio_result["quality"] = {
                "score": portfolio_quality.score,
                "decision": portfolio_quality.decision,
                "investment_quality": portfolio_quality.investment_quality,
                "risk_quality": portfolio_quality.risk_quality,
                "concentration_quality": portfolio_quality.concentration_quality,
                "cash_quality": portfolio_quality.cash_quality,
                "reasons": list(portfolio_quality.reasons),
            }

        # ---------------------------------------------------------
        # 10. INVESTMENT PACKAGE
        # ---------------------------------------------------------

        investment_package = {

            "request": request.to_dict(),

            "trinity": trinity_result.to_dict(),

            "research": research_result.to_dict(),

            "financial": financial_result,

            "investment": investment_result,

            "evidence": evidence_result.to_dict(),

            "verification": (
                verification_result.to_dict()
            ),

            "challenge": challenge_result.to_dict(),

            "reflection": reflection_result.to_dict(),

            **({
                "portfolio": portfolio_result,
            } if portfolio_result is not None else {}),
        }

        # ---------------------------------------------------------
        # 11. NICK
        # ---------------------------------------------------------

        print(f"[ATLAS] NICK START {time.perf_counter()-_t0:.1f}s", flush=True)
        nick_result = self.nick.evaluate(
            investment_package
        )

        pipeline_status = (
            "ready"
            if nick_result["status"] == "ready"
            else "incomplete"
        )

        # ---------------------------------------------------------
        # 12. FINAL OUTPUT
        # ---------------------------------------------------------

        return {

            "pipeline": self.name,

            "status": pipeline_status,

            "thread_id": execution_thread_id,

            "request": request.to_dict(),

            "trinity": trinity_result.to_dict(),

            "research": research_result.to_dict(),

            "financial": financial_result,

            "investment": investment_result,

            "evidence": evidence_result.to_dict(),

            "verification": (
                verification_result.to_dict()
            ),

            "challenge": challenge_result.to_dict(),

            "reflection": reflection_result.to_dict(),

            "nick": nick_result,
        }


DEFAULT_INTELLIGENCE_PIPELINE = IntelligencePipeline()


