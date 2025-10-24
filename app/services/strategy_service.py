from app.models.strategy_model import Strategy

async def create_strategy(data:dict):
    strategy = Strategy(**data)
    await strategy.insert()
    return strategy
     
