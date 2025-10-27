from app.models.paper_trade_model import Paper_Trade
import logging
logger = logging.getLogger(__name__)

async def create_paper_Order(data:dict):
    paper_order = Paper_Trade(**data)
    await paper_order.insert()
    logger.info("new paper trade is store")

    return paper_order


async def get_all_paper_trades():
    paper_trades = await Paper_Trade.find().to_list()
    return paper_trades