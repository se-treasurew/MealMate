"""在临时数据库、上传目录和随机端口中运行完整闭环测试。"""
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent


def find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def wait_for_health(base_url: str, process: subprocess.Popen, timeout: int = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"测试服务提前退出，退出码 {process.returncode}")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError("等待测试服务启动超时")


def remove_temp_directory(
    path: Path,
    *,
    attempts: int = 10,
    delay: float = 0.2,
) -> None:
    """处理 Windows 进程退出后文件句柄短暂未释放的情况。"""
    for attempt in range(attempts):
        if not path.exists():
            return
        try:
            shutil.rmtree(path)
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)


def main() -> int:
    admin_password = os.environ.get("E2E_ADMIN_PASSWORD") or secrets.token_urlsafe(18)
    port = find_available_port()
    base_url = f"http://127.0.0.1:{port}"

    temp_path = Path(tempfile.mkdtemp(prefix="mealmate-e2e-"))
    try:
        upload_dir = temp_path / "uploads"
        database_path = temp_path / "mealmate.db"
        env = os.environ.copy()
        env.update({
            "PYTHONUTF8": "1",
            "DATABASE_URL": f"sqlite+aiosqlite:///{database_path.as_posix()}",
            "UPLOAD_DIR": str(upload_dir),
            "JWT_SECRET": secrets.token_urlsafe(48),
            "ADMIN_INITIAL_PASSWORD": admin_password,
            "E2E_ADMIN_PASSWORD": admin_password,
            "E2E_BASE": base_url,
            "E2E_UPLOAD_DIR": str(upload_dir),
        })

        subprocess.run(
            [sys.executable, "-m", "app.init_db"],
            cwd=BACKEND_DIR,
            env=env,
            check=True,
        )
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
                "--no-access-log",
            ],
            cwd=BACKEND_DIR,
            env=env,
        )
        try:
            wait_for_health(base_url, server)
            result = subprocess.run(
                [sys.executable, "e2e_test.py"],
                cwd=BACKEND_DIR,
                env=env,
            )
            return result.returncode
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
    finally:
        remove_temp_directory(temp_path)


if __name__ == "__main__":
    raise SystemExit(main())
