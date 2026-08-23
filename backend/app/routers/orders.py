from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import (
    User, Order, OrderItem, Dish, DishReview,
)
from app.schemas.order import (
    OrderCreate, OrderUpdate, OrderResponse, OrderItemResponse,
)
from app.schemas.review import (
    ReviewCreate, ReviewResponse, ReviewSubmitResponse, ReviewItemStatus,
)
from app.routers.push import notify_feeders, notify_user

router = APIRouter()

# 允许的状态流转
VALID_STATUSES = {"pending", "accepted", "cooking", "done", "cancelled"}
STAFF_TRANSITIONS = {
    "pending": "accepted",
    "accepted": "cooking",
    "cooking": "done",
}
MEAL_TYPES = {"早餐", "午餐", "晚餐", "夜宵", "自定义"}


def validate_status_transition(
    current_status: str,
    target_status: str,
    *,
    is_staff: bool,
    is_owner: bool,
) -> None:
    """校验订单状态变化，禁止跳级、回退和重开终态订单。"""
    if target_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="状态值无效")

    if target_status == "cancelled":
        if not is_owner:
            raise HTTPException(status_code=403, detail="只能取消自己的订单")
        if current_status != "pending":
            raise HTTPException(status_code=400, detail="仅待处理订单可取消")
        return

    if not is_staff:
        raise HTTPException(status_code=403, detail="无权修改订单状态")
    if STAFF_TRANSITIONS.get(current_status) != target_status:
        raise HTTPException(status_code=400, detail="订单状态流转无效")


async def try_transition_order(
    db: AsyncSession,
    *,
    order_id: int,
    expected_status: str,
    target_status: str,
) -> bool:
    """用条件更新保证同一旧状态只能成功流转一次。"""
    result = await db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == expected_status)
        .values(status=target_status)
    )
    return result.rowcount == 1


