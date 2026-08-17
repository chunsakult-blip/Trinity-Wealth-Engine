from __future__ import annotations


from ai.research.pipeline.investment_pipeline_v2 import (
    InvestmentPipelineV2
)

from ai.research.portfolio.risk_portfolio_engine import (
    RiskPortfolioEngine
)

from ai.research.reporting.investment_report import (
    InvestmentReportGenerator
)

from ai.agents.investment_analyst import (
    InvestmentAnalystAgent
)



def main():


    print("="*60)
    print("TRINITY WEALTH ENGINE")
    print("="*60)


    print("\n[1] Running investment pipeline")


    pipeline = InvestmentPipelineV2()


    stocks = pipeline.run(
        limit=20
    )


    print(
        "Candidates:",
        len(stocks)
    )



    print("\n[2] Building portfolio")


    portfolio_engine = (
        RiskPortfolioEngine()
    )


    portfolio = (
        portfolio_engine
        .allocate(stocks)
    )



    print("\n[3] Generating report")


    reporter = (
        InvestmentReportGenerator()
    )


    report = reporter.generate(
        stocks
    )


    reporter.save(
        report
    )



    print("\n[4] AI Analyst summary")


    analyst = (
        InvestmentAnalystAgent()
    )


    for stock in stocks[:5]:


        memo = analyst.analyze(
            stock,
            None
        )


        print()

        print(
            memo
        )



    print("\nDONE")
    print(
        "Report saved:"
        " data/investment_report.json"
    )



if __name__ == "__main__":

    main()

