from typing import Optional
from datetime import datetime
from beanie import Document


class BrokerModel(BaseModel):
    userId: str
    name: str
    email: str
    brokerName: str = "upstox"
    clientId: str
    apiKey: str
    apiSecret: str
    feedToken: Optional[str] = None
    accessToken: Optional[str] = None
    tokenExpiry: Optional[str] = None
    exchanges: Optional[list] = []
    products: Optional[list] = []
    status: Optional[bool] = True

class UserModel(Document):
    name: Optional[str] = ''
    email: Optional[str] = ''
    mobileNo: Optional[str] = ''
    isDeleted: bool = False
    connectedBroker: Optional[BrokerModel] = None
    strategiesCount: int = 0
    createdAt: datetime = datetime.now()

    class Settings:
        name = "users"
