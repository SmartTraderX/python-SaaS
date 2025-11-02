from beanie import Document , PydanticObjectId
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from bson import ObjectId

class Symbol(BaseModel):
    id:PydanticObjectId =Field(default_factory = ObjectId)
    name: str
    theStrategyMatch: bool = False,
    symbolCode: Optional[str]
    

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
