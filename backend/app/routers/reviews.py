from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import DishReview, User
from app.schemas.review import ReviewResponse

router = APIRouter()


@router.get("/dishes/{dish_id}/reviews", response_model=list[ReviewResponse])
async def list_dish_reviews(
    dish_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取菜品的公开评价列表（游客可读）"""
    stmt = (
        select(DishReview)
        .options(selectinload(DishReview.user))
        .where(DishReview.dish_id == dish_id)
        .order_by(DishReview.created_at.desc())
    )
    reviews = (await db.execute(stmt)).scalars().all()
    return [
        ReviewResponse(
            id=r.id,
            dish_id=r.dish_id,
            order_id=r.order_id,
            user_id=r.user_id,
            user_nickname=r.user.nickname if r.user else None,
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in reviews
    ]


@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除不当评价：仅饲养员/店长"""
    if not (current_user.is_feeder or current_user.is_admin):
        raise HTTPException(status_code=403, detail="无权限删除评价")

    result = await db.execute(select(DishReview).where(DishReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="评价不存在")

    await db.delete(review)
    await db.commit()
