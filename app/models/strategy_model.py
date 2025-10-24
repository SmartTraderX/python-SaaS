from beanie import Document
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

class Symbol(BaseModel):
    symbolName: str
    theStrategyMatch: bool = False

class OrderDetails(BaseModel):
    action: Optional[str]
    symbol: List[Symbol] = []
    orderType: Optional[str]
    quantity: Optional[int]
    validity: Optional[str]
    SL: Optional[str]
    TP: Optional[str]

class Strategy(Document):
    userId: str
    strategyName: Optional[str]
    strategyType: Optional[str]
    category: Optional[str]
    createdBy: Optional[str]
    description: Optional[str]
    timeframe: Optional[str]
    status: bool = False
    condition: Optional[dict]
    associatedBroker: Optional[str]
    expiryDate: datetime = datetime.now() + timedelta(days=7)
    orderDetails: Optional[OrderDetails]
    totalSubscriber: Optional[list] = []
    tags: Optional[list] = []
    createdAt: datetime = datetime.now()

    class Settings:
        name = "strategies"   # Mongo collection name
