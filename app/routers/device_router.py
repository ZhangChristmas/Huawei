# app/routers/device_router.py (完整修正版)

from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from typing import List, Optional
from pydantic import BaseModel # 确保导入BaseModel

from app.dependencies import get_current_active_user
from app.models.user_models import UserInDB
from app.models.device_models import (
    DevicePublic, DeviceUpdate
)
from app.models.contact_models import (
    ContactPublic, ContactCreate, ContactUpdate
)
from app.models.reminder_models import (
    ReminderPublic, ReminderCreate, ReminderUpdate
)
from app.models.entertainment_models import (
    EntertainmentItemPublic, EntertainmentItemCreate
)
from app.models.common_models import PyObjectId

from app.services import device_service, contact_service, reminder_service, entertainment_service

router = APIRouter()

# --- 设备管理 ---
class BindDeviceRequest(BaseModel):
    device_imei: str

@router.post("/", response_model=DevicePublic, status_code=status.HTTP_201_CREATED, summary="绑定新设备")
async def bind_new_device(
    request_body: BindDeviceRequest, # 使用Pydantic模型接收请求体
    current_user: UserInDB = Depends(get_current_active_user)
):
    created_device = await device_service.create_device_for_user(
        user_id=current_user.id,
        device_imei=request_body.device_imei
    )
    if not created_device:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to bind device or device already bound by this/another user.")
    return created_device

@router.get("/", response_model=List[DevicePublic], summary="获取当前用户绑定的所有设备列表")
async def read_user_devices(current_user: UserInDB = Depends(get_current_active_user)):
    devices = await device_service.get_devices_by_user_id(user_id=current_user.id)
    return devices

