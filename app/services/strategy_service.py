from app.models.strategy_model import Strategy

async def create_strategy(data:dict):
    strategy = Strategy(**data)
    await strategy.insert()
    return strategy
     
async def get_all_strategy():
    strategies = await Strategy.find().to_list(length=None)  # fetch all
    return strategies