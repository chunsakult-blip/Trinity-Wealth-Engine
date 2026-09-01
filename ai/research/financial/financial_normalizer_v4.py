from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NormalizedFinancials:

    ticker: str

    revenue: float
    net_income: float
    assets: float
    liabilities: float
    cashflow: float

    revenue_growth: float
    net_margin: float
    operating_margin: float
    gross_margin: float

    roe: float
    roic: float

    debt_to_asset: float
    free_cashflow_margin: float

    data_quality: float

    # ---------------------------------------------------------
    # Canonical financial fields
    #
    # These fields preserve the metrics already extracted by
    # FinancialIntelligenceV2.
    #
    # None means genuinely unavailable.
    # 0.0 means an actual numeric zero.
    # ---------------------------------------------------------

    free_cash_flow: float | None = None
    fcf: float | None = None

    operating_cash_flow: float | None = None

    capital_expenditures: float | None = None
    capex: float | None = None

    gross_profit: float | None = None
    operating_income: float | None = None
    equity: float | None = None

    ebitda: float | None = None

    # ---------------------------------------------------------
    # Canonical compatibility bridge
    # ---------------------------------------------------------

    _metrics: dict[str, float | None] = field(
        default_factory=dict,
        repr=False,
    )

    _quality: dict = field(
        default_factory=dict,
        repr=False,
    )

    @property
    def metrics(self) -> dict[str, float | None]:
        """
        Canonical metric view.

        IMPORTANT:

        None = metric genuinely unavailable.
        0.0  = actual zero.

        This property does not calculate financial metrics.
        It only exposes the normalized canonical values.
        """

        if self._metrics:
            return dict(self._metrics)

        return {
            "revenue": self.revenue,

            "net_income": self.net_income,

            "free_cash_flow": self.free_cash_flow,

            "gross_margin": (
                self.gross_margin
                if self.gross_margin != 0.0
                else None
            ),

            "operating_margin": (
                self.operating_margin
                if self.operating_margin != 0.0
                else None
            ),

            "roe": (
                self.roe
                if self.roe != 0.0
                else None
            ),

            "roic": (
                self.roic
                if self.roic != 0.0
                else None
            ),
        }

    @property
    def ttm(self):
        """
        Compatibility freshness signal.

        Existing TTM behavior is intentionally preserved.
        This normalizer patch does not perform TTM calculation.
        """

        if any(
            value != 0
            for value in (
                self.revenue,
                self.net_income,
                self.cashflow,
            )
        ):
            return self

        return None

    @property
    def quality(self) -> dict:
        return self._quality

    @quality.setter
    def quality(self, value: dict) -> None:
        self._quality = dict(value or {})