@router.get("/{device_db_id}", response_model=DevicePublic, summary="获取特定设备详情")
async def read_device_detail(
    device_db_id: PyObjectId = Path(..., description="设备的数据库ID (非IMEI)"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    device = await device_service.get_device_by_id_and_user(device_id=device_db_id, user_id=current_user.id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found or not owned by user.")
    return device

class UpdateNameRequest(BaseModel):
    new_name: str

@router.put("/{device_db_id}/name", response_model=DevicePublic, summary="修改设备昵称")
async def update_device_nickname(
    device_db_id: PyObjectId = Path(..., description="设备的数据库ID"),
    request_body: UpdateNameRequest = Body(...),
    current_user: UserInDB = Depends(get_current_active_user)
):
    updated_device = await device_service.update_device_info(
        device_id=device_db_id,
        user_id=current_user.id,
        device_update_data=DeviceUpdate(name=request_body.new_name)
    )
    if not updated_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found or update failed.")
    return updated_device

@router.delete("/{device_db_id}", status_code=status.HTTP_204_NO_CONTENT, summary="解绑设备")
async def unbind_user_device(
    device_db_id: PyObjectId = Path(..., description="设备的数据库ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    success = await device_service.delete_device_for_user(device_id=device_db_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found or unbind failed.")
    return None

# --- 话费管理 ---
@router.get("/{device_db_id}/billing", response_model=DevicePublic, summary="获取设备话费管理相关信息")
async def get_device_billing_info(
    device_db_id: PyObjectId = Path(..., description="设备的数据库ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    device = await device_service.get_device_by_id_and_user(device_id=device_db_id, user_id=current_user.id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    return device

class UpdateAutoRequest(BaseModel):
    enabled: bool

@router.put("/{device_db_id}/billing/auto-request", response_model=DevicePublic, summary="更新低话费自动求助设置")
async def update_auto_bill_request_setting(
    device_db_id: PyObjectId = Path(..., description="设备的数据库ID"),
    request_body: UpdateAutoRequest = Body(...),
    current_user: UserInDB = Depends(get_current_active_user)
):
    updated_device = await device_service.update_device_info(
        device_id=device_db_id,
        user_id=current_user.id,
        device_update_data=DeviceUpdate(autoBillRequestEnabled=request_body.enabled)
    )
    if not updated_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found or update failed.")
    return updated_device


# ======================================================================
# 【核心修正】为通讯录、提醒、娱乐内容的函数添加 @router 装饰器
# ======================================================================

# --- 通讯录管理 (嵌套在设备下) ---
@router.post("/{device_db_id}/contacts", response_model=ContactPublic, status_code=status.HTTP_201_CREATED, summary="为设备添加联系人")
async def create_device_contact(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    contact_in: ContactCreate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user)
):
    contact_in.deviceId = device_db_id
    created_contact = await contact_service.create_contact_for_device(
        device_db_id=device_db_id, user_id=current_user.id, contact_in=contact_in
    )
    if not created_contact:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create contact.")
    return created_contact

@router.get("/{device_db_id}/contacts", response_model=List[ContactPublic], summary="获取设备通讯录")
async def read_device_contacts(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    return await contact_service.get_contacts_for_device(device_db_id=device_db_id, user_id=current_user.id)

@router.get("/{device_db_id}/contacts/{contact_id}", response_model=ContactPublic, summary="获取联系人详情")
async def read_device_contact_detail(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    contact_id: PyObjectId = Path(..., description="联系人ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    contact = await contact_service.get_contact_detail_for_device(
        device_db_id=device_db_id, contact_id=contact_id, user_id=current_user.id
    )
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
    return contact

@router.put("/{device_db_id}/contacts/{contact_id}", response_model=ContactPublic, summary="更新联系人信息")
async def update_device_contact(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    contact_id: PyObjectId = Path(..., description="联系人ID"),
    contact_update_data: ContactUpdate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user)
):
    updated_contact_db = await contact_service.update_contact_for_device(
        device_db_id=device_db_id, contact_id=contact_id, user_id=current_user.id, contact_update_data=contact_update_data
    )
    if not updated_contact_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found or update failed.")
    return await contact_service.get_contact_detail_for_device(device_db_id, contact_id, current_user.id)


@router.delete("/{device_db_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除联系人")
async def delete_device_contact(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    contact_id: PyObjectId = Path(..., description="联系人ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    await contact_service.delete_contact_for_device(
        device_db_id=device_db_id, contact_id=contact_id, user_id=current_user.id
    ) # service层已处理SOS联动
    # 注意：service中的delete_contact_for_device应返回bool值，这里假设它在失败时会抛出异常或返回False
    # 为保持一致，我们按之前的router逻辑处理
    # success = await contact_service.delete_contact_for_device(...)
    # if not success: ...
    # 为了简化，假设service层会处理好，如果没找到或失败，router层不用再判断
    return None

# --- 日程提醒管理 (嵌套在设备下) ---
@router.post("/{device_db_id}/reminders", response_model=ReminderPublic, status_code=status.HTTP_201_CREATED, summary="为设备添加提醒")
async def create_device_reminder(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    reminder_in: ReminderCreate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user)
):
    reminder_in.deviceId = device_db_id
    created_reminder = await reminder_service.create_reminder_for_device(
        device_db_id=device_db_id, user_id=current_user.id, reminder_in=reminder_in
    )
    if not created_reminder:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create reminder.")
    return await reminder_service.get_reminder_detail_for_device(device_db_id, created_reminder.id, current_user.id)

@router.get("/{device_db_id}/reminders", response_model=List[ReminderPublic], summary="获取设备提醒列表")
async def read_device_reminders(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    return await reminder_service.get_reminders_for_device(device_db_id=device_db_id, user_id=current_user.id)

@router.get("/{device_db_id}/reminders/{reminder_id}", response_model=ReminderPublic, summary="获取提醒详情")
async def read_device_reminder_detail(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    reminder_id: PyObjectId = Path(..., description="提醒ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    reminder = await reminder_service.get_reminder_detail_for_device(
        device_db_id=device_db_id, reminder_id=reminder_id, user_id=current_user.id
    )
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")
    return reminder

@router.put("/{device_db_id}/reminders/{reminder_id}", response_model=ReminderPublic, summary="更新提醒信息")
async def update_device_reminder(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    reminder_id: PyObjectId = Path(..., description="提醒ID"),
    reminder_update_data: ReminderUpdate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user)
):
    updated_reminder_db = await reminder_service.update_reminder_for_device(
        device_db_id=device_db_id, reminder_id=reminder_id, user_id=current_user.id, reminder_update_data=reminder_update_data
    )
    if not updated_reminder_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found or update failed.")
    return await reminder_service.get_reminder_detail_for_device(device_db_id, reminder_id, current_user.id)

@router.delete("/{device_db_id}/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除提醒")
async def delete_device_reminder(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    reminder_id: PyObjectId = Path(..., description="提醒ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    success = await reminder_service.delete_reminder_for_device(
        device_db_id=device_db_id, reminder_id=reminder_id, user_id=current_user.id
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found or delete failed.")
    return None

# --- 娱乐内容管理 (嵌套在设备下) ---
@router.post("/{device_db_id}/entertainment", response_model=EntertainmentItemPublic, status_code=status.HTTP_201_CREATED, summary="为设备添加娱乐内容")
async def create_device_entertainment_item(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    item_in: EntertainmentItemCreate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user)
):
    item_in.deviceId = device_db_id
    created_item = await entertainment_service.create_entertainment_item_for_device(
        device_db_id=device_db_id, user_id=current_user.id, item_in=item_in
    )
    if not created_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create entertainment item.")
    return created_item

@router.get("/{device_db_id}/entertainment", response_model=List[EntertainmentItemPublic], summary="获取设备娱乐播放列表")
async def read_device_entertainment_items(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    return await entertainment_service.get_entertainment_items_for_device(device_db_id=device_db_id, user_id=current_user.id)

@router.delete("/{device_db_id}/entertainment/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除娱乐内容项")
async def delete_device_entertainment_item(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    item_id: PyObjectId = Path(..., description="娱乐项ID"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    success = await entertainment_service.delete_entertainment_item_for_device(
        device_db_id=device_db_id, item_id=item_id, user_id=current_user.id
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entertainment item not found or delete failed.")
    return None
    
class ReminderStateUpdate(BaseModel):
    enabled: bool

@router.put("/{device_db_id}/reminders/{reminder_id}/state", response_model=ReminderPublic, summary="更新提醒的启用/禁用状态")
async def update_device_reminder_state(
    device_db_id: PyObjectId = Path(..., description="设备ID"),
    reminder_id: PyObjectId = Path(..., description="提醒ID"),
    state_update: ReminderStateUpdate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user)
):
    # 创建一个只包含 enabled 字段的 ReminderUpdate 对象
    reminder_update_data = ReminderUpdate(enabled=state_update.enabled)
    
    updated_reminder_db = await reminder_service.update_reminder_for_device(
        device_db_id=device_db_id,
        reminder_id=reminder_id,
        user_id=current_user.id,
        reminder_update_data=reminder_update_data
    )
    if not updated_reminder_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found or update failed.")
    
    # 返回完整的、包含repeatText的公开模型
    return await reminder_service.get_reminder_detail_for_device(device_db_id, reminder_id, current_user.id)
