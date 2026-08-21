import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core import deps, security as core_security
from app.core.config import settings
from app import init_db
from app.routers import auth, dishes, orders, users
from app.schemas.auth import UpdateProfileRequest
from app.utils.image import remove_image_files, save_image


class TokenVersionTests(unittest.TestCase):
    def test_token_version_must_match_user(self):
        matcher = getattr(deps, "token_matches_user", None)
        self.assertIsNotNone(matcher, "缺少 token 版本校验函数")

        user = SimpleNamespace(id=7, token_version=3)
        self.assertTrue(matcher({"sub": "7", "ver": 3}, user))
        self.assertFalse(matcher({"sub": "7", "ver": 2}, user))
        self.assertFalse(matcher({"sub": "7"}, user))
        self.assertFalse(matcher({"sub": "8", "ver": 3}, user))


class TokenCredentialParsingTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_integer_subject_is_treated_as_invalid_credentials(self):
        class UnexpectedDatabase:
            async def execute(self, _statement):
                raise AssertionError("无效 subject 不应查询数据库")

        credentials = SimpleNamespace(credentials="signed-token")
        payload = {"type": "access", "sub": "not-an-integer", "ver": 0}

        with patch("app.core.deps.decode_token", return_value=payload):
            user = await deps._get_user_by_credentials(credentials, UnexpectedDatabase())

        self.assertIsNone(user)


class AtomicTokenVersionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE TABLE user ("
                    "id INTEGER PRIMARY KEY, password_hash VARCHAR(255) NOT NULL, "
                    "must_change_password BOOLEAN NOT NULL, "
                    "token_version INTEGER NOT NULL, is_active BOOLEAN NOT NULL)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO user "
                    "(id, password_hash, must_change_password, token_version, is_active) "
                    "VALUES (1, 'old', 1, 0, 1), (2, 'old', 0, 0, 1)"
                )
            )

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_stale_password_update_cannot_reuse_token_version(self):
        updater = getattr(core_security, "try_replace_password", None)
        self.assertIsNotNone(updater, "缺少密码与 token_version 的原子更新")

        async with AsyncSession(self.engine) as session:
            first = await updater(
                session,
                user_id=1,
                expected_token_version=0,
                password_hash="first",
                must_change_password=False,
            )
            await session.commit()

        async with AsyncSession(self.engine) as session:
            stale = await updater(
                session,
                user_id=1,
                expected_token_version=0,
                password_hash="stale",
                must_change_password=False,
            )
            await session.rollback()
            row = (
                await session.execute(
                    text(
                        "SELECT password_hash, token_version FROM user WHERE id = 1"
                    )
                )
            ).one()

        self.assertTrue(first)
        self.assertFalse(stale)
        self.assertEqual(tuple(row), ("first", 1))

    async def test_stale_disable_cannot_reuse_token_version(self):
        updater = getattr(core_security, "try_disable_user", None)
        self.assertIsNotNone(updater, "缺少禁用账号与 token_version 的原子更新")

        async with AsyncSession(self.engine) as session:
            first = await updater(
                session,
                user_id=2,
                expected_token_version=0,
            )
            await session.commit()

        async with AsyncSession(self.engine) as session:
            stale = await updater(
                session,
                user_id=2,
                expected_token_version=0,
            )
            await session.rollback()
            row = (
                await session.execute(
                    text(
                        "SELECT is_active, token_version FROM user WHERE id = 2"
                    )
                )
            ).one()

        self.assertTrue(first)
        self.assertFalse(stale)
        self.assertEqual(tuple(row), (0, 1))


class InitialAdminPasswordTests(unittest.TestCase):
    def test_initial_password_is_required(self):
        getter = getattr(init_db, "get_initial_admin_password", None)
        self.assertIsNotNone(getter, "缺少初始管理员密码校验函数")
        with patch.object(settings, "ADMIN_INITIAL_PASSWORD", None):
            with self.assertRaises(RuntimeError):
                getter()

    def test_initial_password_must_have_at_least_six_characters(self):
        getter = getattr(init_db, "get_initial_admin_password", None)
        self.assertIsNotNone(getter, "缺少初始管理员密码校验函数")
        with patch.object(settings, "ADMIN_INITIAL_PASSWORD", "12345"):
            with self.assertRaises(RuntimeError):
                getter()

    def test_initial_password_is_read_from_settings(self):
        getter = getattr(init_db, "get_initial_admin_password", None)
        self.assertIsNotNone(getter, "缺少初始管理员密码校验函数")
        with patch.object(settings, "ADMIN_INITIAL_PASSWORD", "Safe@123"):
            self.assertEqual(getter(), "Safe@123")


