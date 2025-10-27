from beanie import Document , PydanticObjectId
from datetime import datetime
from typing import Optional


class Paper_Trade (Document):
    userId : Optional[PydanticObjectId] = None
    strategyId : Optional[PydanticObjectId] = None

    symbol : str
    action : str
    order_type : str = "Market"
    quantity :int

    entry_price: float
    exit_prcice: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    status : str ='OPEN'
    pnl: Optional[float] = None
    signal_time: Optional[str] = None                 # Profit/Loss after closing
    created_at: datetime = datetime.utcnow()        # Entry time
    updated_at: datetime = datetime.utcnow()

    class Settings:
        name = "paper_trades" 


