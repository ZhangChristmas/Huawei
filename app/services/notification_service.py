# app/services/notification_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder

from app.db.mongodb_utils import get_notification_collection, get_device_collection
from app.models.common_models import PyObjectId
from app.models.notification_models import NotificationCreate, NotificationInDB, NotificationPublic, DeviceLocation

async def create_notification(notification_in: NotificationCreate) -> Optional[NotificationInDB]:
    notification_collection = get_notification_collection()

    if notification_in.deviceId and not notification_in.deviceName:
        device_collection = get_device_collection()
        device_doc = await device_collection.find_one({"_id": str(notification_in.deviceId)})
        if device_doc:
            notification_in.deviceName = device_doc.get("name")
    
    if not notification_in.title:
        if notification_in.type == "SOS":
            notification_in.title = f"紧急呼叫: {notification_in.deviceName or '未知设备'}"
        elif notification_in.type == "Billing":
            notification_in.title = f"话费提醒: {notification_in.deviceName or '未知设备'}"
        elif notification_in.type == "LowBattery":
            notification_in.title = f"低电量警告: {notification_in.deviceName or '未知设备'}"
        else:
            notification_in.title = "系统通知"

    new_notification_db_obj = NotificationInDB(**notification_in.model_dump())
    notification_doc_to_insert = jsonable_encoder(new_notification_db_obj)

    result = await notification_collection.insert_one(notification_doc_to_insert)
    created_doc = await notification_collection.find_one({"_id": result.inserted_id})
    if created_doc:
        print(f"Notification created (ID: {result.inserted_id}). TODO: Trigger push notification.")
        return NotificationInDB(**created_doc)
    return None

async def get_notifications_for_user(user_id: PyObjectId, skip: int = 0, limit: int = 20) -> List[NotificationPublic]:
    notification_collection = get_notification_collection()
    notifications_cursor = notification_collection.find(
        {"userId": str(user_id)}
    ).sort("time", -1).skip(skip).limit(limit)
    
    results = []
    async for doc in notifications_cursor:
        notif_db = NotificationInDB(**doc)
        notif_public_data = notif_db.model_dump()
        
        if notif_db.type == "SOS" and notif_db.payload and \
           "latitude" in notif_db.payload and "longitude" in notif_db.payload:
            try:
                loc_data = {
                    "latitude": float(notif_db.payload["latitude"]),
                    "longitude": float(notif_db.payload["longitude"]),
                    "address": notif_db.payload.get("address"),
                    "timestamp": notif_db.payload.get("timestamp")
                }
                notif_public_data["location"] = DeviceLocation(**loc_data)
            except (ValueError, TypeError) as e:
                print(f"Error parsing location from notification payload for {notif_db.id}: {e}")
                notif_public_data["location"] = None
        else:
            notif_public_data["location"] = None
            
        results.append(NotificationPublic(**notif_public_data))
    return results

async def get_notification_by_id_for_user(notification_id: PyObjectId, user_id: PyObjectId) -> Optional[NotificationPublic]:
    notification_collection = get_notification_collection()
    notification_doc = await notification_collection.find_one(
        {"_id": str(notification_id), "userId": str(user_id)}
    )
    if notification_doc:
        notif_db = NotificationInDB(**notification_doc)
        notif_public_data = notif_db.model_dump()
        if notif_db.type == "SOS" and notif_db.payload and \
           "latitude" in notif_db.payload and "longitude" in notif_db.payload:
            try:
                loc_data = {
                    "latitude": float(notif_db.payload["latitude"]),
                    "longitude": float(notif_db.payload["longitude"]),
                    "address": notif_db.payload.get("address"),
                    "timestamp": notif_db.payload.get("timestamp")
                }
                notif_public_data["location"] = DeviceLocation(**loc_data)
            except Exception as e:
                print(f"Error parsing location from notification payload for {notif_db.id}: {e}")
                notif_public_data["location"] = None
        else:
            notif_public_data["location"] = None
        return NotificationPublic(**notif_public_data)
    return None

async def mark_notification_read(notification_id: PyObjectId, user_id: PyObjectId) -> Optional[NotificationInDB]:
    notification_collection = get_notification_collection()
    update_data = {
        "isRead": True,
        "updatedAt": datetime.now(timezone.utc)
    }
    update_doc = jsonable_encoder(update_data)

    result = await notification_collection.update_one(
        {"_id": str(notification_id), "userId": str(user_id)},
        {"$set": update_doc}
    )
    if result.matched_count >= 1:
        updated_doc = await notification_collection.find_one({"_id": str(notification_id)})
        return NotificationInDB(**updated_doc) if updated_doc else None
    return None

async def mark_all_notifications_read_for_user(user_id: PyObjectId) -> int:
    notification_collection = get_notification_collection()
    update_data = {
        "isRead": True,
        "updatedAt": datetime.now(timezone.utc)
    }
    update_doc = jsonable_encoder(update_data)
    result = await notification_collection.update_many(
        {"userId": str(user_id), "isRead": False},
        {"$set": update_doc}
    )
    return result.modified_count

async def delete_notification_for_user(notification_id: PyObjectId, user_id: PyObjectId) -> bool:
    notification_collection = get_notification_collection()
    result = await notification_collection.delete_one(
        {"_id": str(notification_id), "userId": str(user_id)}
    )
    return result.deleted_count == 1

async def delete_all_notifications_for_user(user_id: PyObjectId) -> int:
    notification_collection = get_notification_collection()
    result = await notification_collection.delete_many({"userId": str(user_id)})
    return result.deleted_count