class ForcedPasswordChangeTests(unittest.TestCase):
    def test_protected_api_is_blocked_until_password_is_changed(self):
        guard = getattr(deps, "enforce_password_change", None)
        self.assertIsNotNone(guard, "缺少后端强制改密守卫")
        user = SimpleNamespace(must_change_password=True)

        with self.assertRaises(HTTPException) as raised:
            guard(user, "/api/orders")

        self.assertEqual(raised.exception.status_code, 403)

    def test_password_and_me_endpoints_remain_available(self):
        guard = getattr(deps, "enforce_password_change", None)
        self.assertIsNotNone(guard, "缺少后端强制改密守卫")
        user = SimpleNamespace(must_change_password=True)

        guard(user, "/api/auth/me")
        guard(user, "/api/auth/password")


class OptionalAuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def test_forced_password_change_user_is_treated_as_guest(self):
        user = SimpleNamespace(must_change_password=True)
        with patch(
            "app.core.deps._get_user_by_credentials",
            new=AsyncMock(return_value=user),
        ):
            result = await deps.get_current_user_optional(None, SimpleNamespace())

        self.assertIsNone(result)


class PasswordResetTargetTests(unittest.TestCase):
    def test_admin_password_cannot_be_reset_without_old_password(self):
        guard = getattr(users, "validate_password_reset_target", None)
        self.assertIsNotNone(guard, "缺少管理员重置密码目标校验")
        admin = SimpleNamespace(id=1, is_admin=True)

        with self.assertRaises(HTTPException) as raised:
            guard(admin, admin)

        self.assertEqual(raised.exception.status_code, 400)

    def test_regular_member_password_can_be_reset(self):
        guard = getattr(users, "validate_password_reset_target", None)
        self.assertIsNotNone(guard, "缺少管理员重置密码目标校验")
        admin = SimpleNamespace(id=1, is_admin=True)
        member = SimpleNamespace(id=2, is_admin=False)

        guard(member, admin)


class OrderTransitionTests(unittest.TestCase):
    def test_staff_can_follow_forward_state_machine(self):
        validator = getattr(orders, "validate_status_transition", None)
        self.assertIsNotNone(validator, "缺少订单状态流转校验函数")

        validator("pending", "accepted", is_staff=True, is_owner=False)
        validator("accepted", "cooking", is_staff=True, is_owner=False)
        validator("cooking", "done", is_staff=True, is_owner=False)

    def test_skips_reopens_and_repeated_states_are_rejected(self):
        validator = getattr(orders, "validate_status_transition", None)
        self.assertIsNotNone(validator, "缺少订单状态流转校验函数")

        invalid_transitions = [
            ("pending", "cooking"),
            ("accepted", "done"),
            ("cooking", "accepted"),
            ("done", "accepted"),
            ("cancelled", "accepted"),
            ("accepted", "accepted"),
        ]
        for current, target in invalid_transitions:
            with self.subTest(current=current, target=target):
                with self.assertRaises(HTTPException) as raised:
                    validator(current, target, is_staff=True, is_owner=False)
                self.assertEqual(raised.exception.status_code, 400)

    def test_only_owner_can_cancel_pending_order(self):
        validator = getattr(orders, "validate_status_transition", None)
        self.assertIsNotNone(validator, "缺少订单状态流转校验函数")

        validator("pending", "cancelled", is_staff=False, is_owner=True)
        with self.assertRaises(HTTPException) as raised:
            validator("pending", "cancelled", is_staff=True, is_owner=False)
        self.assertEqual(raised.exception.status_code, 403)


class OrderAtomicTransitionTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_status_cannot_be_updated_twice(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        'CREATE TABLE "order" '
                        '(id INTEGER PRIMARY KEY, status VARCHAR(20) NOT NULL, '
                        'updated_at DATETIME)'
                    )
                )
                await connection.execute(
                    text('INSERT INTO "order" (id, status) VALUES (1, \'pending\')')
                )

            async with AsyncSession(engine) as session:
                first = await orders.try_transition_order(
                    session,
                    order_id=1,
                    expected_status="pending",
                    target_status="accepted",
                )
                await session.commit()

            async with AsyncSession(engine) as session:
                stale = await orders.try_transition_order(
                    session,
                    order_id=1,
                    expected_status="pending",
                    target_status="accepted",
                )
                await session.rollback()

            self.assertTrue(first)
            self.assertFalse(stale)
        finally:
            await engine.dispose()


