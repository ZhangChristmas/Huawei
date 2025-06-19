# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer # 用于从请求头获取token
from typing import Optional

from app.core.config import settings
from app.core import security # 导入我们自己的security模块
from app.models.user_models import UserInDB, TokenPayload, UserPublic
from app.services import user_service # 稍后会创建 user_service

# OAuth2PasswordBearer 会从请求的 "Authorization: Bearer <token>" 头中提取token
# tokenUrl 应该指向我们获取token的API端点 (例如 /api/v1/auth/login/wx)
# 注意: FastAPI的OAuth2PasswordBearer主要设计用于用户名密码流程，
# 对于微信登录后我们自定义的token，它也能工作，但tokenUrl的语义略有不同。
# 如果完全不使用它的表单功能，tokenUrl可以是一个象征性的路径。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token") # 假设我们有一个标准的token获取端点

async def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> Optional[TokenPayload]:
    """
    解码并验证token，返回TokenPayload。
    如果token无效或过期，则抛出HTTPException。
    """
    payload = security.decode_token(token)
    if not payload or not payload.sub: # 确保payload和subject存在
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

async def get_current_user(payload: TokenPayload = Depends(get_current_user_payload)) -> Optional[UserInDB]:
    """
    根据TokenPayload中的subject (用户ID) 从数据库获取用户信息。
    如果用户不存在，则抛出HTTPException。
    """
    if not payload.sub: # 再次检查，理论上 get_current_user_payload 已经检查过了
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token subject")

    user = await user_service.get_user_by_id(user_id=payload.sub) # 使用 PyObjectId 作为 ID
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    """
    获取当前活动用户。可以添加用户是否被禁用的检查。
    (当前我们没有用户禁用状态，所以直接返回)
    """
    # if current_user.disabled: # 假设 UserInDB 有 disabled 字段
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# 转换为UserPublic模型，方便API返回 (不包含敏感信息)
async def get_current_user_public(current_user_db: UserInDB = Depends(get_current_active_user)) -> UserPublic:
    return UserPublic.model_validate(current_user_db) # Pydantic v2
    # Pydantic v1: return UserPublic.from_orm(current_user_db)


# 可选的：获取当前用户ID的依赖，如果某些接口只需要用户ID
async def get_current_user_id(payload: TokenPayload = Depends(get_current_user_payload)) -> str:
    if not payload.sub:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token subject for ID")
    return str(payload.sub) # PyObjectId to str
