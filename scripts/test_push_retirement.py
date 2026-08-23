import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PushRetirementSourceTests(unittest.TestCase):
    def test_frontend_has_no_push_controls_or_service_worker_handlers(self):
        profile = (ROOT / "frontend/src/views/Profile.vue").read_text(encoding="utf-8")
        service_worker = (ROOT / "frontend/src/sw.ts").read_text(encoding="utf-8")

        self.assertNotIn("usePush", profile)
        self.assertNotIn("发送测试推送", profile)
        self.assertNotIn("addEventListener('push'", service_worker)
        self.assertNotIn("addEventListener('notificationclick'", service_worker)

    def test_backend_has_no_web_push_runtime_dependency(self):
        requirements = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
        push_router = (ROOT / "backend/app/routers/push.py").read_text(encoding="utf-8")

        self.assertNotIn("pywebpush", requirements)
        self.assertNotIn("py-vapid", requirements)
        self.assertNotIn("send_push", push_router)


if __name__ == "__main__":
    unittest.main()
