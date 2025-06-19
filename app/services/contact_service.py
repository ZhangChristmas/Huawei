# app/services/contact_service.py

from typing import List, Optional
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder

from app.db.mongodb_utils import get_contact_collection, get_device_collection
from app.models.common_models import PyObjectId
from app.models.contact_models import ContactCreate, ContactInDB, ContactUpdate, ContactPublic
from app.models.device_models import DeviceInDB, DeviceUpdate # <--【修正】导入 DeviceUpdate
from app.services import device_service # 导入device_service

async def check_device_ownership(device_db_id: PyObjectId, user_id: PyObjectId) -> bool:
    """辅助函数：检查设备是否属于当前用户"""
    device_collection = get_device_collection()
    device = await device_collection.find_one({"_id": str(device_db_id), "userId": str(user_id)})
    return device is not None

async def create_contact_for_device(device_db_id: PyObjectId, user_id: PyObjectId, contact_in: ContactCreate) -> Optional[ContactInDB]:
    if not await check_device_ownership(device_db_id, user_id):
        return None

    contact_collection = get_contact_collection()
    
    contact_data_for_db = contact_in.model_dump(exclude={"isSosIntent"})
    new_contact_db_obj = ContactInDB(**contact_data_for_db)
    
    contact_doc_to_insert = jsonable_encoder(new_contact_db_obj) # <--【修正】使用jsonable_encoder

    result = await contact_collection.insert_one(contact_doc_to_insert)
    created_doc = await contact_collection.find_one({"_id": result.inserted_id})
    
    if created_doc:
        created_contact_db = ContactInDB(**created_doc)
        if contact_in.isSosIntent and created_contact_db.phone:
            await device_service.update_device_info(
                device_id=device_db_id,
                user_id=user_id,
                device_update_data=DeviceUpdate(sosContactPhone=created_contact_db.phone)
            )
            print(f"Device {device_db_id} SOS contact phone updated to {created_contact_db.phone} on contact creation.")
        return created_contact_db
    return None

async def get_contacts_for_device(device_db_id: PyObjectId, user_id: PyObjectId) -> List[ContactPublic]:
    if not await check_device_ownership(device_db_id, user_id):
        return []

    contact_collection = get_contact_collection()
    device = await device_service.get_device_by_id_and_user(device_id=device_db_id, user_id=user_id)
    sos_phone = device.sosContactPhone if device else None

    contacts_cursor = contact_collection.find({"deviceId": str(device_db_id)})
    public_contacts = []
    async for doc in contacts_cursor:
        contact_db = ContactInDB(**doc)
        is_sos = (sos_phone == contact_db.phone) if sos_phone else False
        
        contact_public_data = contact_db.model_dump()
        contact_public_data["isSosForDisplay"] = is_sos
        public_contacts.append(ContactPublic(**contact_public_data))
    return public_contacts

async def get_contact_detail_for_device(device_db_id: PyObjectId, contact_id: PyObjectId, user_id: PyObjectId) -> Optional[ContactPublic]:
    if not await check_device_ownership(device_db_id, user_id):
        return None

    contact_collection = get_contact_collection()
    contact_doc = await contact_collection.find_one({"_id": str(contact_id), "deviceId": str(device_db_id)})
    if contact_doc:
        contact_db = ContactInDB(**contact_doc)
        device = await device_service.get_device_by_id_and_user(device_id=device_db_id, user_id=user_id)
        sos_phone = device.sosContactPhone if device else None
        is_sos = (sos_phone == contact_db.phone) if sos_phone else False
        
        contact_public_data = contact_db.model_dump()
        contact_public_data["isSosForDisplay"] = is_sos
        return ContactPublic(**contact_public_data)
    return None


async def update_contact_for_device(
    device_db_id: PyObjectId, 
    contact_id: PyObjectId, 
    user_id: PyObjectId, 
    contact_update_data: ContactUpdate
) -> Optional[ContactInDB]:
    if not await check_device_ownership(device_db_id, user_id):
        return None

    contact_collection = get_contact_collection()
    
    update_doc_fields = contact_update_data.model_dump(exclude_unset=True, exclude={"isSosIntent"})
    update_doc = jsonable_encoder({k: v for k, v in update_doc_fields.items() if v is not None}) # <--【修正】

    original_contact_doc = await contact_collection.find_one({"_id": str(contact_id), "deviceId": str(device_db_id)})
    if not original_contact_doc:
        return None
    original_contact = ContactInDB(**original_contact_doc)

    if update_doc:
        update_doc["updatedAt"] = datetime.now(timezone.utc)
        await contact_collection.update_one(
            {"_id": str(contact_id), "deviceId": str(device_db_id)},
            {"$set": update_doc}
        )
    
    updated_phone = update_doc.get("phone", original_contact.phone)

    if contact_update_data.isSosIntent is True and updated_phone:
        await device_service.update_device_info(
            device_id=device_db_id,
            user_id=user_id,
            device_update_data=DeviceUpdate(sosContactPhone=updated_phone)
        )
    elif contact_update_data.isSosIntent is False:
        device = await device_service.get_device_by_id_and_user(device_id=device_db_id, user_id=user_id)
        if device and device.sosContactPhone == original_contact.phone:
             await device_service.update_device_info(
                device_id=device_db_id,
                user_id=user_id,
                device_update_data=DeviceUpdate(sosContactPhone=None)
            )

    updated_contact_doc = await contact_collection.find_one({"_id": str(contact_id), "deviceId": str(device_db_id)})
    return ContactInDB(**updated_contact_doc) if updated_contact_doc else None


async def delete_contact_for_device(device_db_id: PyObjectId, contact_id: PyObjectId, user_id: PyObjectId) -> bool:
    if not await check_device_ownership(device_db_id, user_id):
        return False
        
    contact_to_delete_public = await get_contact_detail_for_device(device_db_id, contact_id, user_id)
    if contact_to_delete_public:
        if contact_to_delete_public.isSosForDisplay:
            await device_service.update_device_info(
                device_id=device_db_id,
                user_id=user_id,
                device_update_data=DeviceUpdate(sosContactPhone=None)
            )
            print(f"Device {device_db_id} SOS contact phone cleared as contact {contact_id} was deleted.")

    contact_collection = get_contact_collection()
    result = await contact_collection.delete_one({"_id": str(contact_id), "deviceId": str(device_db_id)})
    return result.deleted_count == 1
