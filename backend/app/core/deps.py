from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

# auto_error=False：无 Authorization 头时不自动 401，交给业务逻辑处理（游客场景）
security = HTTPBearer(auto_error=False)
PASSWORD_CHANGE_ALLOWED_PATHS = {"/api/auth/me", "/api/auth/password"}


def token_matches_user(payload: dict, user: User) -> bool:
    """校验 JWT 是否属于用户当前有效的令牌版本。"""
    try:
        return (
            int(payload.get("sub")) == user.id
            and int(payload.get("ver")) == user.token_version
        )
    except (TypeError, ValueError):
        return False


def enforce_password_change(user: User, request_path: str) -> None:
    """强制改密期间仅允许读取本人信息和提交新密码。"""
    if (
        user.must_change_password
        and request_path not in PASSWORD_CHANGE_ALLOWED_PATHS
    ):
        raise HTTPException(status_code=403, detail="请先修改初始密码")


async def _get_user_by_credentials(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> User | None:
    """解析 Bearer token 并查询用户；无 token / 无效 / 禁用时返回 None"""
    if credentials is None:
        return None
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not token_matches_user(payload, user):
        return None
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前登录用户（强制鉴权，禁用账号的旧 token 立即失效）"""
    user = await _get_user_by_credentials(credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
        )
    enforce_password_change(user, request.url.path)
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选鉴权：游客/未登录返回 None，登录但无效 token 也视为 None"""
    user = await _get_user_by_credentials(credentials, db)
    # 首次改密期间不授予公开接口中的饲养员/店长扩展视图。
    if user and user.must_change_password:
        return None
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """仅店长可访问（用于新代码）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    return current_user


def require_feeder(current_user: User = Depends(get_current_user)) -> User:
    """饲养员/店长可访问（用于新代码）"""
    if not (current_user.is_feeder or current_user.is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    return current_user
