from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str):
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.PyJWTError:
        return None


async def try_replace_password(
    db: AsyncSession,
    *,
    user_id: int,
    expected_token_version: int,
    password_hash: str,
    must_change_password: bool,
    is_active: bool | None = None,
) -> bool:
    """原子替换密码并提升令牌版本；旧版本不匹配时拒绝覆盖。"""
    values = {
        "password_hash": password_hash,
        "must_change_password": must_change_password,
        "token_version": User.token_version + 1,
    }
    if is_active is not None:
        values["is_active"] = is_active
    result = await db.execute(
        update(User)
        .where(
            User.id == user_id,
            User.token_version == expected_token_version,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


async def try_disable_user(
    db: AsyncSession,
    *,
    user_id: int,
    expected_token_version: int,
) -> bool:
    """原子禁用账号并提升令牌版本。"""
    result = await db.execute(
        update(User)
        .where(
            User.id == user_id,
            User.is_active.is_(True),
            User.token_version == expected_token_version,
        )
        .values(is_active=False, token_version=User.token_version + 1)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1
