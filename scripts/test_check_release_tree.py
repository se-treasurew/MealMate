import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import check_release_tree


class PathRuleTests(unittest.TestCase):
    def test_sensitive_and_runtime_paths_are_rejected(self):
        rejected = (
            "backend/.env",
            "nested/service/.env.production",
            "deploy/private.pem",
            "backend/data/mealmate.sqlite3",
            "backend/uploads/2026/08/avatar.webp",
            "frontend/dist/assets/app.js",
            "tools/__pycache__/helper.pyc",
            "backend/debug_repro.py",
            "prompt_v2.md",
        )
        for path in rejected:
            with self.subTest(path=path):
                self.assertIsNotNone(check_release_tree.path_violation(path))

    def test_examples_and_source_configuration_are_allowed(self):
        allowed = (
            "backend/.env.example",
            "frontend/vite.config.ts",
            "backend/app/core/config.py",
        )
        for path in allowed:
            with self.subTest(path=path):
                self.assertIsNone(check_release_tree.path_violation(path))


class WorktreeCollectionTests(unittest.TestCase):
    def test_worktree_includes_untracked_but_excludes_deleted_and_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
            (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", ".gitignore", "tracked.txt"], cwd=root, check=True
            )
            (root / "tracked.txt").unlink()
            (root / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            (root / "ignored.txt").write_text("ignored\n", encoding="utf-8")

            paths = check_release_tree.list_worktree_paths(root)

            self.assertIn("untracked.txt", paths)
            self.assertNotIn("tracked.txt", paths)
            self.assertNotIn("ignored.txt", paths)


class DistContentTests(unittest.TestCase):
    def test_built_output_with_local_backend_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist = Path(temp_dir)
            (dist / "assets").mkdir()
            (dist / "assets" / "app.js").write_text(
                'const api="http://localhost:8000"', encoding="utf-8"
            )

            violations = check_release_tree.check_dist(dist)

            self.assertEqual(len(violations), 1)
            self.assertIn("localhost:8000", violations[0])

    def test_built_output_without_local_backend_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist = Path(temp_dir)
            (dist / "index.html").write_text("<main>MealMate</main>", encoding="utf-8")

            self.assertEqual(check_release_tree.check_dist(dist), [])


class DeploymentUploadLimitTests(unittest.TestCase):
    def test_caddy_limits_multipart_bodies_before_proxying(self):
        caddyfile = (
            Path(__file__).resolve().parents[1] / "docker" / "Caddyfile"
        ).read_text(encoding="utf-8")

        self.assertIn("@avatarUpload path /api/auth/avatar", caddyfile)
        self.assertIn("max_size 6MB", caddyfile)
        self.assertIn(
            "@dishImages path_regexp dishImages ^/api/dishes/[0-9]+/images$",
            caddyfile,
        )
        self.assertIn("max_size 32MB", caddyfile)


if __name__ == "__main__":
    unittest.main()
