"""菜品评价功能单元测试：校验逻辑、权限、评分范围、upsert 行为"""
import asyncio
import unittest

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    User, Dish, DishCategory, Order, OrderItem, DishReview,
)
from app.routers.dishes import list_dishes
from app.routers.orders import submit_order_reviews
from app.routers.reviews import delete_review, list_dish_reviews
from app.schemas.review import ReviewCreate, ReviewItemCreate


def make_user(user_id: int, *, is_feeder: bool = False, is_admin: bool = False) -> User:
    return User(
        id=user_id,
        username=f"user{user_id}",
        password_hash="x",
        is_feeder=is_feeder,
        is_admin=is_admin,
    )


def make_dish(dish_id: int, category_id: int = 1) -> Dish:
    return Dish(id=dish_id, name=f"菜{dish_id}", category_id=category_id, created_by=1)


class ReviewValidationTests(unittest.IsolatedAsyncioTestCase):
    """submit_order_reviews 的业务规则测试（内存数据库）"""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session = AsyncSession(self.engine, expire_on_commit=False)

        # 基础数据：下单人、饲养员、分类、两个菜品、一个已完成订单
        async with self.session.begin():
            self.session.add_all([
                User(id=1, username="diner", password_hash="x"),
                User(id=2, username="feeder", password_hash="x", is_feeder=True),
                DishCategory(id=1, name="家常菜"),
                Dish(id=10, name="番茄炒蛋", category_id=1, created_by=2),
                Dish(id=11, name="红烧肉", category_id=1, created_by=2),
                Order(
                    id=100,
                    user_id=1,
                    meal_date=__import__("datetime").date(2026, 8, 23),
                    meal_type="午餐",
                    status="done",
                ),
                OrderItem(order_id=100, dish_id=10, quantity=1),
                OrderItem(order_id=100, dish_id=11, quantity=2),
            ])
        # 让 order.items 可用
        result = await self.session.execute(
            select(Order).options(selectinload(Order.items)).where(Order.id == 100)
        )
        self.done_order = result.scalar_one()

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    async def test_only_owner_can_review(self):
        other = make_user(3)
        with self.assertRaises(HTTPException) as ctx:
            await submit_order_reviews(
                100,
                ReviewCreate(items=[ReviewItemCreate(dish_id=10, rating=5)]),
                self.session,
                other,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_only_done_order_can_be_reviewed(self):
        self.session.add(
            Order(
                id=101,
                user_id=1,
                meal_date=self.done_order.meal_date,
                meal_type="晚餐",
                status="pending",
            )
        )
        await self.session.commit()
        result = await self.session.execute(
            select(Order).options(selectinload(Order.items)).where(Order.id == 101)
        )
        pending_order = result.scalar_one()

        with self.assertRaises(HTTPException) as ctx:
            await submit_order_reviews(
                101,
                ReviewCreate(items=[ReviewItemCreate(dish_id=10, rating=5)]),
                self.session,
                make_user(1),
            )
        self.assertEqual(ctx.exception.status_code, 400)
        _ = pending_order

    async def test_dish_must_belong_to_order(self):
        with self.assertRaises(HTTPException) as ctx:
            await submit_order_reviews(
                100,
                ReviewCreate(items=[ReviewItemCreate(dish_id=999, rating=5)]),
                self.session,
                make_user(1),
            )
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_duplicate_dish_in_payload_rejected(self):
        payload = ReviewCreate(items=[
            ReviewItemCreate(dish_id=10, rating=5),
            ReviewItemCreate(dish_id=10, rating=4),
        ])
        with self.assertRaises(HTTPException) as ctx:
            await submit_order_reviews(
                100,
                payload,
                self.session,
                make_user(1),
            )
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rating_bounds_enforced_by_schema(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ReviewItemCreate(dish_id=10, rating=0)
        with self.assertRaises(ValidationError):
            ReviewItemCreate(dish_id=10, rating=6)

    async def test_upsert_creates_then_updates(self):
        diner = make_user(1)
        # 首次提交：创建
        resp = await submit_order_reviews(
            100,
            ReviewCreate(items=[
                ReviewItemCreate(dish_id=10, rating=5, comment="好吃"),
                ReviewItemCreate(dish_id=11, rating=3),
            ]),
            self.session,
            diner,
        )
        self.assertFalse(any(i.updated for i in resp.items))

        rows = (
            await self.session.execute(select(DishReview).order_by(DishReview.dish_id))
        ).scalars().all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].rating, 5)
        self.assertEqual(rows[0].comment, "好吃")

        # 二次提交：更新，不产生新行
        resp2 = await submit_order_reviews(
            100,
            ReviewCreate(items=[ReviewItemCreate(dish_id=10, rating=2, comment="改主意了")]),
            self.session,
            diner,
        )
        self.assertTrue(resp2.items[0].updated)
        self.assertEqual(resp2.items[0].rating, 2)

        rows2 = (
            await self.session.execute(select(DishReview))
        ).scalars().all()
        self.assertEqual(len(rows2), 2)
        updated = next(r for r in rows2 if r.dish_id == 10)
        self.assertEqual(updated.rating, 2)
        self.assertEqual(updated.comment, "改主意了")

    async def test_dish_rating_summary_and_public_review_list(self):
        empty = await list_dishes(None, None, None, self.session, None)
        dish = next(item for item in empty if item.id == 10)
        self.assertIsNone(dish.avg_rating)
        self.assertEqual(dish.rating_count, 0)

        self.session.add(
            DishReview(
                dish_id=10,
                order_id=100,
                user_id=1,
                rating=4,
                comment="味道不错",
            )
        )
        await self.session.commit()

        rated = await list_dishes(None, None, None, self.session, None)
        dish = next(item for item in rated if item.id == 10)
        self.assertEqual(dish.avg_rating, 4.0)
        self.assertEqual(dish.rating_count, 1)

        reviews = await list_dish_reviews(10, self.session)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].comment, "味道不错")

    async def test_only_staff_can_delete_review(self):
        review = DishReview(
            dish_id=10,
            order_id=100,
            user_id=1,
            rating=4,
        )
        self.session.add(review)
        await self.session.commit()

        with self.assertRaises(HTTPException) as ctx:
            await delete_review(review.id, self.session, make_user(1))
        self.assertEqual(ctx.exception.status_code, 403)

        await delete_review(review.id, self.session, make_user(2, is_feeder=True))
        remaining = (await self.session.execute(select(DishReview))).scalars().all()
        self.assertEqual(remaining, [])


if __name__ == "__main__":
    unittest.main()
