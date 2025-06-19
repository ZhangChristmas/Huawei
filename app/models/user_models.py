# app/models/user_models.py
from typing import Optional
from pydantic import BaseModel, Field
from app.models.common_models import BaseDBModel, PyObjectId

# --- 用户模型 (子女账户) ---
class UserBase(BaseModel):
    wxOpenid: str = Field(description="微信用户的唯一标识") # unique在数据库层面实现
    wxUnionid: Optional[str] = Field(None, description="用户在微信开放平台的唯一标识符") # unique, sparse在数据库层面实现
    nickName: Optional[str] = None
    avatarUrl: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserInDB(BaseDBModel, UserBase):
    hashedPassword: Optional[str] = None # 如果支持用户名密码登录，这里存哈希密码 (当前小程序场景可能不需要)
    pass

class UserPublic(BaseDBModel, UserBase):
    id: PyObjectId # 确保id也输出
    # token: Optional[str] = None # Token通常不在用户模型中返回，而是登录接口直接返回
    pass

# 用于Token Payload
class TokenPayload(BaseModel):
    sub: Optional[PyObjectId] = None # subject, 通常是用户ID
    # openid: Optional[str] = None # 也可以直接用openid作为sub
    type: Optional[str] = Field(default="access") # "access" or "refresh"
