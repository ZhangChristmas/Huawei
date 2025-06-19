# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union # Union 추가
from passlib.context import CryptContext
from jose import jwt, JWTError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from app.core.config import settings
from app.models.user_models import TokenPayload # TokenPayload用于解码和类型提示

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- 密码处理 (如果将来支持用户名密码登录) ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --- JWT 令牌处理 ---

def get_public_key_from_private(private_key_pem: str) -> Optional[str]:
    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        if isinstance(private_key, rsa.RSAPrivateKey):
            public_key = private_key.public_key()
            pem_public_key = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            return pem_public_key.decode()
        return None
    except Exception as e:
        print(f"Error deriving public key from private key: {e}")
        return None

JWT_PRIVATE_KEY = settings.RSA_PRIVATE_KEY
JWT_PUBLIC_KEY = settings.RSA_PUBLIC_KEY

if settings.ALGORITHM.startswith("RS") and JWT_PRIVATE_KEY and not JWT_PUBLIC_KEY:
    print("Attempting to derive public key from private key for JWT verification...")
    JWT_PUBLIC_KEY = get_public_key_from_private(JWT_PRIVATE_KEY)
    if not JWT_PUBLIC_KEY:
        # 生产环境中，如果公钥无法派生，应该是一个严重错误
        # raise ValueError("Failed to derive public key. Ensure RSA_PUBLIC_KEY_PATH is set or the private key is valid.")
        print("CRITICAL: Failed to derive public key. JWT verification will fail if public key is not explicitly provided.")


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"} # "sub" 通常是用户ID (PyObjectId会转为str)

    if settings.ALGORITHM.startswith("RS"):
        if not JWT_PRIVATE_KEY:
            raise ValueError("RSA_PRIVATE_KEY is not configured for creating access token with RS algorithm.")
        encoded_jwt = jwt.encode(to_encode, JWT_PRIVATE_KEY, algorithm=settings.ALGORITHM)
    else: # 假设不支持其他算法，或者可以添加对HS256的显式支持
        raise ValueError(f"Unsupported JWT algorithm for creation: {settings.ALGORITHM}")
        
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}

    if settings.ALGORITHM.startswith("RS"):
        if not JWT_PRIVATE_KEY:
            raise ValueError("RSA_PRIVATE_KEY is not configured for creating refresh token with RS algorithm.")
        encoded_jwt = jwt.encode(to_encode, JWT_PRIVATE_KEY, algorithm=settings.ALGORITHM)
    else:
        raise ValueError(f"Unsupported JWT algorithm for creation: {settings.ALGORITHM}")
    return encoded_jwt

def decode_token(token: str) -> Optional[TokenPayload]:
    try:
        if settings.ALGORITHM.startswith("RS"):
            if not JWT_PUBLIC_KEY: 
                raise ValueError("RSA_PUBLIC_KEY is not configured for decoding token with RS algorithm.")
            payload_dict = jwt.decode(token, JWT_PUBLIC_KEY, algorithms=[settings.ALGORITHM])
        else:
            raise ValueError(f"Unsupported JWT algorithm for decoding: {settings.ALGORITHM}")
        
        # 确保sub存在且是PyObjectId兼容的
        if "sub" not in payload_dict:
             raise JWTError("Token missing 'sub' claim.")
        # payload_dict["sub"] = PyObjectId(payload_dict["sub"]) # PyObjectId.validate会处理str
        return TokenPayload(**payload_dict) # 将解码后的字典转换为TokenPayload模型
    
    except JWTError as e:
        print(f"JWT Error: {e}") 
        return None
    except ValueError as e: 
        print(f"Token Configuration or Validation Error: {e}")
        return None
    except Exception as e: # 捕获其他可能的错误
        print(f"An unexpected error occurred during token decoding: {e}")
        return None
