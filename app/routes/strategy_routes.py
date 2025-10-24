from fastapi import APIRouter , HTTPException  , Body
from app.services.strategy_service import (create_strategy)

router = APIRouter(prefix='/strategy' , tags=['strategies'])

@router.post('/create')
async def create_strategy_route(data:dict = Body(...)):

    print(data)

    strategy= await create_strategy(data)
    return {"message":'Strategy created', "data": strategy}