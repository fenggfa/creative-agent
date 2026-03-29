#!/usr/bin/env python
"""
Harness 工具集 - 自动化执行器

用法:
    uv run python scripts/verify.py              # 完整验证
    uv run python scripts/verify.py --quick      # 快速检查
    uv run python scripts/verify.py --harness    # Harness 运行时验证
    uv run python scripts/verify.py --entropy    # 熵检查
    uv run python scripts/verify.py --docs       # 文档健康检查
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


def verify_harness() -> bool:
    """运行 Harness 运行时验证。"""
    import asyncio

    from src.harness import HarnessVerifier

    print("\n" + "=" * 50)
    print("🔍 Harness 运行时验证")
    print("=" * 50)

    verifier = HarnessVerifier()
    results = asyncio.run(verifier.run_all_checks())
    verifier.print_report()

    return all(r.status.value == "passed" for r in results)


def verify_entropy() -> bool:
    """运行熵检查。"""
    from src.harness import run_entropy_check

    print("\n" + "=" * 50)
    print("🔍 熵检查 (AI 垃圾回收)")
    print("=" * 50)

    result = run_entropy_check()

    print(f"\n熵分数: {result['entropy_score']:.2f}")
    print(f"扫描文件: {result['total_files']}")
    print(f"问题总数: {result['total_issues']}")

    print("\n问题分布:")
    for severity, count in result["issues_by_severity"].items():
        if count > 0:
            print(f"  - {severity}: {count}")

    # 熵分数 < 0.5 为健康
    is_healthy = result["entropy_score"] < 0.5
    if is_healthy:
        print("\n✅ 熵检查通过 (熵分数 < 0.5)")
    else:
        print("\n⚠️ 熵分数过高，建议清理")

    return is_healthy


def verify_docs() -> bool:
    """运行文档健康检查。"""
    from src.harness import run_doc_lint

    print("\n" + "=" * 50)
    print("🔍 文档健康检查")
    print("=" * 50)

    result = run_doc_lint()

    print(f"\n文档健康分数: {result['health_score']:.2%}")
    print(f"文档总数: {result['total_docs']}")
    print(f"健康文档: {result['healthy_docs']}")

    if result["issues_by_type"]:
        print("\n问题分布:")
        for issue_type, count in result["issues_by_type"].items():
            print(f"  - {issue_type}: {count}")

    if result["suggestions"]:
        print("\n改进建议:")
        for suggestion in result["suggestions"]:
            print(f"  {suggestion}")

    # 健康分数 >= 0.8 为通过
    is_healthy = result["health_score"] >= 0.8
    if is_healthy:
        print("\n✅ 文档健康检查通过 (健康分数 >= 80%)")
    else:
        print("\n⚠️ 文档健康分数过低，需要改进")

    return is_healthy


def main() -> int:
    """主入口。"""
    import argparse

    parser = argparse.ArgumentParser(description="Harness 验证工具")
    parser.add_argument("--quick", action="store_true", help="快速检查（跳过测试）")
    parser.add_argument("--harness", action="store_true", help="运行 Harness 运行时验证")
    parser.add_argument("--entropy", action="store_true", help="运行熵检查")
    parser.add_argument("--docs", action="store_true", help="运行文档健康检查")
    args = parser.parse_args()

    print("🚀 Harness Engineering 验证工具")
    print("=" * 50)

    # 处理专项检查
    if args.harness:
        success = verify_harness()
    elif args.entropy:
        success = verify_entropy()
    elif args.docs:
        success = verify_docs()
    elif args.quick:
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
