from typing import Optional
from datetime import datetime
from beanie import Document
from pydantic import BaseModel


class UserModel(Document):
    name: Optional[str] = ''
    margin:float = 800000.00
    email: Optional[str] = ''
    mobileNo: Optional[str] = ''
    clientCode: Optional[str] = ''
    pwd: Optional[str] = ''
    apiKey: Optional[str] = ''
    secretKey: Optional[str] = ''
    feedToken: Optional[str] = ''
    authToken: Optional[str] = ''
    refreshToken: Optional[str] = ''
    isDeleted: bool = False
    strategiesCount: int = 0
    tokenExpiry: datetime = datetime.now()
    createdAt: datetime = datetime.now()
    

    class Settings:
        name = "users"
