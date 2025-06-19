# app/models/reminder_models.py
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, time # 导入Python的time类型
from app.models.common_models import BaseDBModel, PyObjectId

class ReminderBase(BaseModel):
    content: str
    time: time # 使用Python的time类型，例如 time(8, 0)
    repeat: List[str] = Field(default_factory=list, description="0-6 (周日-周六)") # 与小程序一致
    enabled: bool = Field(default=True)

class ReminderCreate(ReminderBase):
    deviceId: PyObjectId

class ReminderUpdate(BaseModel): # 用于更新
    content: Optional[str] = None
    time: Optional[time] = None
    repeat: Optional[List[str]] = None
    enabled: Optional[bool] = None

class ReminderInDB(BaseDBModel, ReminderCreate):
    nextTriggerAt: Optional[datetime] = None
    lastConfirmedAt: Optional[datetime] = None

class ReminderPublic(BaseDBModel, ReminderBase):
    id: PyObjectId
    deviceId: PyObjectId
    repeatText: Optional[str] = None 
    pass