class FinancialNormalizerV4:

    def normalize(
        self,
        financial,
    ):

        ticker = getattr(
            financial,
            "ticker",
            "",
        )

        # -----------------------------------------------------
        # Legacy normalized scalar values
        # -----------------------------------------------------

        revenue = self._number(
            financial,
            "revenue",
        )

        net_income = self._number(
            financial,
            "net_income",
        )

        assets = self._number(
            financial,
            "assets",
        )

        liabilities = self._number(
            financial,
            "liabilities",
        )

        cashflow = self._number(
            financial,
            "cashflow",
        )

        revenue_growth = self._number(
            financial,
            "revenue_growth",
        )

        gross_margin = self._number(
            financial,
            "gross_margin",
        )

        operating_margin = self._number(
            financial,
            "operating_margin",
        )

        roe = self._number(
            financial,
            "roe",
        )

        roic = self._number(
            financial,
            "roic",
        )

        # -----------------------------------------------------
        # Preserve canonical source metrics
        #
        # IMPORTANT:
        #
        # free_cash_flow MUST come from source.free_cash_flow.
        #
        # It must NEVER be silently replaced by cashflow.
        # -----------------------------------------------------

        free_cash_flow = self._optional_number(
            financial,
            "free_cash_flow",
        )

        capex = self._optional_number(
            financial,
            "capex",
        )

        gross_profit = self._optional_number(
            financial,
            "gross_profit",
        )

        operating_income = self._optional_number(
            financial,
            "operating_income",
        )

        equity = self._optional_number(
            financial,
            "equity",
        )

        # -----------------------------------------------------
        # Explicit operating cash flow alias
        #
        # FinancialIntelligenceV2 uses "cashflow" as the
        # canonical operating cash flow field.
        # -----------------------------------------------------

        operating_cash_flow = self._optional_number(
            financial,
            "cashflow",
        )

        # -----------------------------------------------------
        # CapEx compatibility alias
        # -----------------------------------------------------

        capital_expenditures = capex

        # -----------------------------------------------------
        # EBITDA
        #
        # Do NOT invent EBITDA.
        #
        # EBITDA requires a valid D&A source.
        # If D&A is unavailable, EBITDA remains None.
        #
        # If a future provider supplies EBITDA directly,
        # preserve it.
        # -----------------------------------------------------

        ebitda = self._optional_number(
            financial,
            "ebitda",
        )

        if ebitda is None:

            depreciation = self._optional_number(
                financial,
                "depreciation",
            )

            amortization = self._optional_number(
                financial,
                "amortization",
            )

            if (
                operating_income is not None
                and (
                    depreciation is not None
                    or amortization is not None
                )
            ):

                depreciation_value = (
                    depreciation
                    if depreciation is not None
                    else 0.0
                )

                amortization_value = (
                    amortization
                    if amortization is not None
                    else 0.0
                )

                ebitda = (
                    operating_income
                    + depreciation_value
                    + amortization_value
                )

        # -----------------------------------------------------
        # Derived legacy metrics
        # -----------------------------------------------------

        net_margin = 0.0

        if revenue > 0:
            net_margin = (
                net_income / revenue
            )

        debt_to_asset = 0.0

        if assets > 0:
            debt_to_asset = (
                liabilities / assets
            )

        # -----------------------------------------------------
        # FCF margin
        #
        # IMPORTANT:
        #
        # FCF margin = FCF / Revenue
        #
        # NOT operating cash flow / Revenue.
        # -----------------------------------------------------

        free_cashflow_margin = 0.0

        if (
            revenue > 0
            and free_cash_flow is not None
        ):
            free_cashflow_margin = (
                free_cash_flow / revenue
            )

        # -----------------------------------------------------
        # Data quality for legacy contract
        # -----------------------------------------------------

        populated = 0

        fields = [
            revenue,
            net_income,
            assets,
            liabilities,
            cashflow,
        ]

        for value in fields:
            if value != 0:
                populated += 1

        data_quality = (
            populated / len(fields)
        ) * 100

        # -----------------------------------------------------
        # Canonical metric availability
        #
        # IMPORTANT:
        #
        # Never convert unavailable values to zero.
        # -----------------------------------------------------

        metrics = {

            "revenue": self._optional_number(
                financial,
                "revenue",
            ),

            "net_income": self._optional_number(
                financial,
                "net_income",
            ),

            "free_cash_flow": free_cash_flow,

            "gross_margin": self._optional_number(
                financial,
                "gross_margin",
            ),

            "operating_margin": self._optional_number(
                financial,
                "operating_margin",
            ),

            "roe": self._optional_number(
                financial,
                "roe",
            ),

            "roic": self._optional_number(
                financial,
                "roic",
            ),
        }

        return NormalizedFinancials(

            ticker=ticker,

            revenue=revenue,

            net_income=net_income,

            assets=assets,

            liabilities=liabilities,

            cashflow=cashflow,

            revenue_growth=revenue_growth,

            net_margin=net_margin,

            operating_margin=operating_margin,

            gross_margin=gross_margin,

            roe=roe,

            roic=roic,

            debt_to_asset=debt_to_asset,

            free_cashflow_margin=free_cashflow_margin,

            data_quality=round(
                data_quality,
                2,
            ),

            # -------------------------------------------------
            # Canonical financial fields
            # -------------------------------------------------

            free_cash_flow=free_cash_flow,

            fcf=free_cash_flow,

            operating_cash_flow=operating_cash_flow,

            capital_expenditures=capital_expenditures,

            capex=capex,

            gross_profit=gross_profit,

            operating_income=operating_income,

            equity=equity,

            ebitda=ebitda,

            _metrics=metrics,
        )

    # =========================================================
    # Numeric helpers
    # =========================================================

    @staticmethod
    def _number(
        obj,
        field,
    ):

        value = getattr(
            obj,
            field,
            0,
        )

        if value is None:
            return 0.0

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    @staticmethod
    def _optional_number(
        obj,
        field,
    ):
        """
        Return None when the source does not actually provide
        the metric.

        This is intentionally different from _number().
        """

        if not hasattr(
            obj,
            field,
        ):
            return None

        value = getattr(
            obj,
            field,
            None,
        )

        if value is None:
            return None

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return None
