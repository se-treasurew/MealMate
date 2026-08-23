import asyncio
import unittest

from app.models import User
from app.routers.push import (
    PushTestRequest,
    SubscribeRequest,
    SubscriptionKeys,
    get_vapid_public_key,
    notify_feeders,
    notify_user,
    subscribe,
    test_push,
    unsubscribe,
)


class ExplodingSession:
    async def execute(self, *args, **kwargs):
        raise AssertionError("停用后的推送兼容层不得访问数据库")

    async def commit(self):
        raise AssertionError("停用后的推送兼容层不得写入数据库")


class PushRetirementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.user = User(id=1, username="tester", password_hash="x")
        self.db = ExplodingSession()

    async def test_vapid_endpoint_is_always_disabled(self):
        result = await get_vapid_public_key(self.user)
        self.assertEqual(result, {"enabled": False, "public_key": None})

    async def test_legacy_endpoints_return_without_database_access(self):
        payload = SubscribeRequest(
            endpoint="https://example.invalid/push",
            keys=SubscriptionKeys(p256dh="key", auth="auth"),
        )
        subscribed = await subscribe(payload, self.db, self.user)
        unsubscribed = await unsubscribe(payload.endpoint, self.db, self.user)
        tested = await test_push(PushTestRequest(message="test"), self.db, self.user)

        self.assertEqual(subscribed["enabled"], False)
        self.assertEqual(unsubscribed["enabled"], False)
        self.assertEqual(tested["enabled"], False)

    async def test_order_notification_hooks_are_immediate_noops(self):
        await asyncio.wait_for(notify_user(self.db, 1, "status"), timeout=0.1)
        await asyncio.wait_for(notify_feeders(self.db, "new order"), timeout=0.1)


if __name__ == "__main__":
    unittest.main()
