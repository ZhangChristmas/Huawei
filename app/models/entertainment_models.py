# app/models/entertainment_models.py
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl
from app.models.common_models import BaseDBModel, PyObjectId

class EntertainmentItemBase(BaseModel):
    name: str
    url: HttpUrl # Pydantic会自动校验是否是合法的HTTP/HTTPS URL
    type: str = Field(default="audio_url", description="内容类型，如 audio_url, radio_stream")

class EntertainmentItemCreate(EntertainmentItemBase):
    deviceId: PyObjectId

class EntertainmentItemUpdate(BaseModel): # 用于更新
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    type: Optional[str] = None

class EntertainmentItemInDB(BaseDBModel, EntertainmentItemCreate):
    pass

class EntertainmentItemPublic(BaseDBModel, EntertainmentItemBase):
    id: PyObjectId
    deviceId: PyObjectId
    pass
