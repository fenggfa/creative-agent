#!/usr/bin/env python
"""
Harness 工具集 - 自动化执行器

用法:
    uv run python scripts/verify.py      # 完整验证
    uv run python scripts/verify.py --quick  # 快速检查
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """执行命令并返回是否成功。"""
    print(f"\n{'='*50}")
    print(f"🔍 {description}")
    print(f"{'='*50}")
    print(f"执行: {cmd}\n")

    result = subprocess.run(cmd, shell=True, cwd=Path(__file__).parent.parent)

    if result.returncode != 0:
        print(f"\n❌ {description} 失败")
        return False

    print(f"\n✅ {description} 通过")
    return True


def verify_full() -> bool:
    """完整验证流程。"""
    steps = [
        ("uv run ruff check src/", "Ruff Lint"),
        ("uv run mypy src/", "MyPy 类型检查"),
        ("uv run pytest tests/ -v", "Pytest 测试"),
    ]

    all_passed = True
    for cmd, desc in steps:
        if not run_command(cmd, desc):
            all_passed = False

    return all_passed


def verify_quick() -> bool:
    """快速检查（仅 lint 和类型检查）。"""
    steps = [
        ("uv run ruff check src/", "Ruff Lint"),
        ("uv run mypy src/", "MyPy 类型检查"),
    ]

    all_passed = True
    for cmd, desc in steps:
        if not run_command(cmd, desc):
            all_passed = False

    return all_passed


def main() -> int:
    """主入口。"""
    import argparse

    parser = argparse.ArgumentParser(description="Harness 验证工具")
    parser.add_argument("--quick", action="store_true", help="快速检查（跳过测试）")
    args = parser.parse_args()

    print("🚀 Harness Engineering 验证工具")
    print("=" * 50)

    if args.quick:
        success = verify_quick()
    else:
        success = verify_full()

    print("\n" + "=" * 50)
    if success:
        print("🎉 所有检查通过!")
        return 0
    else:
        print("💥 存在检查失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
