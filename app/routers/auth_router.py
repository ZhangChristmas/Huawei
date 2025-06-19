# app/routers/auth_router.py

from fastapi import APIRouter, HTTPException, status, Depends, Body
from datetime import timedelta
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core import security
from app.services import user_service, third_party_services
from app.models.user_models import UserCreate, UserPublic, UserInDB, TokenPayload
from app.models.common_models import PyObjectId
from app.dependencies import get_current_active_user, get_current_user_payload
from app.db.mongodb_utils import get_user_collection # 导入用于直接查询验证

router = APIRouter()

# --- Pydantic Models for this router ---

class WxLoginRequest(BaseModel):
    code: str
    nickName: Optional[str] = None
    avatarUrl: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_info: UserPublic

class RefreshTokenRequest(BaseModel):
    refresh_token: str


# --- API Endpoints ---

@router.post("/login/wx", response_model=TokenResponse, summary="微信小程序登录或注册")
async def login_via_wechat(login_data: WxLoginRequest):
    """
    处理微信小程序登录请求:
    1. 使用前端传来的 `code` 调用微信 `code2Session` API 获取 `openid`。
    2. 根据 `openid` 在数据库中查找用户，如果不存在则创建。
    3. 生成 `access_token` 和 `refresh_token` 返回给小程序。
    """
    print("\n--- [AUTH] Received POST /login/wx request ---")
    print(f"[AUTH] Request body (login_data): {login_data.model_dump_json()}")

    if not login_data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code (code) is required."
        )

    print("[AUTH] Calling WeChat code2Session API...")
    wx_session_data = await third_party_services.wx_code_to_session(login_data.code)
    
    if not wx_session_data or "openid" not in wx_session_data:
        print("!!! [AUTH] WeChat code2Session FAILED or returned no openid.")
        print(f"[AUTH] WeChat API response: {wx_session_data}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with WeChat. Invalid code or WeChat API error."
        )
    
    openid = wx_session_data["openid"]
    unionid = wx_session_data.get("unionid")
    print(f"[AUTH] WeChat code2Session SUCCESS. OpenID: {openid}, UnionID: {unionid}")

    print(f"[AUTH] Checking for existing user with openid: {openid}")
    user = await user_service.get_user_by_openid(openid)
    print(f"[AUTH] User found in DB: {'Yes' if user else 'No'}")

    if not user:
        print("[AUTH] User not found, attempting to create new user...")
        user_create_data = UserCreate(
            wxOpenid=openid,
            wxUnionid=unionid,
            nickName=login_data.nickName,
            avatarUrl=login_data.avatarUrl
        )
        try:
            user = await user_service.create_user(user_create_data)
            if user:
                 print(f"[AUTH] New user created successfully. User DB ID: {user.id}")
            else: # create_user 在用户已存在时可能返回None或已存在的用户，需要根据实现调整
                 print("!!! [AUTH] user_service.create_user returned None, possibly due to race condition or logic error.")
                 # 重新查询一次以应对并发创建的情况
                 user = await user_service.get_user_by_openid(openid)
                 if not user:
                     raise Exception("Failed to retrieve user even after creation attempt.")

        except Exception as e:
            print(f"!!! [AUTH] Error during user creation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create user: {e}"
            )
    else:
        print(f"[AUTH] User found. User DB ID: {user.id}. Proceeding to generate tokens.")
        if login_data.nickName or login_data.avatarUrl:
            print("[AUTH] Updating user info for existing user...")
            updated_user = await user_service.update_user_info(
                user_id=user.id,
                nick_name=login_data.nickName,
                avatar_url=login_data.avatarUrl
            )
            if updated_user:
                user = updated_user
                print("[AUTH] User info updated.")

    if not user:
        raise HTTPException(status_code=500, detail="User object is unexpectedly None before generating tokens.")


    # --- [DB VERIFICATION STEP] ---
    print("\n--- [DB VERIFICATION STEP] ---")
    print(f"Verifying user with ID: {user.id} in the database...")
    user_collection = get_user_collection()
    verify_doc = await user_collection.find_one({"_id": str(user.id)})
    if verify_doc:
        print("SUCCESS: Found the user document in the database immediately after operation.")
        print(f"DB Document: {verify_doc}")
    else:
        print("!!! CRITICAL FAILURE: Could NOT find the user document in the database right after it was supposedly created/found.")
    print("--- [END DB VERIFICATION STEP] ---\n")
    # --- END [DB VERIFICATION STEP] ---


    print(f"[AUTH] Generating tokens for user ID: {user.id}")
    access_token = security.create_access_token(subject=user.id)
    refresh_token = security.create_refresh_token(subject=user.id)
    print("[AUTH] Tokens generated.")
    
    user_public_info = UserPublic.model_validate(user)

    print("[AUTH] Sending TokenResponse back to client.")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_info=user_public_info
    )

@router.post("/token/refresh", response_model=TokenResponse, summary="刷新访问令牌")
async def refresh_access_token(refresh_request: RefreshTokenRequest):
    payload = security.decode_token(refresh_request.refresh_token)
    if not payload or payload.type != "refresh" or not payload.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id_obj = PyObjectId(payload.sub)
    user = await user_service.get_user_by_id(user_id=user_id_obj)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for this refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_access_token = security.create_access_token(subject=user.id)
    new_refresh_token = security.create_refresh_token(subject=user.id)
    user_public_info = UserPublic.model_validate(user)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user_info=user_public_info
    )


@router.post("/token/check", response_model=UserPublic, summary="验证当前Token并返回用户信息")
async def check_current_token(current_user_db: UserInDB = Depends(get_current_active_user)):
    """
    验证 access_token 有效性并返回最新用户信息。
    """
    return UserPublic.model_validate(current_user_db)
