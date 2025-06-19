# app/models/contact_models.py
from typing import Optional
from pydantic import BaseModel, Field
from app.models.common_models import BaseDBModel, PyObjectId

class ContactBase(BaseModel):
    name: str
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    dialectName: Optional[str] = None
    # isSos 字段由前端在创建/更新时传递意图，后端据此更新Device.sosContactPhone

class ContactCreate(ContactBase):
    deviceId: PyObjectId
    isSosIntent: bool = Field(default=False, description="是否意图将此联系人设为SOS") # 新增

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$")
    dialectName: Optional[str] = None
    isSosIntent: Optional[bool] = Field(None, description="是否意图将此联系人设为SOS或取消SOS") # 新增

class ContactInDB(BaseDBModel, ContactCreate):
    # isSosIntent 不直接存储在ContactDB中，它只是一个传递给service层的信号
    # 但如果为了方便，也可以选择存储，但其真实性依赖于Device.sosContactPhone
    pass

class ContactPublic(BaseDBModel, ContactBase):
    id: PyObjectId
    deviceId: PyObjectId
    isSosForDisplay: bool = Field(default=False, description="此联系人是否为当前设备的SOS号码 (后端填充)") # 新增
    pass