class AvatarValidationTests(unittest.TestCase):
    def test_avatar_accepts_presets_current_upload_and_empty_value(self):
        validator = getattr(auth, "validate_avatar_url", None)
        self.assertIsNotNone(validator, "缺少头像路径白名单校验函数")

        current = "2026/08/current_thumb.webp"
        self.assertIsNone(validator(None, current))
        self.assertEqual(validator("/avatars/cat.png", current), "/avatars/cat.png")
        self.assertEqual(validator(current, current), current)

    def test_avatar_rejects_external_and_other_upload_paths(self):
        validator = getattr(auth, "validate_avatar_url", None)
        self.assertIsNotNone(validator, "缺少头像路径白名单校验函数")

        current = "2026/08/current_thumb.webp"
        for value in (
            "https://example.com/avatar.png",
            "/uploads/2026/08/other.webp",
            "2026/08/other.webp",
            "/avatars/not-a-preset.png",
        ):
            with self.subTest(value=value):
                with self.assertRaises(HTTPException) as raised:
                    validator(value, current)
                self.assertEqual(raised.exception.status_code, 400)


class ImageValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_reader_is_bounded_before_size_validation(self):
        class OversizedReader:
            filename = "large.png"

            def __init__(self):
                self.requested_size = None

            async def read(self, size=-1):
                self.requested_size = size
                return b"x" * (settings.MAX_UPLOAD_SIZE + 1)

        upload = OversizedReader()
        with self.assertRaises(HTTPException) as raised:
            await save_image(upload)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(upload.requested_size, settings.MAX_UPLOAD_SIZE + 1)

    async def test_corrupt_image_is_rejected_without_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            upload = UploadFile(filename="broken.png", file=io.BytesIO(b"not-an-image"))
            with patch("app.utils.image.settings.UPLOAD_DIR", temp_dir):
                with self.assertRaises(HTTPException) as raised:
                    await save_image(upload)

            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(list(Path(temp_dir).rglob("*")), [])

    async def test_disguised_image_format_is_rejected_without_files(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(image_bytes, format="JPEG")

        with tempfile.TemporaryDirectory() as temp_dir:
            upload = UploadFile(filename="fake.png", file=io.BytesIO(image_bytes.getvalue()))
            with patch("app.utils.image.settings.UPLOAD_DIR", temp_dir):
                with self.assertRaises(HTTPException) as raised:
                    await save_image(upload)

            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(list(Path(temp_dir).rglob("*")), [])

    async def test_thumbnail_encoding_failure_is_rejected_without_files(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(image_bytes, format="PNG")

        with tempfile.TemporaryDirectory() as temp_dir:
            upload = UploadFile(
                filename="thumbnail-failure.png",
                file=io.BytesIO(image_bytes.getvalue()),
            )
            with (
                patch("app.utils.image.settings.UPLOAD_DIR", temp_dir),
                patch(
                    "PIL.Image.Image.save",
                    side_effect=[None, OSError("thumbnail encoding failed")],
                ),
            ):
                with self.assertRaises(HTTPException) as raised:
                    await save_image(upload)

            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(list(Path(temp_dir).rglob("*")), [])

    async def test_valid_image_is_normalized_to_webp(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (400, 300), "red").save(image_bytes, format="PNG")

        with tempfile.TemporaryDirectory() as temp_dir:
            upload = UploadFile(filename="valid.png", file=io.BytesIO(image_bytes.getvalue()))
            with patch("app.utils.image.settings.UPLOAD_DIR", temp_dir):
                image_path, thumb_path = await save_image(upload)

            self.assertTrue(image_path.endswith(".webp"))
            self.assertTrue(thumb_path.endswith("_thumb.webp"))
            created_files = [path for path in Path(temp_dir).rglob("*") if path.is_file()]
            self.assertEqual(len(created_files), 2)
            for path in created_files:
                with Image.open(path) as image:
                    self.assertEqual(image.format, "WEBP")

    async def test_exif_orientation_is_applied_before_encoding(self):
        image_bytes = io.BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (3, 5), "red").save(
            image_bytes,
            format="JPEG",
            exif=exif,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            upload = UploadFile(
                filename="rotated.jpg",
                file=io.BytesIO(image_bytes.getvalue()),
            )
            with patch("app.utils.image.settings.UPLOAD_DIR", temp_dir):
                image_path, _ = await save_image(upload)

            with Image.open(Path(temp_dir) / image_path) as image:
                self.assertEqual(image.size, (5, 3))


class ImageLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def test_cleanup_never_escapes_upload_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "uploads"
            root.mkdir()
            inside = root / "inside.webp"
            outside = Path(temp_dir) / "outside.webp"
            inside.write_bytes(b"inside")
            outside.write_bytes(b"outside")

            with patch("app.utils.image.settings.UPLOAD_DIR", str(root)):
                remove_image_files(["inside.webp", "../outside.webp"])

            self.assertFalse(inside.exists())
            self.assertTrue(outside.exists())

    async def test_avatar_upload_cleans_unused_and_replaced_files_after_commit(self):
        user = SimpleNamespace(avatar_url="2025/07/old_thumb.webp")
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())

        with (
            patch(
                "app.routers.auth.save_image",
                new=AsyncMock(return_value=("2026/08/new.webp", "2026/08/new_thumb.webp")),
            ),
            patch("app.routers.auth.remove_image_files") as cleanup,
        ):
            await auth.upload_avatar(SimpleNamespace(), user, db)

        self.assertEqual(user.avatar_url, "2026/08/new_thumb.webp")
        cleanup.assert_called_once_with(
            [
                "2026/08/new.webp",
                "2025/07/old_thumb.webp",
                "2025/07/old.webp",
            ]
        )

    async def test_avatar_upload_rolls_back_and_cleans_new_files_on_commit_error(self):
        user = SimpleNamespace(avatar_url="/avatars/cat.png")
        db = SimpleNamespace(
            commit=AsyncMock(side_effect=RuntimeError("commit failed")),
            refresh=AsyncMock(),
            rollback=AsyncMock(),
        )

        with (
            patch(
                "app.routers.auth.save_image",
                new=AsyncMock(return_value=("2026/08/new.webp", "2026/08/new_thumb.webp")),
            ),
            patch("app.routers.auth.remove_image_files") as cleanup,
            self.assertRaises(RuntimeError),
        ):
            await auth.upload_avatar(SimpleNamespace(), user, db)

        db.rollback.assert_awaited_once()
        cleanup.assert_called_once_with(["2026/08/new.webp", "2026/08/new_thumb.webp"])

    async def test_clearing_avatar_removes_previous_upload_after_commit(self):
        user = SimpleNamespace(
            avatar_url="2025/07/old_thumb.webp",
            nickname="member",
        )
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

        with patch("app.routers.auth.remove_image_files") as cleanup:
            await auth.update_profile(UpdateProfileRequest(avatar_url=""), user, db)

        self.assertIsNone(user.avatar_url)
        cleanup.assert_called_once_with(
            ["2025/07/old_thumb.webp", "2025/07/old.webp"]
        )

    async def test_dish_image_files_are_removed_only_after_database_commit(self):
        events = []
        image = SimpleNamespace(
            image_path="2026/08/dish.webp",
            thumbnail_path="2026/08/dish_thumb.webp",
        )

        class Result:
            def scalar_one_or_none(self):
                return image

        class Database:
            async def execute(self, _statement):
                return Result()

            async def delete(self, _image):
                events.append("delete")

            async def commit(self):
                events.append("commit")

        user = SimpleNamespace(is_feeder=True, is_admin=False)
        with patch(
            "app.routers.dishes.remove_image_files",
            side_effect=lambda _paths: events.append("remove"),
        ):
            await dishes.delete_dish_image(1, 1, Database(), user)

        self.assertEqual(events, ["delete", "commit", "remove"])


class DishUploadBatchTests(unittest.TestCase):
    def test_batch_upload_count_is_limited(self):
        validator = getattr(dishes, "validate_upload_batch", None)
        self.assertIsNotNone(validator, "缺少菜品批量上传数量校验")

        validator([object()] * 5)
        with self.assertRaises(HTTPException) as raised:
            validator([object()] * 6)

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