async def build_order_response(db: AsyncSession, order: Order) -> OrderResponse:
    """构造订单响应，补充菜品名称"""
    dish_ids = {item.dish_id for item in order.items}

    # 批量查询菜品名称
    dish_names = {}
    if dish_ids:
        result = await db.execute(select(Dish).where(Dish.id.in_(dish_ids)))
        for d in result.scalars().all():
            dish_names[d.id] = d.name

    items = []
    for item in order.items:
        items.append(OrderItemResponse(
            id=item.id,
            dish_id=item.dish_id,
            dish_name=dish_names.get(item.dish_id, f"菜品#{item.dish_id}"),
            quantity=item.quantity,
            item_note=item.item_note,
        ))

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        user_nickname=order.user.nickname if order.user else None,
        meal_date=order.meal_date,
        meal_type=order.meal_type,
        status=order.status,
        note=order.note,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=items,
    )


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status_filter: str | None = None,
    mine_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取订单列表"""
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
    )

    # 饭团只能看自己的订单；饲养员/店长默认看全部
    if not (current_user.is_feeder or current_user.is_admin) or mine_only:
        stmt = stmt.where(Order.user_id == current_user.id)

    if status_filter and status_filter in VALID_STATUSES:
        stmt = stmt.where(Order.status == status_filter)

    stmt = stmt.order_by(Order.created_at.desc())
    result = await db.execute(stmt)
    orders = result.scalars().unique().all()

    return [await build_order_response(db, o) for o in orders]


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交订单"""
    if not payload.items:
        raise HTTPException(status_code=400, detail="订单至少包含一个菜品")

    if payload.meal_type not in MEAL_TYPES:
        raise HTTPException(status_code=400, detail="餐次类型无效")

    # 校验菜品是否存在且上架
    dish_ids = {item.dish_id for item in payload.items}
    result = await db.execute(select(Dish).where(Dish.id.in_(dish_ids)))
    dishes = {d.id: d for d in result.scalars().all()}
    if len(dishes) != len(dish_ids):
        raise HTTPException(status_code=400, detail="部分菜品不存在")
    for d in dishes.values():
        if d.status != "active":
            raise HTTPException(status_code=400, detail=f"菜品「{d.name}」已下架，无法下单")

    order = Order(
        user_id=current_user.id,
        meal_date=payload.meal_date,
        meal_type=payload.meal_type,
        note=payload.note,
        status="pending",
    )
    db.add(order)
    await db.flush()

    for item in payload.items:
        order_item = OrderItem(
            order_id=order.id,
            dish_id=item.dish_id,
            quantity=item.quantity,
            item_note=item.item_note,
        )
        db.add(order_item)

    await db.commit()

    # 重新加载
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .where(Order.id == order.id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one()
    resp = await build_order_response(db, order)

    # 通知所有饲养员：有新订单
    item_count = sum(i.quantity for i in order.items)
    try:
        await notify_feeders(
            db,
            f"🍚 新订单！{order.user.nickname or order.user.username} 下单了 "
            f"{item_count} 份，期望{payload.meal_date} {payload.meal_type}",
        )
    except Exception:
        pass  # 兼容通知钩子不得影响下单

    return resp


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取订单详情"""
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .where(Order.id == order_id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    # 饭团只能看自己的
    if order.user_id != current_user.id and not (
        current_user.is_feeder or current_user.is_admin
    ):
        raise HTTPException(status_code=403, detail="无权查看此订单")

    return await build_order_response(db, order)


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    payload: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新订单（状态流转/取消）"""
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .where(Order.id == order_id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    is_staff = current_user.is_feeder or current_user.is_admin

    if payload.status is not None:
        previous_status = order.status
        validate_status_transition(
            previous_status,
            payload.status,
            is_staff=is_staff,
            is_owner=order.user_id == current_user.id,
        )
        if not await try_transition_order(
            db,
            order_id=order.id,
            expected_status=previous_status,
            target_status=payload.status,
        ):
            await db.rollback()
            raise HTTPException(status_code=400, detail="订单状态已变化，请刷新后重试")

    if payload.note is not None and is_staff:
        order.note = payload.note

    await db.commit()
    await db.refresh(order)

    # 重新加载
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .where(Order.id == order.id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one()
    resp = await build_order_response(db, order)

    # 状态变更通知饭团
    if payload.status is not None and payload.status != "cancelled":
        status_text = {
            "accepted": "已接单",
            "cooking": "制作中",
            "done": "已完成",
        }.get(payload.status, payload.status)
        try:
            await notify_user(db, order.user_id, f"👨‍🍳 你的订单#{order.id} {status_text}")
        except Exception:
            pass

    return resp


@router.delete("/{order_id}", status_code=204)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """饭团取消自己的待处理订单（便捷接口）"""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能取消自己的订单")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="仅待处理订单可取消")

    if not await try_transition_order(
        db,
        order_id=order.id,
        expected_status="pending",
        target_status="cancelled",
    ):
        await db.rollback()
        raise HTTPException(status_code=400, detail="订单状态已变化，请刷新后重试")
    await db.commit()


@router.post("/{order_id}/reviews", response_model=ReviewSubmitResponse)
async def submit_order_reviews(
    order_id: int,
    payload: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """订单完成后，下单人对订单内菜品逐个评价（重复提交视为修改）"""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能评价自己的订单")
    if order.status != "done":
        raise HTTPException(status_code=400, detail="仅已完成订单可评价")

    # 校验：去重、菜品必须属于该订单
    seen: set[int] = set()
    order_dish_ids = {item.dish_id for item in order.items}
    for item in payload.items:
        if item.dish_id in seen:
            raise HTTPException(status_code=400, detail=f"菜品#{item.dish_id} 重复评价")
        if item.dish_id not in order_dish_ids:
            raise HTTPException(status_code=400, detail="评价的菜品不在该订单中")
        seen.add(item.dish_id)

    results: list[ReviewItemStatus] = []
    existing = {
        r.dish_id: r
        for r in (
            await db.execute(
                select(DishReview).where(
                    DishReview.order_id == order_id,
                    DishReview.user_id == current_user.id,
                )
            )
        ).scalars().all()
    }

    for item in payload.items:
        review = existing.get(item.dish_id)
        if review:
            review.rating = item.rating
            review.comment = item.comment
            updated = True
        else:
            review = DishReview(
                dish_id=item.dish_id,
                order_id=order_id,
                user_id=current_user.id,
                rating=item.rating,
                comment=item.comment,
            )
            db.add(review)
            await db.flush()
            updated = False
        results.append(ReviewItemStatus(
            dish_id=item.dish_id,
            review_id=review.id,
            rating=review.rating,
            comment=review.comment,
            updated=updated,
        ))

    await db.commit()
    return ReviewSubmitResponse(order_id=order_id, items=results)


@router.get("/{order_id}/reviews", response_model=list[ReviewResponse])
async def list_order_reviews(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取本人对某订单已提交的评价（用于回显修改）"""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != current_user.id and not (
        current_user.is_feeder or current_user.is_admin
    ):
        raise HTTPException(status_code=403, detail="无权查看此订单的评价")

    stmt = (
        select(DishReview)
        .options(selectinload(DishReview.user))
        .where(DishReview.order_id == order_id)
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
