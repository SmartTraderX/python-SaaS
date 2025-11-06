
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI ="mongodb+srv://vishalgarna:vishalgarna%401@cluster0.uxsnu.mongodb.net"
    MONGO_DB = "Saas"

    class Config:
        env_file ='.env'


setting =Settings()