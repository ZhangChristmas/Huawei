# app/services/device_service.py
from typing import List, Optional
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder

from app.db.mongodb_utils import (
    get_device_collection,
    get_contact_collection,
    get_reminder_collection,
    get_entertainment_item_collection
)
from app.models.common_models import PyObjectId
from app.models.device_models import DeviceCreate, DeviceInDB, DeviceUpdate, DeviceStatusUpdate
from app.models.user_models import UserInDB

async def create_device_for_user(user_id: PyObjectId, device_imei: str, initial_name: Optional[str] = None) -> Optional[DeviceInDB]:
    device_collection = get_device_collection()
    existing_device_by_imei = await device_collection.find_one({"deviceId": device_imei})
    if existing_device_by_imei:
        # 如果设备已存在，检查是否属于当前用户
        if str(existing_device_by_imei.get("userId")) == str(user_id):
             # 已被当前用户绑定，直接返回该设备信息
             return DeviceInDB(**existing_device_by_imei)
        else:
            # 已被其他用户绑定
            return None

    device_data_to_create = DeviceCreate(
        deviceId=device_imei,
        userId=user_id,
        name=initial_name or f"安心通设备-{device_imei[-4:]}"
    )
    
    new_device_db_obj = DeviceInDB(**device_data_to_create.model_dump())
    device_doc_to_insert = jsonable_encoder(new_device_db_obj)

    result = await device_collection.insert_one(device_doc_to_insert)
    
    created_doc = await device_collection.find_one({"_id": result.inserted_id})
    if created_doc:
        return DeviceInDB(**created_doc)
    return None

async def get_devices_by_user_id(user_id: PyObjectId) -> List[DeviceInDB]:
    device_collection = get_device_collection()
    devices_cursor = device_collection.find({"userId": str(user_id)})
    return [DeviceInDB(**doc) async for doc in devices_cursor]

async def get_device_by_id_and_user(device_id: PyObjectId, user_id: PyObjectId) -> Optional[DeviceInDB]:
    device_collection = get_device_collection()
    device_doc = await device_collection.find_one({"_id": str(device_id), "userId": str(user_id)})
    if device_doc:
        return DeviceInDB(**device_doc)
    return None

async def get_device_by_imei(device_imei: str) -> Optional[DeviceInDB]:
    device_collection = get_device_collection()
    device_doc = await device_collection.find_one({"deviceId": device_imei})
    if device_doc:
        return DeviceInDB(**device_doc)
    return None

async def update_device_info(device_id: PyObjectId, user_id: PyObjectId, device_update_data: DeviceUpdate) -> Optional[DeviceInDB]:
    device_collection = get_device_collection()
    
    update_doc_fields = device_update_data.model_dump(exclude_unset=True)
    update_doc = jsonable_encoder({k: v for k, v in update_doc_fields.items() if v is not None})
    
    if not update_doc:
        return await get_device_by_id_and_user(device_id, user_id)

    update_doc["updatedAt"] = datetime.now(timezone.utc)

    result = await device_collection.update_one(
        {"_id": str(device_id), "userId": str(user_id)},
        {"$set": update_doc}
    )
    if result.matched_count >= 1:
        return await get_device_by_id_and_user(device_id, user_id)
    return None

async def update_device_status_by_imei(device_imei: str, status_update: DeviceStatusUpdate) -> Optional[DeviceInDB]:
    device_collection = get_device_collection()
    device = await get_device_by_imei(device_imei)
    if not device:
        return None

    update_doc_fields = status_update.model_dump(exclude_unset=True)
    update_doc = jsonable_encoder({k: v for k, v in update_doc_fields.items() if v is not None})

    if not update_doc:
        return device

    if "lastLocation" in update_doc and update_doc["lastLocation"]:
        loc_data = update_doc["lastLocation"]
        if "timestamp" not in loc_data or not loc_data["timestamp"]:
            loc_data["timestamp"] = datetime.now(timezone.utc)
        update_doc["lastLocation"] = loc_data

    update_doc["updatedAt"] = datetime.now(timezone.utc)

    result = await device_collection.update_one(
        {"deviceId": device_imei},
        {"$set": update_doc}
    )
    if result.matched_count >= 1:
        updated_device_doc = await device_collection.find_one({"deviceId": device_imei})
        if updated_device_doc:
            return DeviceInDB(**updated_device_doc)
    return device

async def delete_device_for_user(device_id: PyObjectId, user_id: PyObjectId) -> bool:
    device_collection = get_device_collection()
    device = await get_device_by_id_and_user(device_id, user_id)
    if not device:
        return False

    delete_result = await device_collection.delete_one({"_id": str(device_id), "userId": str(user_id)})
    if delete_result.deleted_count == 1:
        print(f"Device {device_id} deleted. Cleaning up associated data...")
        # 清理关联数据
        await get_contact_collection().delete_many({"deviceId": str(device_id)})
        await get_reminder_collection().delete_many({"deviceId": str(device_id)})
        await get_entertainment_item_collection().delete_many({"deviceId": str(device_id)})
        # 可以添加其他关联数据的清理，如通知、SOS记录等
        return True
    return False
