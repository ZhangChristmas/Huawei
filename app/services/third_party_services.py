# app/services/third_party_services.py
import httpx # 推荐使用 httpx 进行异步HTTP请求
from typing import Optional, Dict, Any
from app.core.config import settings
from datetime import datetime

WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
WECHAT_GET_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WECHAT_SEND_SUBSCRIBE_MESSAGE_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"
# WECHAT_GET_UNLIMITED_WXACODE_URL = "https://api.weixin.qq.com/wxa/getwxacodeunlimit" # 生成小程序码

# --- 微信API服务 ---
async def wx_code_to_session(code: str) -> Optional[Dict[str, Any]]:
    """
    用code换取微信用户的openid和session_key
    """
    if not settings.WX_APPID or not settings.WX_SECRET:
        print("Error: WX_APPID or WX_SECRET not configured.")
        return None

    params = {
        "appid": settings.WX_APPID,
        "secret": settings.WX_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(WECHAT_CODE2SESSION_URL, params=params)
            response.raise_for_status() # 如果HTTP状态码是4xx或5xx，则抛出异常
            data = response.json()
            if data.get("errcode") and data.get("errcode") != 0:
                print(f"WeChat API Error (code2Session): {data.get('errmsg')}, Code: {data.get('errcode')}")
                return None
            return data # 应该包含 openid, session_key, unionid (如果绑定了开放平台)
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred while calling WeChat code2Session: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"Request error occurred while calling WeChat code2Session: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in wx_code_to_session: {e}")
        return None


# TODO: 实现获取和缓存微信全局 access_token 的逻辑
# 这个 access_token 用于调用发送订阅消息等服务端接口
# 它有有效期，需要定时刷新并缓存 (例如使用Redis)
_wechat_access_token: Optional[str] = None
_wechat_access_token_expires_at: Optional[datetime] = None

async def get_wechat_access_token() -> Optional[str]:
    """
    获取有效的微信全局接口调用凭证 (access_token)。
    需要实现缓存和过期刷新逻辑。
    """
    global _wechat_access_token, _wechat_access_token_expires_at
    from datetime import datetime, timedelta, timezone # 局部导入

    if _wechat_access_token and _wechat_access_token_expires_at and datetime.now(timezone.utc) < _wechat_access_token_expires_at:
        return _wechat_access_token

    if not settings.WX_APPID or not settings.WX_SECRET:
        print("Error: WX_APPID or WX_SECRET not configured for getting access_token.")
        return None

    params = {
        "grant_type": "client_credential",
        "appid": settings.WX_APPID,
        "secret": settings.WX_SECRET,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(WECHAT_GET_ACCESS_TOKEN_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("access_token") and data.get("expires_in"):
                _wechat_access_token = data["access_token"]
                # 提前一点点过期，避免临界问题
                _wechat_access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"] - 300)
                print(f"Successfully fetched new WeChat access_token, expires at {_wechat_access_token_expires_at}")
                # 在生产环境中，应该将token和过期时间存入Redis等缓存
                return _wechat_access_token
            else:
                print(f"WeChat API Error (get_access_token): {data.get('errmsg')}, Code: {data.get('errcode')}")
                _wechat_access_token = None
                _wechat_access_token_expires_at = None
                return None
    except Exception as e:
        print(f"Error fetching WeChat access_token: {e}")
        _wechat_access_token = None
        _wechat_access_token_expires_at = None
        return None

async def send_wechat_subscribe_message(
    touser_openid: str,
    template_id: str,
    page: Optional[str] = None, # 点击模板卡片后的跳转页面，不填则无法跳转
    data: Dict[str, Dict[str, Any]] = None, # 模板内容，格式如 {"thing1": {"value": "xxx"}, "time2": {"value": "yyy"}}
    miniprogram_state: str = "developer" # 跳转小程序类型：developer为开发版；trial为体验版；formal为正式版
) -> bool:
    """
    发送微信订阅消息
    """
    access_token = await get_wechat_access_token()
    if not access_token:
        print("Failed to send subscribe message: could not get access_token.")
        return False

    payload = {
        "touser": touser_openid,
        "template_id": template_id,
        "data": data or {},
    }
    if page:
        payload["page"] = page
    if miniprogram_state: # formal, trial, developer
        payload["miniprogram_state"] = miniprogram_state
        # payload["lang"] = "zh_CN" # 默认中文

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{WECHAT_SEND_SUBSCRIBE_MESSAGE_URL}?access_token={access_token}",
                json=payload
            )
            response.raise_for_status()
            result_data = response.json()
            if result_data.get("errcode") == 0:
                print(f"Successfully sent subscribe message to {touser_openid} with template {template_id}")
                return True
            else:
                print(f"WeChat API Error (send_subscribe_message): {result_data.get('errmsg')}, Code: {result_data.get('errcode')}")
                # 特殊错误码处理，例如 43101: user refuse to accept the msg
                if result_data.get("errcode") == 43101:
                    print(f"User {touser_openid} refused to accept message for template {template_id}")
                return False
    except Exception as e:
        print(f"Error sending WeChat subscribe message: {e}")
        return False

# 其他第三方服务可以类似地添加...
