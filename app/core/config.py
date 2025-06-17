# 环境变量和配置
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SuivueTong Backend"
    MONGO_URL: str
    SECRET_KEY: str # 用于JWT签名
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7天

    class Config:
        env_file = ".env"

settings = Settings()
