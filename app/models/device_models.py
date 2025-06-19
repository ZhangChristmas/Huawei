# app/models/device_models.py
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from app.models.common_models import BaseDBModel, PyObjectId
from datetime import datetime

class DeviceLocation(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    timestamp: Optional[datetime] = None # 位置上报时间

class DeviceBase(BaseModel):
    name: str = Field(default="我的安心通设备")
    sim: Optional[str] = None
    isOnline: bool = Field(default=False)
    battery: Optional[int] = Field(None, ge=0, le=100)
    signal: Optional[int] = Field(None, ge=0, le=5)
    firmwareVersion: Optional[str] = None
    lastLocation: Optional[DeviceLocation] = None
    sosContactPhone: Optional[str] = Field(None, description="设备绑定的唯一SOS紧急联系电话")
    sosSmsTemplate: str = Field(default="【安心通】设备[{deviceName}]发起了紧急呼叫！位置：{location}")
    autoBillRequestEnabled: bool = Field(default=True)
    billReminderContacts: List[str] = Field(default_factory=list, description="接收话费不足通知的子女手机号列表")

class DeviceCreateData(DeviceBase): # 用于创建设备时，不包含userId和deviceId (IMEI)
    pass

class DeviceCreate(DeviceBase): # 用于服务层创建完整设备对象
    deviceId: str = Field(description="设备的唯一标识 (如IMEI)") # unique在数据库层面实现
    userId: PyObjectId

class DeviceUpdate(BaseModel): # 用于更新设备信息
    name: Optional[str] = None
    sim: Optional[str] = None
    sosContactPhone: Optional[str] = None
    sosSmsTemplate: Optional[str] = None
    autoBillRequestEnabled: Optional[bool] = None
    billReminderContacts: Optional[List[str]] = None
    # isOnline, battery, signal, firmwareVersion, lastLocation 由设备MQTT上报更新，不由API直接修改

class DeviceInDB(BaseDBModel, DeviceCreate): # 存储在DB中的完整模型
    pass

class DevicePublic(BaseDBModel, DeviceBase): # 返回给小程序，包含ID
    id: PyObjectId
    deviceId: str # IMEI也一并返回
    userId: PyObjectId # 有时前端也需要知道所属用户ID
    pass

# 用于设备MQTT上报状态
class DeviceStatusUpdate(BaseModel):
    isOnline: Optional[bool] = None
    battery: Optional[int] = Field(None, ge=0, le=100)
    signal: Optional[int] = Field(None, ge=0, le=5)
    firmwareVersion: Optional[str] = None
    lastLocation: Optional[DeviceLocation] = None
