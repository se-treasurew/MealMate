import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    Dish,
    DishCategory,
    DishFavorite,
    DishImage,
    DishReview,
    DishTag,
    Order,
    OrderItem,
    Tag,
    User,
)
from app.routers import dishes as dishes_router, orders as orders_router
from app.schemas.review import ReviewCreate


def make_user(user_id: int, *, is_feeder: bool = False, is_admin: bool = False) -> User:
    return User(
        id=user_id,
        username=f"user{user_id}",
        password_hash="x",
        is_active=True,
        is_feeder=is_feeder,
        is_admin=is_admin,
    )


class FavoriteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session = AsyncSession(self.engine, expire_on_commit=False)

        now = datetime.now(timezone.utc)
        self.session.add_all([
            make_user(1),
            make_user(2),
            make_user(3, is_feeder=True),
            DishCategory(id=1, name="主食", sort_order=1),
            DishCategory(id=2, name="饮品", sort_order=2),
            Dish(
                id=10,
                name="新炒饭",
                category_id=1,
                created_by=1,
                status="active",
                created_at=now,
            ),
            Dish(
                id=11,
                name="老炒饭",
                category_id=1,
                created_by=1,
                status="active",
                created_at=now - timedelta(days=1),
            ),
            Dish(
                id=12,
                name="隐藏炒饭",
                category_id=1,
                created_by=1,
                status="inactive",
                created_at=now + timedelta(days=1),
            ),
            Dish(
                id=13,
                name="果汁",
                category_id=2,
                created_by=1,
                status="active",
                created_at=now + timedelta(hours=1),
            ),
        ])
        await self.session.commit()

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    async def test_favorite_is_idempotent_and_scoped_to_current_user(self):
        favorite_dish = getattr(dishes_router, "favorite_dish", None)
        unfavorite_dish = getattr(dishes_router, "unfavorite_dish", None)
        self.assertIsNotNone(favorite_dish, "缺少收藏菜品接口")
        self.assertIsNotNone(unfavorite_dish, "缺少取消收藏接口")

        user1 = await self.session.get(User, 1)
        user2 = await self.session.get(User, 2)
        await favorite_dish(11, self.session, user1)
        await favorite_dish(11, self.session, user1)

        count = await self.session.scalar(select(func.count(DishFavorite.id)))
        self.assertEqual(count, 1)

        mine = await dishes_router.list_dishes(None, None, None, self.session, user1)
        other = await dishes_router.list_dishes(None, None, None, self.session, user2)
        guest = await dishes_router.list_dishes(None, None, None, self.session, None)
        self.assertEqual([dish.id for dish in mine], [13, 10, 11])
        self.assertTrue(next(dish for dish in mine if dish.id == 11).is_favorite)
        self.assertFalse(any(dish.is_favorite for dish in other))
        self.assertFalse(any(dish.is_favorite for dish in guest))

        await unfavorite_dish(11, self.session, user1)
        await unfavorite_dish(11, self.session, user1)
        count = await self.session.scalar(select(func.count(DishFavorite.id)))
        self.assertEqual(count, 0)

    async def test_favorite_does_not_reorder_category_or_search_results(self):
        favorite_dish = getattr(dishes_router, "favorite_dish", None)
        self.assertIsNotNone(favorite_dish, "缺少收藏菜品接口")
        user = await self.session.get(User, 1)
        await favorite_dish(11, self.session, user)

        category = await dishes_router.list_dishes(1, None, None, self.session, user)
        search = await dishes_router.list_dishes(None, None, "炒饭", self.session, user)
        detail = await dishes_router.get_dish(11, self.session, user)

        self.assertEqual([dish.id for dish in category], [10, 11])
        self.assertEqual([dish.id for dish in search], [10, 11])
        self.assertTrue(detail.is_favorite)

    async def test_favorites_page_is_recent_first_scoped_and_role_aware(self):
        list_favorite_dishes = getattr(dishes_router, "list_favorite_dishes", None)
        self.assertIsNotNone(list_favorite_dishes, "缺少收藏列表接口")

        now = datetime.now(timezone.utc)
        self.session.add_all([
            DishFavorite(user_id=1, dish_id=10, created_at=now - timedelta(hours=2)),
            DishFavorite(user_id=1, dish_id=11, created_at=now - timedelta(hours=1)),
            DishFavorite(user_id=1, dish_id=12, created_at=now),
            DishFavorite(user_id=3, dish_id=10, created_at=now - timedelta(hours=2)),
            DishFavorite(user_id=3, dish_id=11, created_at=now - timedelta(hours=1)),
            DishFavorite(user_id=3, dish_id=12, created_at=now),
        ])
        await self.session.commit()

        diner = await list_favorite_dishes(
            self.session, await self.session.get(User, 1)
        )
        other = await list_favorite_dishes(
            self.session, await self.session.get(User, 2)
        )
        feeder = await list_favorite_dishes(
            self.session, await self.session.get(User, 3)
        )

        self.assertEqual([dish.id for dish in diner], [11, 10])
        self.assertEqual(other, [])
        self.assertEqual([dish.id for dish in feeder], [12, 11, 10])
        self.assertTrue(all(dish.is_favorite for dish in diner + feeder))

    async def test_favorites_search_matches_dish_name_or_tag_and_excludes_nonmatches(self):
        now = datetime.now(timezone.utc)
        self.session.add_all([
            Tag(id=1, name="清爽"),
            DishFavorite(user_id=1, dish_id=10, created_at=now - timedelta(hours=2)),
            DishFavorite(user_id=1, dish_id=11, created_at=now - timedelta(hours=1)),
            DishFavorite(user_id=1, dish_id=13, created_at=now),
        ])
        await self.session.flush()
        self.session.add(DishTag(dish_id=13, tag_id=1))
        await self.session.commit()

        user = await self.session.get(User, 1)
        by_name = await dishes_router.list_favorite_dishes(
            self.session, user, search="新炒"
        )
        by_tag = await dishes_router.list_favorite_dishes(
            self.session, user, search="清爽"
        )
        no_match = await dishes_router.list_favorite_dishes(
            self.session, user, search="不存在"
        )

        self.assertEqual([dish.id for dish in by_name], [10])
        self.assertEqual([dish.id for dish in by_tag], [13])
        self.assertEqual(no_match, [])

    def test_favorites_static_route_precedes_dynamic_dish_route(self):
        paths = [route.path for route in dishes_router.router.routes]
        self.assertIn("/favorites", paths)
        self.assertLess(paths.index("/favorites"), paths.index("/{dish_id}"))

    async def test_inactive_dish_cannot_be_newly_favorited(self):
        favorite_dish = getattr(dishes_router, "favorite_dish", None)
        self.assertIsNotNone(favorite_dish, "缺少收藏菜品接口")
        user = await self.session.get(User, 1)
        with self.assertRaises(HTTPException) as raised:
            await favorite_dish(12, self.session, user)
        self.assertEqual(raised.exception.status_code, 404)


class PermanentOrderDeletionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session = AsyncSession(self.engine, expire_on_commit=False)

        self.session.add_all([
            make_user(1, is_admin=True),
            make_user(2),
            make_user(3, is_feeder=True),
            DishCategory(id=1, name="主食", sort_order=1),
            Dish(
                id=10,
                name="炒饭",
                category_id=1,
                created_by=1,
                status="active",
            ),
            Order(id=100, user_id=2, meal_date=datetime.now().date(), meal_type="午餐", status="done"),
            Order(id=101, user_id=2, meal_date=datetime.now().date(), meal_type="晚餐", status="cancelled"),
            Order(id=102, user_id=2, meal_date=datetime.now().date(), meal_type="午餐", status="pending"),
            OrderItem(id=1000, order_id=100, dish_id=10, quantity=1),
            OrderItem(id=1001, order_id=101, dish_id=10, quantity=1),
            OrderItem(id=1002, order_id=102, dish_id=10, quantity=1),
            DishReview(id=2000, dish_id=10, order_id=100, user_id=2, rating=5),
        ])
        await self.session.commit()

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    async def test_only_admin_can_permanently_delete_terminal_order(self):
        delete_order = getattr(orders_router, "permanently_delete_order", None)
        self.assertIsNotNone(delete_order, "缺少管理员永久删除订单接口")

        with self.assertRaises(HTTPException) as member_error:
            await delete_order(101, self.session, await self.session.get(User, 2))
        self.assertEqual(member_error.exception.status_code, 403)

        with self.assertRaises(HTTPException) as feeder_error:
            await delete_order(101, self.session, await self.session.get(User, 3))
        self.assertEqual(feeder_error.exception.status_code, 403)

        await delete_order(101, self.session, await self.session.get(User, 1))
        self.assertIsNone(await self.session.get(Order, 101))

    async def test_active_order_cannot_be_permanently_deleted(self):
        delete_order = getattr(orders_router, "permanently_delete_order", None)
        self.assertIsNotNone(delete_order, "缺少管理员永久删除订单接口")

        with self.assertRaises(HTTPException) as raised:
            await delete_order(102, self.session, await self.session.get(User, 1))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIsNotNone(await self.session.get(Order, 102))

    async def test_deleting_done_order_removes_items_reviews_and_rating(self):
        delete_order = getattr(orders_router, "permanently_delete_order", None)
        self.assertIsNotNone(delete_order, "缺少管理员永久删除订单接口")

        before = await dishes_router.list_dishes(None, None, None, self.session, None)
        self.assertEqual(before[0].rating_count, 1)

        await delete_order(100, self.session, await self.session.get(User, 1))

        self.assertIsNone(await self.session.get(Order, 100))
        self.assertIsNone(await self.session.get(OrderItem, 1000))
        self.assertIsNone(await self.session.get(DishReview, 2000))
        after = await dishes_router.list_dishes(None, None, None, self.session, None)
        self.assertEqual(after[0].rating_count, 0)
        self.assertIsNone(after[0].avg_rating)


class OrderDishPresentationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session = AsyncSession(self.engine, expire_on_commit=False)

        today = datetime.now().date()
        self.session.add_all([
            make_user(1),
            make_user(2, is_feeder=True),
            DishCategory(id=1, name="主食", sort_order=1),
            Dish(id=10, name="炒饭", category_id=1, created_by=2, status="active"),
            Dish(id=11, name="下架面", category_id=1, created_by=2, status="inactive"),
            Dish(id=12, name="无图汤", category_id=1, created_by=2, status="active"),
            DishImage(
                id=100,
                dish_id=10,
                image_path="late.webp",
                thumbnail_path="late_thumb.webp",
                sort_order=5,
            ),
            DishImage(
                id=101,
                dish_id=10,
                image_path="cover.webp",
                thumbnail_path="cover_thumb.webp",
                sort_order=1,
            ),
            DishImage(
                id=102,
                dish_id=11,
                image_path="inactive.webp",
                thumbnail_path=None,
                sort_order=0,
            ),
            Order(id=100, user_id=1, meal_date=today, meal_type="午餐", status="done"),
            Order(id=101, user_id=1, meal_date=today, meal_type="晚餐", status="done"),
            OrderItem(id=1000, order_id=100, dish_id=10, quantity=1),
            OrderItem(id=1001, order_id=100, dish_id=11, quantity=2),
            OrderItem(id=1002, order_id=100, dish_id=12, quantity=1),
            OrderItem(id=1003, order_id=100, dish_id=99, quantity=1),
            OrderItem(id=1004, order_id=101, dish_id=10, quantity=1),
        ])
        await self.session.commit()

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    async def test_order_items_expose_current_cover_and_role_aware_availability(self):
        diner = await self.session.get(User, 1)
        feeder = await self.session.get(User, 2)

        diner_response = await orders_router.get_order(100, self.session, diner)
        feeder_response = await orders_router.get_order(100, self.session, feeder)
        diner_items = {item.dish_id: item for item in diner_response.items}
        feeder_items = {item.dish_id: item for item in feeder_response.items}

        self.assertEqual(diner_items[10].dish_image_path, "cover_thumb.webp")
        self.assertTrue(diner_items[10].dish_available)
        self.assertIsNone(diner_items[11].dish_image_path)
        self.assertFalse(diner_items[11].dish_available)
        self.assertIsNone(diner_items[12].dish_image_path)
        self.assertTrue(diner_items[12].dish_available)
        self.assertIsNone(diner_items[99].dish_image_path)
        self.assertFalse(diner_items[99].dish_available)

        self.assertEqual(feeder_items[11].dish_image_path, "inactive.webp")
        self.assertTrue(feeder_items[11].dish_available)

    async def test_order_list_batches_dish_and_image_queries(self):
        statements: list[str] = []

        def capture_statement(_conn, _cursor, statement, _params, _context, _many):
            statements.append(" ".join(statement.lower().split()))

        event.listen(self.engine.sync_engine, "before_cursor_execute", capture_statement)
        try:
            responses = await orders_router.list_orders(
                None, False, self.session, await self.session.get(User, 2)
            )
        finally:
            event.remove(
                self.engine.sync_engine, "before_cursor_execute", capture_statement
            )

        self.assertEqual(len(responses), 2)
        dish_queries = [sql for sql in statements if " from dish " in f" {sql} "]
        image_queries = [sql for sql in statements if " from dish_image " in f" {sql} "]
        self.assertEqual(len(dish_queries), 1)
        self.assertEqual(len(image_queries), 1)


class PermanentDeleteConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name, "concurrent.sqlite3").as_posix()
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{database_path}",
            connect_args={"timeout": 10},
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as session:
            session.add_all([
                make_user(1, is_admin=True),
                make_user(2),
                DishCategory(id=1, name="主食", sort_order=1),
                Dish(id=10, name="炒饭", category_id=1, created_by=1, status="active"),
                Order(
                    id=100,
                    user_id=2,
                    meal_date=datetime.now().date(),
                    meal_type="午餐",
                    status="done",
                ),
                OrderItem(id=1000, order_id=100, dish_id=10, quantity=1),
            ])
            await session.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_concurrent_review_cannot_survive_permanent_order_deletion(self):
        self.assertTrue(
            hasattr(orders_router, "begin_order_write_transaction"),
            "评价提交与永久删除需要共享 SQLite 写事务锁",
        )
        async with self.sessions() as admin_session, self.sessions() as owner_session:
            admin = await admin_session.get(User, 1)
            owner = await owner_session.get(User, 2)
            results = await asyncio.gather(
                orders_router.permanently_delete_order(100, admin_session, admin),
                orders_router.submit_order_reviews(
                    100,
                    ReviewCreate(items=[{"dish_id": 10, "rating": 5}]),
                    owner_session,
                    owner,
                ),
                return_exceptions=True,
            )

        self.assertTrue(
            results[1] is None or isinstance(results[1], HTTPException)
            or getattr(results[1], "order_id", None) == 100
        )
        async with self.sessions() as verify_session:
            self.assertIsNone(await verify_session.get(Order, 100))
            review_count = await verify_session.scalar(select(func.count(DishReview.id)))
            self.assertEqual(review_count, 0)


if __name__ == "__main__":
    unittest.main()
