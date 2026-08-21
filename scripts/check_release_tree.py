#!/usr/bin/env python3
"""检查即将发布的 Git 树与前端构建产物是否包含本地或敏感文件。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath


FORBIDDEN_DIRECTORIES = {
    ".claude",
    ".local",
    ".pytest_cache",
    ".workbuddy",
    ".worktrees",
    ".zcode",
    "__pycache__",
    "dev-dist",
    "dist",
    "node_modules",
    "venv",
}

# 这些文件已从 v1.0 发布树移除，防止调试、预览和旧账号逻辑回流。
REMOVED_RELEASE_PATHS = {
    "agents.md",
    "claude.md",
    "project_status.md",
    "backend/check_leftover.py",
    "backend/cleanup_leftover.py",
    "backend/debug_repro.py",
    "backend/gen_preset_avatars.py",
    "backend/preset_preview.png",
    "frontend/readme.md",
    "frontend/src/assets/hero.png",
    "frontend/src/assets/vite.svg",
    "frontend/src/assets/vue.svg",
    "frontend/src/components/helloworld.vue",
    "frontend/src/utils/accounts.ts",
    "prompt.md",
    "prompt_v2.md",
    "start-mobile-debug.bat",
    "start-mobile-debug.sh",
    "todo.md",
    "开发日志/ui重设计_20260819_152017.md",
    "开发日志/测试结果.md",
    "开发日志/闭环测试摘要.md",
    "开发日志/问题记录.md",
    "开发日志_ui重设计_20260819_152017.md",
    "移动端调试指南.md",
    "菜单模板.md",
}


def _normalize(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./").strip("/")


def path_violation(path: str) -> str | None:
    """返回路径违反的发布规则；允许路径返回 None。"""
    normalized = _normalize(path)
    lowered = normalized.casefold()
    parts = tuple(part.casefold() for part in PurePosixPath(normalized).parts)
    filename = parts[-1] if parts else ""

    if lowered in REMOVED_RELEASE_PATHS:
        return "已从 v1.0 发布树移除的调试、预览或内部文件"
    if any(part in FORBIDDEN_DIRECTORIES for part in parts):
        return "本地工具目录、依赖目录或构建产物目录"
    if len(parts) > 2 and parts[:2] == ("backend", "uploads"):
        return "backend/uploads 运行时上传内容"
    if filename == ".env.example":
        return None
    if filename == ".env" or filename.startswith(".env."):
        return "环境变量或密钥文件（仅允许 .env.example）"
    if filename.endswith(".pem"):
        return "PEM 密钥文件"
    if filename.endswith(".db") or ".db-" in filename:
        return "数据库或数据库旁路文件"
    if ".sqlite" in filename:
        return "SQLite 数据库文件"
    return None


def _run_git(root: Path, arguments: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *arguments],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "Git 命令执行失败")
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def list_worktree_paths(root: Path) -> list[str]:
    """列出发布工作树：索引文件加非忽略未跟踪文件，并排除已删除项。"""
    paths = _run_git(
        root,
        ["ls-files", "-z", "--cached", "--others", "--exclude-standard"],
    )
    present = []
    for path in paths:
        candidate = root / Path(path)
        if candidate.is_file() or candidate.is_symlink():
            present.append(_normalize(path))
    return sorted(set(present), key=str.casefold)


def list_tree_paths(root: Path, mode: str) -> list[str]:
    if mode == "worktree":
        return list_worktree_paths(root)
    if mode == "index":
        arguments = ["ls-files", "-z", "--cached"]
    elif mode == "head":
        arguments = ["ls-tree", "-r", "--name-only", "-z", "HEAD"]
    else:
        raise ValueError(f"未知扫描模式：{mode}")
    return sorted({_normalize(path) for path in _run_git(root, arguments)}, key=str.casefold)


def check_dist(dist_dir: Path) -> list[str]:
    """检查实际构建目录，不扫描源码中的开发代理配置。"""
    if not dist_dir.is_dir():
        return [f"{dist_dir.as_posix()}：构建目录不存在"]

    marker = b"localhost:8000"
    violations = []
    for path in sorted(dist_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            if marker in path.read_bytes():
                relative = path.relative_to(dist_dir).as_posix()
                violations.append(f"frontend/dist/{relative}：包含 localhost:8000")
        except OSError as error:
            violations.append(f"{path.as_posix()}：无法读取（{error}）")
    return violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查 MealMate 即将发布的文件树与前端构建产物。"
    )
    parser.add_argument(
        "--mode",
        choices=("worktree", "index", "head"),
        default="worktree",
        help="扫描来源；默认 worktree，包含未 git add 的非忽略文件。",
    )
    parser.add_argument(
        "--check-dist",
        action="store_true",
        help="额外检查实际 frontend/dist 是否存在 localhost:8000。",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="仓库根目录，默认根据脚本位置确定。",
    )
    return parser


def configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output()
    args = build_parser().parse_args(argv)
    root = args.root.resolve()

    try:
        paths = list_tree_paths(root, args.mode)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"发布检查失败：{error}", file=sys.stderr)
        return 1

    violations = []
    for path in paths:
        reason = path_violation(path)
        if reason:
            violations.append(f"{path}：{reason}")

    if args.check_dist:
        violations.extend(check_dist(root / "frontend" / "dist"))

    if violations:
        print(f"发布检查未通过（{len(violations)} 项）：")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    suffix = "，已检查 frontend/dist" if args.check_dist else ""
    print(f"发布检查通过：{args.mode} 模式共扫描 {len(paths)} 个路径{suffix}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
