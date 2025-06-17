# MongoDB连接和工具函数 (使用Motor)
from motor.motor_asyncio import AsyncIOMotorClient
from ..core.config import settings

class Database:
    client: AsyncIOMotorClient = None

db = Database()

async def connect_to_mongo():
    print("Connecting to MongoDB...")
    db.client = AsyncIOMotorClient(settings.MONGO_URL)
    print("Connection successful.")

async def close_mongo_connection():
    print("Closing MongoDB connection.")
    db.client.close()

def get_database():
    return db.client.get_database("suivuetong_db")
