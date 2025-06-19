# app/services/user_service.py
from typing import Optional
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder

from app.db.mongodb_utils import get_user_collection
from app.models.user_models import UserCreate, UserInDB, PyObjectId
from app.core.security import get_password_hash

async def get_user_by_openid(openid: str) -> Optional[UserInDB]:
    user_collection = get_user_collection()
    user_doc = await user_collection.find_one({"wxOpenid": openid})
    if user_doc:
        return UserInDB(**user_doc)
    return None

async def get_user_by_id(user_id: PyObjectId) -> Optional[UserInDB]:
    user_collection = get_user_collection()
    user_doc = await user_collection.find_one({"_id": str(user_id)})
    if user_doc:
        return UserInDB(**user_doc)
    return None

async def create_user(user_in: UserCreate) -> UserInDB:
    user_collection = get_user_collection()
    existing_user = await get_user_by_openid(user_in.wxOpenid)
    if existing_user:
        # 如果用户已存在，可以考虑更新其信息或直接返回
        # 这里我们直接返回已存在的用户，符合小程序登录逻辑
        return existing_user

    # 使用Pydantic模型构建完整的数据库对象（包含默认值）
    new_user_db = UserInDB(**user_in.model_dump())
    # 使用jsonable_encoder确保所有字段都能被BSON正确编码
    user_doc_to_insert = jsonable_encoder(new_user_db)

    result = await user_collection.insert_one(user_doc_to_insert)
    
    created_user_doc = await user_collection.find_one({"_id": result.inserted_id})
    if created_user_doc:
        return UserInDB(**created_user_doc)
    
    # 理论上不应该到这里，除非发生非常罕见的并发问题
    raise Exception("Failed to create user or retrieve it after creation.")


async def update_user_info(user_id: PyObjectId, nick_name: Optional[str], avatar_url: Optional[str]) -> Optional[UserInDB]:
    user_collection = get_user_collection()
    update_data = {}
    if nick_name is not None:
        update_data["nickName"] = nick_name
    if avatar_url is not None:
        update_data["avatarUrl"] = avatar_url
    
    # 如果没有需要更新的字段，直接返回当前用户信息
    if not update_data:
        return await get_user_by_id(user_id)

    update_data["updatedAt"] = datetime.now(timezone.utc)
    
    # 虽然这里的update_data都是基础类型，但保持使用jsonable_encoder是好习惯
    update_doc = jsonable_encoder(update_data)

    result = await user_collection.update_one(
        {"_id": str(user_id)},
        {"$set": update_doc}
    )
    
    # 无论是否真的修改了内容(可能传入的值和原来一样)，只要匹配到了用户，就返回更新后的用户信息
    if result.matched_count >= 1:
        return await get_user_by_id(user_id)
        
    return None # 如果用户ID不存在，则返回None
