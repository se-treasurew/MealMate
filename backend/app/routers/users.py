from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import get_password_hash, try_disable_user, try_replace_password
from app.models import User
from app.schemas.user import (
    UserCreate,
    UserFeederUpdate,
    UserStatusUpdate,
    PasswordReset,
    UserListItem,
)
from app.schemas.auth import UserResponse

router = APIRouter()

# 不允许创建/提升/禁用管理员，保证管理员唯一
ADMIN_ACTION_FORBIDDEN = "不可对管理员账号执行此操作"


def validate_password_reset_target(user: User, current_admin: User) -> None:
    """管理员重置接口不得绕过管理员自身的旧密码校验。"""
    if user.is_admin or user.id == current_admin.id:
        raise HTTPException(status_code=400, detail=ADMIN_ACTION_FORBIDDEN)


@router.get("", response_model=list[UserListItem])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """获取所有用户列表（不访问关系属性，避免 MissingGreenlet）"""
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.post("", response_model=UserListItem, status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """管理员创建账号（初始密码 + 首次登录强制改密）"""
    existing = await db.execute(
        select(User).where(User.username == payload.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        nickname=payload.nickname.strip() if payload.nickname else None,
        is_feeder=payload.is_feeder,
        is_active=True,
        must_change_password=True,  # 首次登录强制改密
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/{user_id}/feeder", response_model=UserListItem)
async def toggle_feeder(
    user_id: int,
    payload: UserFeederUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """授予/收回饲养员权限"""
    user = await _get_user_or_404(db, user_id)
    if user.is_admin:
        raise HTTPException(status_code=400, detail=ADMIN_ACTION_FORBIDDEN)
    user.is_feeder = payload.is_feeder
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/{user_id}/status", response_model=UserListItem)
async def toggle_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """启用/禁用账号（不能操作自己，不能操作 admin）"""
    user = await _get_user_or_404(db, user_id)
    if user.is_admin or user.id == current_admin.id:
        raise HTTPException(status_code=400, detail=ADMIN_ACTION_FORBIDDEN)
    if user.is_active and not payload.is_active:
        changed = await try_disable_user(
            db,
            user_id=user.id,
            expected_token_version=user.token_version,
        )
        if not changed:
            await db.rollback()
            raise HTTPException(status_code=409, detail="账号状态已变化，请刷新后重试")
    else:
        user.is_active = payload.is_active
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/{user_id}/password", response_model=UserResponse)
async def reset_password(
    user_id: int,
    payload: PasswordReset,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """管理员重置密码（同时启用账号、重置后强制改密）"""
    user = await _get_user_or_404(db, user_id)
    validate_password_reset_target(user, current_admin)
    changed = await try_replace_password(
        db,
        user_id=user.id,
        expected_token_version=user.token_version,
        password_hash=get_password_hash(payload.password),
        must_change_password=True,
        is_active=True,
    )
    if not changed:
        await db.rollback()
        raise HTTPException(status_code=409, detail="账号状态已变化，请刷新后重试")
    await db.commit()
    await db.refresh(user)
    return user


async def _get_user_or_404(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user
