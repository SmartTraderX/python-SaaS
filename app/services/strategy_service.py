from app.models.strategy_model import Strategy
from beanie import PydanticObjectId

async def create_strategy(data:dict):
    strategy = Strategy(**data)
    await strategy.insert()
    return strategy

async def update_strategy_status(id: str, status: bool):
    try:
        # Convert string to PydanticObjectId
        object_id = PydanticObjectId(id)

        # Toggle or set the new status
        new_status = not status

        # Perform update directly
        updated = await Strategy.find_one(Strategy.id == object_id).update(
            {"$set": {"status": new_status}}
        )

        if not updated.modified_count:
            raise Exception("Strategy not found or not updated")

        # Fetch the updated document to return
        updated_strategy = await Strategy.get(object_id)
        return updated_strategy

    except Exception as e:
        raise Exception(f"Error updating strategy: {str(e)}")
    
       
   
                                                     
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
    try:
       strategies = await Strategy.find().to_list(length=None)  # fetch all
       return strategies
    except Exception as e:
       raise Exception(f"Error{str(e)}")
       
       
    