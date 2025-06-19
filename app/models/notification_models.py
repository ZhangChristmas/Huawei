# app/models/notification_models.py
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.common_models import BaseDBModel, PyObjectId
from app.models.device_models import DeviceLocation # 导入DeviceLocation

class NotificationBase(BaseModel):
    userId: PyObjectId # 推送给哪个子女用户
    deviceId: Optional[PyObjectId] = None # 关联的设备 (可选)
    deviceName: Optional[str] = None
    type: str # 'SOS', 'Billing', 'LowBattery', 'ReminderDue', 'DeviceOffline', 'Unbind' 等
    title: Optional[str] = None # 后端可以根据type和content自动生成
    content: str
    time: datetime = Field(default_factory=datetime.utcnow)
    isRead: bool = Field(default=False)
    # payload可以更具体化，或者保持通用字典
    # 例如，对于SOS，payload可以包含DeviceLocation
    payload: Optional[Dict[str, Any]] = None # 例如: {"latitude": 30.0, "longitude": 120.0} for SOS

class NotificationCreate(NotificationBase):
    pass

class NotificationInDB(BaseDBModel, NotificationBase):
    pass

class NotificationPublic(BaseDBModel, NotificationBase): # 返回给小程序的通知列表
    id: PyObjectId
    # 根据type和payload，可以添加一些便利字段给前端
    location: Optional[DeviceLocation] = None # 如果type是SOS且payload有位置

    # Pydantic v2: model_post_init for post-initialization logic
    # Pydantic v1: @root_validator or similar for derived fields
    # Example for Pydantic v1 using root_validator (adapt for v2 if needed)
    # from pydantic import root_validator
    # @root_validator(pre=False, skip_on_failure=True)
    # def populate_location_from_payload(cls, values):
    #     type_ = values.get("type")
    #     payload = values.get("payload")
    #     if type_ == "SOS" and payload and "latitude" in payload and "longitude" in payload:
    #         values["location"] = DeviceLocation(**payload)
    #     return values
    pass

# SOS Alert记录，与通知区分，更侧重事件的持久化和状态跟踪
class SosAlertBase(BaseModel):
    deviceId: PyObjectId
    userId: PyObjectId # 触发SOS时设备所属的用户 (方便查询)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    location: Optional[DeviceLocation] = None
    status: str = Field(default="pending", description="pending, acknowledged, resolved")
    acknowledgedBy: Optional[PyObjectId] = None # 确认处理的子女用户ID
    acknowledgedAt: Optional[datetime] = None
    # 还可以加入通话记录ID等关联信息

class SosAlertCreate(SosAlertBase):
    pass

class SosAlertInDB(BaseDBModel, SosAlertBase):
    pass

class SosAlertPublic(BaseDBModel, SosAlertBase):
    id: PyObjectId
    deviceName: Optional[str] = None # 后端填充
    pass
