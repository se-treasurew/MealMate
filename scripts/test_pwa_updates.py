from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PwaUpdateSourceTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_vite_uses_manual_service_worker_registration(self):
        source = self.read("frontend/vite.config.ts")

        self.assertIn("registerType: 'autoUpdate'", source)
        self.assertIn("injectRegister: false", source)

    def test_pwa_names_are_consistently_mealmate(self):
        vite_source = self.read("frontend/vite.config.ts")
        html_source = self.read("frontend/index.html")

        self.assertIn("name: '饭饭之交'", vite_source)
        self.assertIn("short_name: '饭饭之交'", vite_source)
        self.assertIn(
            '<meta name="apple-mobile-web-app-title" content="饭饭之交" />',
            html_source,
        )
        self.assertIn("<title>饭饭之交</title>", html_source)

    def test_service_worker_can_activate_without_claiming_existing_pages(self):
        source = self.read("frontend/src/sw.ts")

        self.assertIn("self.skipWaiting()", source)
        self.assertIn("SKIP_WAITING", source)
        self.assertIn("event.waitUntil(self.skipWaiting())", source)
        self.assertNotIn("clients.claim()", source)

    def test_shared_update_composable_exposes_update_controls(self):
        source = self.read("frontend/src/composables/useAppUpdate.ts")

        for symbol in (
            "updateAvailable",
            "checking",
            "checkForUpdate",
            "applyUpdate",
            "dismissUpdate",
            "currentRegistration.update",
            "updateDeferred",
            "pending",
            "waitForWorkerActivation",
        ):
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, source)

    def test_app_and_profile_expose_update_ui(self):
        app_source = self.read("frontend/src/App.vue")
        profile_source = self.read("frontend/src/views/Profile.vue")

        for text in ("发现新版本", "立即更新", "稍后", "applyUpdate"):
            with self.subTest(text=text):
                self.assertIn(text, app_source)
        for text in ("检查更新", "checkForUpdate", "checking"):
            with self.subTest(text=text):
                self.assertIn(text, profile_source)
        self.assertIn("result === 'pending'", profile_source)
        self.assertIn("right: 84px", app_source)

    def test_nginx_revalidates_entrypoints_and_caches_hashed_assets(self):
        source = self.read("frontend/nginx.conf")

        for path in (
            "/index.html",
            "/sw.js",
            "/manifest.webmanifest",
            "/favicon.png",
        ):
            with self.subTest(path=path):
                self.assertIn(path, source)
        self.assertIn("no-cache, must-revalidate", source)
        self.assertIn("location ^~ /icons/", source)
        self.assertIn("/assets/", source)
        self.assertIn("[^/]+[-_][A-Za-z0-9_-]{8,}", source)
        self.assertIn("public, max-age=31536000, immutable", source)
        self.assertIn("expires off", source)
        self.assertNotIn(
            "location ~* \\.(jpg|jpeg|png|gif|ico|css|js|woff|woff2)$",
            source,
        )

    def test_nginx_hash_regex_is_quoted_for_nginx_parser(self):
        source = self.read("frontend/nginx.conf")

        self.assertIn(
            'location ~* "^/assets/[^/]+[-_][A-Za-z0-9_-]{8,}[.](css|js|woff|woff2)$" {',
            source,
        )
        self.assertNotIn(
            "location ~* ^/assets/[^/]+[-_][A-Za-z0-9_-]{8,}",
            source,
        )

    def test_ci_validates_frontend_nginx_configuration(self):
        source = self.read(".github/workflows/release-check.yml")

        self.assertIn(
            "docker compose run --rm --no-deps frontend nginx -t",
            source,
        )


if __name__ == "__main__":
    unittest.main()
