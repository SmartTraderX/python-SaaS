from fastapi import APIRouter , HTTPException  , Body
from app.services.strategy_service import (create_strategy ,get_all_strategy)
from app.services.strategy_evalutation_services import (BacktestStrategy)

router = APIRouter(prefix='/strategy-management' , tags=['strategies'])

@router.post('/create')
async def create_strategy_route(data:dict = Body(...)):
    try:
        strategy= await create_strategy(data)
        return {"message":'Strategy created', "data": strategy}
    except  Exception as e:
        raise HTTPException(status_code=500 , detail = str(e))


@router.get('/all-strategy')
async def get_all_strategy_route():
    try:
        strategies = await get_all_strategy()
        return {"message":'success', "data": strategies}
    except  Exception as e:
        raise HTTPException(status_code=500 , detail = str(e))


@router.post('/backtest-result')
async def backtest_result(data:dict = Body(...)):
    try:
        result = BacktestStrategy(data)
        return {"message":'success', "data": result}
    except  Exception as e:
        raise HTTPException(status_code=500 , detail = str(e))

        

