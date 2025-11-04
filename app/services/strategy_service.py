from app.models.strategy_model import Strategy

async def create_strategy(data:dict):
    strategy = Strategy(**data)
    await strategy.insert()
    return strategy

async def update_strategy_status(id:str , status:bool):
    updated_strategy  = await Strategy.findByIdAndUpdate(id, {
        "$set" : {"status" : not status}
    },
    return_document = True
    )

    if not updated_strategy:
        raise Exception("strategy Not found")
    
    return updated_strategy
                                                     
                                                     
                                                     
     
async def get_all_strategy():
    strategies = await Strategy.find().to_list(length=None)  # fetch all
    return strategies