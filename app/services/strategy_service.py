from app.models.strategy_model import Strategy
from beanie import PydanticObjectId

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
                                                     
async def   mark_symbol_match(id:str , symbolid:str):
    try:
        strategy = await Strategy.get(PydanticObjectId(id))
        if not strategy:
         raise Exception('No Strategy Found')
        
        symbolFound = False

        for symbol in strategy.orderDetails.get("symbol",[]):
           if symbol.get("id") == symbolid:
              symbolFound =True
              symbol["theStrategyMatch"] = True
              break
           
        if not symbolFound:
           raise Exception(f"symbol Not found{symbolid}") 

        await strategy.save() 
        print(f"Symmbol is match and mark as true")

    except Exception as e:
      raise Exception(f"Error{str(e)}")
    

                                                     
     
async def get_all_strategy():
    strategies = await Strategy.find().to_list(length=None)  # fetch all
    return strategies