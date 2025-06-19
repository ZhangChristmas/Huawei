# app/db/mongodb_utils.py
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings # 确保路径正确

class MongoDB:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

db_manager = MongoDB()

async def connect_to_mongo():
    print(f"Connecting to MongoDB at {settings.MONGO_URI}...")
    try:
        db_manager.client = AsyncIOMotorClient(str(settings.MONGO_URI)) # 确保 MONGO_URI 是字符串
        db_manager.db = db_manager.client[str(settings.MONGO_DB_NAME)] # 确保 MONGO_DB_NAME 是字符串
        # 尝试ping一下服务器，确认连接成功
        await db_manager.client.admin.command('ping')
        print("Successfully connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        # 在实际应用中，这里可能需要更健壮的错误处理或重试机制
        # 或者在应用启动时如果连接失败则直接退出
        raise  # 重新抛出异常，让FastAPI知道启动失败

async def close_mongo_connection():
    if db_manager.client:
        print("Closing MongoDB connection...")
        db_manager.client.close()
        print("MongoDB connection closed.")

def get_database() -> AsyncIOMotorDatabase:
    if db_manager.db is None:
        raise RuntimeError("MongoDB not connected. Call connect_to_mongo first during app startup.")
    return db_manager.db

# --- Collection Getters (为每个模型创建一个获取对应collection的函数) ---
def get_user_collection():
    return get_database()["users"]

def get_device_collection():
    return get_database()["devices"]

def get_contact_collection():
    return get_database()["contacts"]

def get_reminder_collection():
    return get_database()["reminders"]

def get_entertainment_item_collection(): # 注意名称与模型对应
    return get_database()["entertainment_items"]

def get_notification_collection():
    return get_database()["notifications"]

def get_sos_alert_collection():
    return get_database()["sos_alerts"]

# 可以在应用启动时创建索引 (可选，但推荐)
async def create_db_indexes():
    print("Attempting to create database indexes...")
    db = get_database()
    try:
        # User Collection
        await db["users"].create_index("wxOpenid", unique=True)
        await db["users"].create_index("wxUnionid", unique=True, sparse=True)
        print("Indexes for 'users' collection ensured.")

        # Device Collection
        await db["devices"].create_index("deviceId", unique=True) # IMEI
        await db["devices"].create_index("userId")
        print("Indexes for 'devices' collection ensured.")

        # Contacts Collection
        await db["contacts"].create_index("deviceId")
        print("Indexes for 'contacts' collection ensured.")

        # Reminders Collection
        await db["reminders"].create_index("deviceId")
        await db["reminders"].create_index([("nextTriggerAt", 1), ("isEnabled", 1)]) # 组合索引，用于调度查询
        print("Indexes for 'reminders' collection ensured.")

        # Entertainment Items Collection
        await db["entertainment_items"].create_index("deviceId")
        print("Indexes for 'entertainment_items' collection ensured.")

        # Notifications Collection
        await db["notifications"].create_index("userId")
        await db["notifications"].create_index("deviceId")
        await db["notifications"].create_index([("time", -1), ("isRead", 1)]) # 按时间降序，未读优先
        print("Indexes for 'notifications' collection ensured.")

        # SOS Alerts Collection
        await db["sos_alerts"].create_index("deviceId")
        await db["sos_alerts"].create_index("timestamp")
        print("Indexes for 'sos_alerts' collection ensured.")

        print("Database indexes creation process completed.")
    except Exception as e:
        print(f"Error creating database indexes: {e}")
