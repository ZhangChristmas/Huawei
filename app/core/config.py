# app/core/config.py
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional, Union

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 加载 .env 文件
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

def load_key_from_file(key_path_str: Optional[str]) -> Optional[str]:
    if not key_path_str:
        return None
    key_path = BASE_DIR / key_path_str
    if key_path.exists():
        with open(key_path, "r") as f:
            return f.read()
    else:
        print(f"Warning: Key file not found at {key_path}")
        return None

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "岁悦通后端服务")
    PROJECT_VERSION: str = os.getenv("PROJECT_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

    # MongoDB
    MONGO_URI: Optional[str] = os.getenv("MONGO_URI")
    MONGO_DB_NAME: Optional[str] = os.getenv("MONGO_DB_NAME")

    # MQTT
    MQTT_BROKER_HOST: Optional[str] = os.getenv("MQTT_BROKER_HOST")
    MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", 1883))
    MQTT_USERNAME: Optional[str] = os.getenv("MQTT_USERNAME")
    MQTT_PASSWORD: Optional[str] = os.getenv("MQTT_PASSWORD")
    MQTT_CLIENT_ID_PREFIX: str = os.getenv("MQTT_CLIENT_ID_PREFIX", "backend_client_")
    MQTT_TLS_ENABLED: bool = os.getenv("MQTT_TLS_ENABLED", "False").lower() == "true"
    MQTT_CA_CERTS: Optional[str] = os.getenv("MQTT_CA_CERTS")
    MQTT_CERTFILE: Optional[str] = os.getenv("MQTT_CERTFILE")
    MQTT_KEYFILE: Optional[str] = os.getenv("MQTT_KEYFILE")


    # JWT
    RSA_PRIVATE_KEY_PATH: Optional[str] = os.getenv("RSA_PRIVATE_KEY_PATH")
    RSA_PUBLIC_KEY_PATH: Optional[str] = os.getenv("RSA_PUBLIC_KEY_PATH") # 公钥文件路径
    ALGORITHM: str = os.getenv("ALGORITHM", "RS256") # 确保是RS256
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

    # 从文件加载密钥内容
    RSA_PRIVATE_KEY: Optional[str] = load_key_from_file(RSA_PRIVATE_KEY_PATH)
    RSA_PUBLIC_KEY: Optional[str] = load_key_from_file(RSA_PUBLIC_KEY_PATH)


    # WeChat Mini Program
    WX_APPID: Optional[str] = os.getenv("WX_APPID")
    WX_SECRET: Optional[str] = os.getenv("WX_SECRET")
    WX_SUB_ID_SOS: Optional[str] = os.getenv("WX_SUB_ID_SOS")
    WX_SUB_ID_BILLING: Optional[str] = os.getenv("WX_SUB_ID_BILLING")
    WX_SUB_ID_LOW_BATT: Optional[str] = os.getenv("WX_SUB_ID_LOW_BATT")

    # CORS
    BACKEND_CORS_ORIGINS_STR: Optional[str] = os.getenv("BACKEND_CORS_ORIGINS")
    BACKEND_CORS_ORIGINS: List[str] = []
    if BACKEND_CORS_ORIGINS_STR:
        try:
            BACKEND_CORS_ORIGINS = json.loads(BACKEND_CORS_ORIGINS_STR)
        except json.JSONDecodeError:
            print(f"Warning: BACKEND_CORS_ORIGINS is not a valid JSON list: {BACKEND_CORS_ORIGINS_STR}")
            # 可以设置一个默认值或者直接抛出错误
            # BACKEND_CORS_ORIGINS = ["*"] # 生产环境不推荐 "*"

    # 简单校验关键配置
    if not MONGO_URI: raise ValueError("MONGO_URI not set")
    if not MONGO_DB_NAME: raise ValueError("MONGO_DB_NAME not set")
    if ALGORITHM.startswith("RS") and not RSA_PRIVATE_KEY: # 如果使用RSA算法，则私钥必须存在
        raise ValueError("RSA_PRIVATE_KEY not loaded. Check RSA_PRIVATE_KEY_PATH in .env and file existence.")
    # 如果使用RSA，公钥要么从文件加载，要么可以从私钥派生 (security.py中处理)
    # 如果选择从私钥派生公钥，则RSA_PUBLIC_KEY可以不是必须的
    if ALGORITHM.startswith("RS") and not RSA_PUBLIC_KEY:
        print("Warning: RSA_PUBLIC_KEY not loaded from file. Will attempt to derive from private key if needed for verification by this service.")
    if not WX_APPID: raise ValueError("WX_APPID not set")
    if not WX_SECRET: raise ValueError("WX_SECRET not set")
    if not MQTT_BROKER_HOST: raise ValueError("MQTT_BROKER_HOST not set")


settings = Settings()

if settings.DEBUG:
    print("--- Application Settings Loaded ---")
    print(f"PROJECT_NAME: {settings.PROJECT_NAME}")
    print(f"DEBUG: {settings.DEBUG}")
    print(f"MONGO_URI: {settings.MONGO_URI.split('@')[-1] if '@' in settings.MONGO_URI else settings.MONGO_URI}")
    print(f"MQTT_BROKER_HOST: {settings.MQTT_BROKER_HOST}")
    print(f"WX_APPID: {settings.WX_APPID[:4]}****")
    print(f"JWT ALGORITHM: {settings.ALGORITHM}")
    print(f"RSA_PRIVATE_KEY loaded: {'Yes' if settings.RSA_PRIVATE_KEY else 'No'}")
    print(f"RSA_PUBLIC_KEY loaded: {'Yes' if settings.RSA_PUBLIC_KEY else 'No'}")
    print("---------------------------------")
