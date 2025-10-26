from app.models.paper_trade_model import Paper_Trade

async def create_paper_Order(data:dict):
    paper_order = Paper_Trade(**data)
    await paper_order.insert()
    return paper_order
     