from ai.research.universe.sec_market_loader import SECMarketLoader
from ai.research.universe.growth_universe import GrowthUniverseBuilder


loader = SECMarketLoader()

stocks = loader.load()

builder = GrowthUniverseBuilder()

candidates = builder.build(stocks)


print("TOTAL CANDIDATES:", len(candidates))


for item in candidates[:20]:
    print(item)

