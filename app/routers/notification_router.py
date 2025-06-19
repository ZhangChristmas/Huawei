# app/routers/notification_router.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import List, Optional

from app.dependencies import get_current_active_user, get_current_user_id
from app.models.user_models import UserInDB # 虽然没直接用，但依赖中可能需要
from app.models.notification_models import NotificationPublic, PyObjectId
from app.services import notification_service

router = APIRouter()

@router.get("/", response_model=List[NotificationPublic], summary="获取当前用户的通知列表")
async def read_user_notifications(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="每页返回的记录数"),
    current_user_id: PyObjectId = Depends(get_current_user_id)
):
    notifications = await notification_service.get_notifications_for_user(
        user_id=current_user_id, skip=skip, limit=limit
    )
    return notifications

@router.get("/{notification_id}", response_model=NotificationPublic, summary="获取单条通知详情")
async def read_single_notification(
    notification_id: PyObjectId = Path(..., description="通知的数据库ID"),
    current_user_id: PyObjectId = Depends(get_current_user_id)
):
    notification = await notification_service.get_notification_by_id_for_user(
        notification_id=notification_id, user_id=current_user_id
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    return notification


@router.put("/{notification_id}/read", response_model=NotificationPublic, summary="标记单条通知为已读")
async def mark_single_notification_as_read(
    notification_id: PyObjectId = Path(..., description="通知的数据库ID"),
    current_user_id: PyObjectId = Depends(get_current_user_id)
):
    updated_notification_db = await notification_service.mark_notification_read(
        notification_id=notification_id, user_id=current_user_id
    )
    if not updated_notification_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found or already read.")
    
    # 需要将DB模型转换为Public模型并处理location
    public_notification = await notification_service.get_notification_by_id_for_user(
        notification_id=updated_notification_db.id, user_id=current_user_id
    ) # 重新获取以应用Public模型的转换逻辑
    if not public_notification: # 理论上不会发生，因为上面已经操作成功
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve notification after marking as read.")
    return public_notification


@router.put("/read-all", summary="标记所有未读通知为已读")
async def mark_all_user_notifications_as_read(
    current_user_id: PyObjectId = Depends(get_current_user_id)
):
    modified_count = await notification_service.mark_all_notifications_read_for_user(user_id=current_user_id)
    return {"message": f"{modified_count} notifications marked as read."}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除单条通知")
async def delete_single_notification(
    notification_id: PyObjectId = Path(..., description="通知的数据库ID"),
    current_user_id: PyObjectId = Depends(get_current_user_id)
):
    success = await notification_service.delete_notification_for_user(
        notification_id=notification_id, user_id=current_user_id
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found or delete failed.")
    return None # 204 No Content

@router.delete("/", summary="删除当前用户的所有通知") # 注意这个路径，如果前面有 /notifications 前缀，则是 DELETE /api/v1/notifications/
async def delete_all_user_notifications(
    current_user_id: PyObjectId = Depends(get_current_user_id)
):
    deleted_count = await notification_service.delete_all_notifications_for_user(user_id=current_user_id)
    return {"message": f"{deleted_count} notifications deleted."}
