from ai.research.pipeline.investment_pipeline import InvestmentPipeline


engine = InvestmentPipeline()


stocks = engine.run(
    limit=10
)


for stock in stocks:

    print(stock)


