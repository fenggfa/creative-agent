#!/usr/bin/env python
"""
Harness 环境检查 - 环境自愈

用法:
    uv run python scripts/check_env.py
"""

import subprocess
import sys
from pathlib import Path


def check_python() -> bool:
    """检查 Python 版本。"""
    result = subprocess.run(
        ["python", "--version"],
        capture_output=True,
        text=True,
    )
    version = result.stdout.strip()
    print(f"Python: {version}")

    if "3.10" in version or "3.11" in version or "3.12" in version:
        print("✅ Python 版本符合要求")
        return True

    print("❌ 需要 Python 3.10+")
    return False


def check_uv() -> bool:
    """检查 uv 是否安装。"""
    result = subprocess.run(
        ["uv", "--version"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"✅ uv: {result.stdout.strip()}")
        return True

    print("❌ uv 未安装，请运行: pip install uv")
    return False


def check_dependencies() -> bool:
    """检查依赖是否安装。"""
    result = subprocess.run(
        ["uv", "sync", "--dry-run"],
        cwd=Path(__file__).parent.parent,
    )

    if result.returncode == 0:
        print("✅ 依赖已安装")
        return True

    print("⚠️ 依赖需要安装，请运行: uv sync")
    return False


def check_env_file() -> bool:
    """检查 .env 文件。"""
    env_path = Path(__file__).parent.parent / ".env"

    if env_path.exists():
        print("✅ .env 文件存在")
        return True

    print("⚠️ .env 文件不存在，请创建并配置 API Key")
    return False


def main() -> int:
    print("🔍 Harness 环境检查")
    print("=" * 50)

    checks = [
        check_python,
        check_uv,
        check_dependencies,
        check_env_file,
    ]

    results = [check() for check in checks]

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 环境检查通过 ({passed}/{total})")
        return 0
    else:
        print(f"⚠️ 环境检查未完全通过 ({passed}/{total})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
