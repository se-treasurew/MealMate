from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, DishCategory, Dish
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
)

router = APIRouter()


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
):
    """获取所有分类（按 sort_order 排序）"""
    result = await db.execute(
        select(DishCategory).order_by(DishCategory.sort_order, DishCategory.id)
    )
    return result.scalars().all()


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建分类（仅饲养员/店长）"""
    if not (current_user.is_feeder or current_user.is_admin):
        raise HTTPException(status_code=403, detail="无权限")

    # 检查名称是否重复
    existing = await db.execute(
        select(DishCategory).where(DishCategory.name == payload.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="分类名称已存在")

    category = DishCategory(name=payload.name, sort_order=payload.sort_order)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新分类（仅饲养员/店长）"""
    if not (current_user.is_feeder or current_user.is_admin):
        raise HTTPException(status_code=403, detail="无权限")

    result = await db.execute(
        select(DishCategory).where(DishCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    if payload.name is not None:
        category.name = payload.name
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order

    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除分类（仅饲养员/店长）"""
    if not (current_user.is_feeder or current_user.is_admin):
        raise HTTPException(status_code=403, detail="无权限")

    result = await db.execute(
        select(DishCategory).where(DishCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    # 分类下仍有菜品时禁止删除，避免菜品 category_id 悬空
    dish_count = await db.scalar(
        select(func.count()).select_from(Dish).where(Dish.category_id == category_id)
    )
    if dish_count:
        raise HTTPException(
            status_code=400,
            detail=f"该分类下还有 {dish_count} 道菜品，请先移动或删除",
        )

    await db.delete(category)
    await db.commit()
