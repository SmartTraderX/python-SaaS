from typing import Optional
from datetime import datetime
from beanie import Document
from pydantic import BaseModel


class UserModel(Document):
    name: Optional[str] = ''
    email: Optional[str] = ''
    mobileNo: Optional[str] = ''
    userId: Optional[str] = ''
    pwd: Optional[str] = ''
    apiKey: Optional[str] = ''
    secretKey: Optional[str] = ''
    feedToken: Optional[str] = ''
    authToken: Optional[str] = ''
    refreshToken: Optional[str] = ''
    isDeleted: bool = False
    strategiesCount: int = 0
    createdAt: datetime = datetime.now()

    class Settings:
        name = "users"
