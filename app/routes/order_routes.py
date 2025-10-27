from fastapi import APIRouter , HTTPException  , Body
from app.services.paper_trade_service import (get_all_paper_trades)

router =  APIRouter(prefix='/order-management' , tags=['orders'])

@router.get('/get_paper_trades')
async def all_paper_trades_route():
    try:
        result  = await get_all_paper_trades()
        return {"message":'success', "data": result}
    except Exception as e :
        raise HTTPException(status_code=500 , detail = str(e))


