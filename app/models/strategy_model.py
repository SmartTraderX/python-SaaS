from beanie import Document , PydanticObjectId
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

class Symbol(BaseModel):
    name: str
    theStrategyMatch: bool = False

class OrderDetails(BaseModel):
    action: Optional[str]
    symbol: List[Symbol] = []
    orderType: Optional[str]
    quantity: Optional[int]
    # validity: Optional[str]
    SL: Optional[str]
    TP: Optional[str]

class Strategy(Document):
    userId: Optional[PydanticObjectId] = None
    strategyName: Optional[str]
    category: Optional[str]
    createdBy: Optional[str] = None
    description: Optional[str]
    timeframe: Optional[str]
    status: bool = False
    condition: Optional[list]
    associatedBroker: Optional[str]=None
    expiryDate: datetime = datetime.now() + timedelta(days=7)
    orderDetails: Optional[OrderDetails]
    totalSubscriber: Optional[list] = []
    tags: Optional[list] = []
    createdAt: datetime = datetime.now()

    class Settings:
        name = "strategies"   # Mongo collection name
