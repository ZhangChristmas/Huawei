# app/services/entertainment_service.py

from typing import List, Optional
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder

from app.db.mongodb_utils import get_entertainment_item_collection
from app.models.common_models import PyObjectId
from app.models.entertainment_models import EntertainmentItemCreate, EntertainmentItemInDB, EntertainmentItemUpdate
from app.services.contact_service import check_device_ownership

async def create_entertainment_item_for_device(
    device_db_id: PyObjectId, user_id: PyObjectId, item_in: EntertainmentItemCreate
) -> Optional[EntertainmentItemInDB]:
    if not await check_device_ownership(device_db_id, user_id):
        return None
        
    item_collection = get_entertainment_item_collection()
    if item_in.deviceId != device_db_id:
        item_in.deviceId = device_db_id

    new_item_db_obj = EntertainmentItemInDB(**item_in.model_dump())
    item_doc_to_insert = jsonable_encoder(new_item_db_obj) # <--【修正】

    result = await item_collection.insert_one(item_doc_to_insert)
    created_doc = await item_collection.find_one({"_id": result.inserted_id})
    if created_doc:
        return EntertainmentItemInDB(**created_doc)
    return None

async def get_entertainment_items_for_device(device_db_id: PyObjectId, user_id: PyObjectId) -> List[EntertainmentItemInDB]:
    if not await check_device_ownership(device_db_id, user_id):
        return []
    item_collection = get_entertainment_item_collection()
    items_cursor = item_collection.find({"deviceId": str(device_db_id)})
    return [EntertainmentItemInDB(**doc) async for doc in items_cursor]

async def update_entertainment_item_for_device(
    device_db_id: PyObjectId,
    item_id: PyObjectId,
    user_id: PyObjectId,
    item_update_data: EntertainmentItemUpdate
) -> Optional[EntertainmentItemInDB]:
    if not await check_device_ownership(device_db_id, user_id):
        return None
        
    item_collection = get_entertainment_item_collection()
    update_doc_fields = item_update_data.model_dump(exclude_unset=True)
    update_doc = jsonable_encoder({k: v for k, v in update_doc_fields.items() if v is not None}) # <--【修正】

    if not update_doc:
        item_doc = await item_collection.find_one({"_id": str(item_id), "deviceId": str(device_db_id)})
        return EntertainmentItemInDB(**item_doc) if item_doc else None

    update_doc["updatedAt"] = datetime.now(timezone.utc)
    result = await item_collection.update_one(
        {"_id": str(item_id), "deviceId": str(device_db_id)},
        {"$set": update_doc}
    )
    if result.modified_count == 1 or result.matched_count == 1:
        updated_doc = await item_collection.find_one({"_id": str(item_id)})
        return EntertainmentItemInDB(**updated_doc) if updated_doc else None
    return None

async def delete_entertainment_item_for_device(device_db_id: PyObjectId, item_id: PyObjectId, user_id: PyObjectId) -> bool:
    if not await check_device_ownership(device_db_id, user_id):
        return False
    item_collection = get_entertainment_item_collection()
    result = await item_collection.delete_one({"_id": str(item_id), "deviceId": str(device_db_id)})
    return result.deleted_count == 1
