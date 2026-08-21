from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_optional
from app.models import User, Tag, DishTag
from app.schemas.tag import TagCreate, TagResponse

router = APIRouter()


@router.get("", response_model=list[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    _current_user: User | None = Depends(get_current_user_optional),
):
    """获取所有标签（游客可访问，用于展示）"""
    result = await db.execute(select(Tag).order_by(Tag.id))
    return result.scalars().all()


@router.post("", response_model=TagResponse, status_code=201)
async def create_tag(
    payload: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建标签（仅饲养员/店长）"""
    if not (current_user.is_feeder or current_user.is_admin):
        raise HTTPException(status_code=403, detail="无权限")

    existing = await db.execute(select(Tag).where(Tag.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="标签名称已存在")

    tag = Tag(name=payload.name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除标签（仅饲养员/店长）"""
    if not (current_user.is_feeder or current_user.is_admin):
        raise HTTPException(status_code=403, detail="无权限")

    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    # 先清理菜品关联，避免遗留孤儿关联行
    await db.execute(delete(DishTag).where(DishTag.tag_id == tag_id))

    await db.delete(tag)
    await db.commit()
