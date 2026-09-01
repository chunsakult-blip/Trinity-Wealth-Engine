"""
SEC XBRL concept aliases.

Different issuers use different taxonomy concepts.
The normalizer therefore works from concept aliases rather than
assuming one exact XBRL tag.
"""

GAAP_CONCEPTS = {
    "depreciation": [
        "Depreciation",
        "DepreciationDepletionAndAmortization",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        "DepreciationAndAmortization",
    ],
    "amortization": [
        "AmortizationOfIntangibleAssets",
        "AmortizationOfIntangibleAssetsExcludingGoodwill",
        "AmortizationOfFinancingCosts",
        "AmortizationOfDeferredCosts",
    ],

    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],

    "gross_profit": [
        "GrossProfit",
    ],

    "operating_income": [
        "OperatingIncomeLoss",
    ],

    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],

    "eps": [
        "EarningsPerShareBasic",
        "EarningsPerShareDiluted",
    ],

    "assets": [
        "Assets",
    ],

    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],

    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],

    "debt": [
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "ShortTermBorrowings",
        "DebtCurrent",
        "DebtLongtermAndShorttermCombinedAmount",
        "Borrowings",
        "LongtermBorrowings",
        "CurrentPortionOfLongtermBorrowings",
        "ShorttermBorrowings",
    ],

    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],

    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
        "PaymentsToAcquireProductiveAssets",
        "PurchaseOfPropertyPlantAndEquipment",
        "PaymentsForPropertyPlantAndEquipment",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssetsClassifiedAsInvestingActivities",
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    ],

    "shares": [
        "EntityCommonStockSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],

    "interest_expense": [
        "InterestExpenseNonOperating",
        "InterestExpenseDebt",
        "InterestAndDebtExpense",
    ],
}


# ============================================================
# ATLAS — CANONICAL D&A SEC CONCEPT CANDIDATES
#
# IMPORTANT:
# concept_values may contain either:
#   - bare SEC concept names
#   - us-gaap:<concept>
#
# Therefore both forms are intentionally supported.
# ============================================================

DEPRECIATION_CANDIDATES = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
    "Depreciation",
    "DepreciationExpense",

    "us-gaap:DepreciationDepletionAndAmortization",
    "us-gaap:DepreciationAndAmortization",
    "us-gaap:DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
    "us-gaap:Depreciation",
    "us-gaap:DepreciationExpense",
]

AMORTIZATION_CANDIDATES = [
    "AmortizationOfIntangibleAssets",
    "AmortizationExpense",
    "AmortizationOfIntangibleAssetsExcludingGoodwill",
    "Amortization",

    "us-gaap:AmortizationOfIntangibleAssets",
    "us-gaap:AmortizationExpense",
    "us-gaap:AmortizationOfIntangibleAssetsExcludingGoodwill",
    "us-gaap:Amortization",
]
