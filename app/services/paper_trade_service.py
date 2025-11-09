from app.models.paper_trade_model import Paper_Trade
from app.models.user_model import UserModel
import logging
from bson import ObjectId
from app.logger import logger

async def create_paper_Order(data:dict):
    try :
        user =await UserModel.get(ObjectId("6905f6e134e7250e9e8b3389"))
        if not user:
            raise Exception('User Not Found')
        
        required_margin  =  data["quantity"] * data["entry_price"]
        if user.margin <  required_margin:
            raise Exception('Insuffecient Balance !')
        
        paper_order = Paper_Trade(**data)
        await paper_order.insert()
        logger.info("new paper trade is store")

        logger.info('Updating User Account')

        user.margin -= required_margin
        await user.save()
        logger.info("User account updated")

    except Exception as e:
        raise Exception(f'Error:{e}')

async def get_all_paper_trades():
    paper_trades = await Paper_Trade.find().to_list()
    return paper_trades