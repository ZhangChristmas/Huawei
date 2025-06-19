# app/services/reminder_service.py

from typing import List, Optional
from datetime import datetime, timezone, time
from fastapi.encoders import jsonable_encoder

from app.db.mongodb_utils import get_reminder_collection
from app.models.common_models import PyObjectId
from app.models.reminder_models import ReminderCreate, ReminderInDB, ReminderUpdate, ReminderPublic
from app.services.contact_service import check_device_ownership

def calculate_repeat_text_from_data(repeat_days_str: List[str]) -> str:
    if not repeat_days_str:
        return "不重复"
    
    try:
        repeat_days_int = sorted([int(d) for d in repeat_days_str])
    except ValueError:
        return "重复规则错误"

    if len(repeat_days_int) == 7 and all(d in repeat_days_int for d in range(7)):
        return "每天"
    
    if repeat_days_int == [1, 2, 3, 4, 5]:
        return "工作日"
    if repeat_days_int == [0, 6]:
        return "周末"

    week_map = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    try:
        return "每周" + "、".join([week_map[day_int] for day_int in repeat_days_int])
    except IndexError:
        return "重复规则错误"

async def create_reminder_for_device(device_db_id: PyObjectId, user_id: PyObjectId, reminder_in: ReminderCreate) -> Optional[ReminderInDB]:
    if not await check_device_ownership(device_db_id, user_id):
        return None

    reminder_collection = get_reminder_collection()
    if reminder_in.deviceId != device_db_id:
        reminder_in.deviceId = device_db_id

    new_reminder_db_obj = ReminderInDB(**reminder_in.model_dump(), nextTriggerAt=None)
    reminder_doc_to_insert = jsonable_encoder(new_reminder_db_obj) # <--【修正】

    result = await reminder_collection.insert_one(reminder_doc_to_insert)
    created_doc = await reminder_collection.find_one({"_id": result.inserted_id})
    if created_doc:
        return ReminderInDB(**created_doc)
    return None

async def get_reminders_for_device(device_db_id: PyObjectId, user_id: PyObjectId) -> List[ReminderPublic]:
    if not await check_device_ownership(device_db_id, user_id):
        return []
    reminder_collection = get_reminder_collection()
    reminders_cursor = reminder_collection.find({"deviceId": str(device_db_id)})
    
    results = []
    async for doc in reminders_cursor:
        reminder_db = ReminderInDB(**doc)
        public_reminder = ReminderPublic.model_validate(reminder_db)
        public_reminder.repeatText = calculate_repeat_text_from_data(reminder_db.repeat)
        results.append(public_reminder)
    return results

async def get_reminder_detail_for_device(device_db_id: PyObjectId, reminder_id: PyObjectId, user_id: PyObjectId) -> Optional[ReminderPublic]:
    if not await check_device_ownership(device_db_id, user_id):
        return None
    reminder_collection = get_reminder_collection()
    reminder_doc = await reminder_collection.find_one({"_id": str(reminder_id), "deviceId": str(device_db_id)})
    if reminder_doc:
        reminder_db = ReminderInDB(**reminder_doc)
        public_reminder = ReminderPublic.model_validate(reminder_db)
        public_reminder.repeatText = calculate_repeat_text_from_data(reminder_db.repeat)
        return public_reminder
    return None

async def update_reminder_for_device(
    device_db_id: PyObjectId,
    reminder_id: PyObjectId,
    user_id: PyObjectId,
    reminder_update_data: ReminderUpdate
) -> Optional[ReminderInDB]:
    if not await check_device_ownership(device_db_id, user_id):
        return None

    reminder_collection = get_reminder_collection()
    update_doc_fields = reminder_update_data.model_dump(exclude_unset=True)
    update_doc = jsonable_encoder({k: v for k, v in update_doc_fields.items() if v is not None}) # <--【修正】

    if not update_doc:
        updated_doc = await reminder_collection.find_one({"_id": str(reminder_id)})
        return ReminderInDB(**updated_doc) if updated_doc else None

    update_doc["updatedAt"] = datetime.now(timezone.utc)

    result = await reminder_collection.update_one(
        {"_id": str(reminder_id), "deviceId": str(device_db_id)},
        {"$set": update_doc}
    )
    if result.modified_count == 1 or result.matched_count == 1:
        updated_doc = await reminder_collection.find_one({"_id": str(reminder_id)})
        return ReminderInDB(**updated_doc) if updated_doc else None
    return None

async def delete_reminder_for_device(device_db_id: PyObjectId, reminder_id: PyObjectId, user_id: PyObjectId) -> bool:
    if not await check_device_ownership(device_db_id, user_id):
        return False
    reminder_collection = get_reminder_collection()
    result = await reminder_collection.delete_one({"_id": str(reminder_id), "deviceId": str(device_db_id)})
    return result.deleted_count == 1
