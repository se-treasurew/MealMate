import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class LegacySqliteMigrationTests(unittest.TestCase):
    def test_init_db_only_requires_password_when_creating_admin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "initialized.db"
            environment = os.environ.copy()
            environment.update(
                {
                    "PYTHONUTF8": "1",
                    "JWT_SECRET": "test",
                    "ADMIN_INITIAL_PASSWORD": "Initial@123",
                    "DATABASE_URL": f"sqlite+aiosqlite:///{database.as_posix()}",
                }
            )

            first = subprocess.run(
                [sys.executable, "-m", "app.init_db"],
                cwd=BACKEND_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)

            # 显式空值覆盖开发者本地可能存在的 backend/.env。
            environment["ADMIN_INITIAL_PASSWORD"] = ""
            second = subprocess.run(
                [sys.executable, "-m", "app.init_db"],
                cwd=BACKEND_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr or second.stdout)

    def test_token_version_and_legacy_avatar_are_migrated_idempotently(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "legacy.db"
            with closing(sqlite3.connect(database)) as connection:
                connection.execute(
                    """
                    CREATE TABLE user (
                        id INTEGER PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        nickname VARCHAR(50),
                        avatar_url VARCHAR(255),
                        is_admin BOOLEAN DEFAULT 0,
                        is_feeder BOOLEAN DEFAULT 0,
                        created_at DATETIME
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO user (username, password_hash, avatar_url) "
                    "VALUES (?, ?, ?)",
                    ("legacy", "not-a-real-hash", "presets/cat.png"),
                )
                connection.commit()

            environment = os.environ.copy()
            environment.update(
                {
                    "PYTHONUTF8": "1",
                    "JWT_SECRET": "test",
                    "DATABASE_URL": f"sqlite+aiosqlite:///{database.as_posix()}",
                }
            )

            for _ in range(2):
                result = subprocess.run(
                    [sys.executable, "-m", "app.migrate"],
                    cwd=BACKEND_ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

            with closing(sqlite3.connect(database)) as connection:
                columns = {
                    row[1]: row for row in connection.execute("PRAGMA table_info(user)")
                }
                avatar_url = connection.execute(
                    "SELECT avatar_url FROM user WHERE username = 'legacy'"
                ).fetchone()[0]

            self.assertIn("token_version", columns)
            self.assertEqual(columns["token_version"][2].upper(), "INTEGER")
            self.assertEqual(columns["token_version"][3], 1)
            self.assertEqual(columns["token_version"][4], "0")
            self.assertEqual(avatar_url, "/avatars/cat.png")


if __name__ == "__main__":
    unittest.main()
