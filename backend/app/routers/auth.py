from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    try_replace_password,
)
from app.core.deps import get_current_user, token_matches_user
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
    UpdateProfileRequest,
    ChangePasswordRequest,
)
from app.utils.image import remove_image_files, save_image

router = APIRouter()

PRESET_AVATARS = {
    f"/avatars/{name}.png"
    for name in (
        "bear", "cat", "chick", "dog", "fox", "frog",
        "lion", "owl", "panda", "pig", "rabbit", "tiger",
    )
}


def _is_existing_upload_path(value: str) -> bool:
    """判断数据库中的头像值是否为后端生成的相对上传路径。"""
    parts = value.split("/")
    return (
        len(parts) == 3
        and len(parts[0]) == 4
        and parts[0].isdigit()
        and len(parts[1]) == 2
        and parts[1].isdigit()
        and ".." not in parts
        and not value.startswith("/")
        and parts[2].lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    )


def validate_avatar_url(value: str | None, current_avatar: str | None) -> str | None:
    """只允许清空头像、使用内置头像或保留本人当前上传的头像。"""
    normalized = value.strip() if value else None
    if normalized is None:
        return None
    if normalized in PRESET_AVATARS:
        return normalized
    if normalized == current_avatar and _is_existing_upload_path(normalized):
        return normalized
    raise HTTPException(status_code=400, detail="头像路径无效")


def _avatar_upload_files(value: str | None) -> list[str]:
    """返回自定义头像使用的缩略图及对应原图路径。"""
    if not value or not _is_existing_upload_path(value):
        return []
    paths = [value]
    if value.endswith("_thumb.webp"):
        paths.append(f"{value.removesuffix('_thumb.webp')}.webp")
    return paths


def _create_token_response(user: User) -> TokenResponse:
    claims = {"sub": str(user.id), "ver": user.token_version}
    return TokenResponse(
        access_token=create_access_token(claims),
        refresh_token=create_refresh_token(claims),
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    # 查询用户
    result = await db.execute(
        select(User).where(User.username == credentials.username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 禁用账号直接拒绝（不泄露密码校验结果）
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    # 验证密码
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 生成 token
    return _create_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """刷新 access token"""
    token_payload = decode_token(payload.refresh_token)
    if not token_payload or token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )

    user_id = token_payload.get("sub")
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    result = await db.execute(select(User).where(User.id == user_id_int))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    if not token_matches_user(token_payload, user):
        raise HTTPException(status_code=401, detail="刷新令牌已失效")

    return _create_token_response(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新个人资料（昵称/头像）"""
    previous_avatar = current_user.avatar_url
    if payload.nickname is not None:
        current_user.nickname = payload.nickname.strip() or None
    if "avatar_url" in payload.model_fields_set:
        current_user.avatar_url = validate_avatar_url(
            payload.avatar_url,
            current_user.avatar_url,
        )
    await db.commit()
    if previous_avatar != current_user.avatar_url:
        remove_image_files(_avatar_upload_files(previous_avatar))
    await db.refresh(current_user)
    return current_user


@router.put("/password", response_model=TokenResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改密码（校验旧密码；成功后清除强制改密标志）"""
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码不正确",
        )
    changed = await try_replace_password(
        db,
        user_id=current_user.id,
        expected_token_version=current_user.token_version,
        password_hash=get_password_hash(payload.new_password),
        must_change_password=False,
    )
    if not changed:
        await db.rollback()
        raise HTTPException(status_code=409, detail="账号状态已变化，请重新登录")
    await db.commit()
    await db.refresh(current_user)
    return _create_token_response(current_user)


@router.post("/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传自定义头像（复用菜品图片上传，自动生成 200x200 缩略图）"""
    previous_avatar = current_user.avatar_url
    image_path, thumb_path = await save_image(file)
    current_user.avatar_url = thumb_path
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        current_user.avatar_url = previous_avatar
        remove_image_files([image_path, thumb_path])
        raise
    remove_image_files([image_path, *_avatar_upload_files(previous_avatar)])
    await db.refresh(current_user)
    return current_user
