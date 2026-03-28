#!/usr/bin/env python
"""
Harness 回滚工具 - 执行器动作

用法:
    uv run python scripts/rollback.py <commit_hash>
    uv run python scripts/rollback.py --last
"""

import subprocess
import sys
from pathlib import Path


def get_last_commit() -> str:
    """获取上一个 commit hash。"""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD~1"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    return result.stdout.strip()


def rollback(commit_hash: str) -> bool:
    """回滚到指定 commit。"""
    print(f"🔄 回滚到 commit: {commit_hash[:8]}")

    result = subprocess.run(
        ["git", "revert", "--no-commit", commit_hash],
        cwd=Path(__file__).parent.parent,
    )

    if result.returncode != 0:
        print(f"❌ 回滚失败")
        return False

    print("✅ 回滚成功（未自动提交）")
    print("请检查变更后执行: git commit -m 'revert: ...'")
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Harness 回滚工具")
    parser.add_argument("commit", nargs="?", help="目标 commit hash")
    parser.add_argument("--last", action="store_true", help="回滚上一个 commit")
    args = parser.parse_args()

    if args.last:
        commit_hash = get_last_commit()
    elif args.commit:
        commit_hash = args.commit
    else:
        print("❌ 请指定 commit 或使用 --last")
        return 1

    return 0 if rollback(commit_hash) else 1


if __name__ == "__main__":
    sys.exit(main())
