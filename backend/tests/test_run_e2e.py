import unittest
from pathlib import Path
from unittest.mock import patch

import run_e2e


class TemporaryDirectoryCleanupTests(unittest.TestCase):
    def test_windows_file_lock_is_retried(self):
        cleanup = getattr(run_e2e, "remove_temp_directory", None)
        self.assertIsNotNone(cleanup, "缺少临时目录清理重试函数")

        with (
            patch(
                "run_e2e.shutil.rmtree",
                side_effect=[PermissionError("locked"), None],
            ) as remove,
            patch.object(Path, "exists", return_value=True),
            patch("run_e2e.time.sleep") as wait,
        ):
            cleanup(Path("temporary-e2e"), attempts=2, delay=0.01)

        self.assertEqual(remove.call_count, 2)
        wait.assert_called_once_with(0.01)


if __name__ == "__main__":
    unittest.main()
