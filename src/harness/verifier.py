"""Harness 验证器 - 实现自动化验证循环。"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    """检查状态。"""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class CheckResult:
    """检查结果。"""

    name: str
    status: CheckStatus
    message: str
    details: dict[str, Any] | None = None


class HarnessVerifier:
    """Harness 验证器 - 执行所有验证检查。"""

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.results: list[CheckResult] = []

    async def run_command(
        self,
        command: list[str],
        timeout: float = 60.0,
    ) -> tuple[int, str, str]:
        """运行命令并返回结果。"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
            return (
                process.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        except asyncio.TimeoutError:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    async def verify_types(self) -> CheckResult:
        """验证类型检查。"""
        returncode, stdout, stderr = await self.run_command(
            ["uv", "run", "mypy", "src/", "--ignore-missing-imports"],
            timeout=60.0,
        )

        if returncode == 0:
            return CheckResult(
                name="类型检查",
                status=CheckStatus.PASSED,
                message="类型检查通过",
                details={"output": stdout},
            )
        else:
            return CheckResult(
                name="类型检查",
                status=CheckStatus.FAILED,
                message="类型检查失败",
                details={"errors": stderr, "output": stdout},
            )

    async def verify_lint(self) -> CheckResult:
        """验证代码风格。"""
        returncode, stdout, stderr = await self.run_command(
            ["uv", "run", "ruff", "check", "src/"],
            timeout=30.0,
        )

        if returncode == 0:
            return CheckResult(
                name="代码风格",
                status=CheckStatus.PASSED,
                message="代码风格检查通过",
                details={"output": stdout},
            )
        else:
            return CheckResult(
                name="代码风格",
                status=CheckStatus.FAILED,
                message="代码风格检查失败",
                details={"errors": stdout or stderr},
            )

    async def verify_tests(self) -> CheckResult:
        """验证测试。"""
        returncode, stdout, stderr = await self.run_command(
            ["uv", "run", "pytest", "tests/", "-v", "--tb=short"],
            timeout=120.0,
        )

        if returncode == 0:
            # 解析测试结果
            passed = stdout.count("PASSED")
            return CheckResult(
                name="单元测试",
                status=CheckStatus.PASSED,
                message=f"测试通过 ({passed} tests)",
                details={"output": stdout, "passed": passed},
            )
        else:
            failed = stdout.count("FAILED")
            return CheckResult(
                name="单元测试",
                status=CheckStatus.FAILED,
                message=f"测试失败 ({failed} failures)",
                details={"errors": stdout, "failed": failed},
            )

    async def verify_constraints(self) -> CheckResult:
        """验证约束模块。"""
        try:
            from src.constraints.rules import ConstraintChecker

            checker = ConstraintChecker()
            # 测试约束检查器是否正常工作
            violations = checker.run_all_checks("测试内容，用于验证约束系统正常工作。")

            return CheckResult(
                name="约束系统",
                status=CheckStatus.PASSED,
                message="约束系统正常运行",
                details={"violations_count": len(violations)},
            )
        except ImportError as e:
            return CheckResult(
                name="约束系统",
                status=CheckStatus.ERROR,
                message=f"约束模块导入失败: {e}",
            )
        except Exception as e:
            return CheckResult(
                name="约束系统",
                status=CheckStatus.ERROR,
                message=f"约束系统错误: {e}",
            )

    async def verify_feedback(self) -> CheckResult:
        """验证反馈模块。"""
        try:
            from src.feedback.evaluator import EvaluationCriteria

            criteria = EvaluationCriteria()
            # 验证评估标准是否正确配置
            total_weight = sum(criteria.weights.values())

            if abs(total_weight - 1.0) < 0.01:
                return CheckResult(
                    name="反馈系统",
                    status=CheckStatus.PASSED,
                    message="反馈系统配置正确",
                    details={"total_weight": total_weight},
                )
            else:
                return CheckResult(
                    name="反馈系统",
                    status=CheckStatus.FAILED,
                    message=f"评估权重配置错误: 总和为 {total_weight}",
                )
        except ImportError as e:
            return CheckResult(
                name="反馈系统",
                status=CheckStatus.ERROR,
                message=f"反馈模块导入失败: {e}",
            )
        except Exception as e:
            return CheckResult(
                name="反馈系统",
                status=CheckStatus.ERROR,
                message=f"反馈系统错误: {e}",
            )

    async def verify_config(self) -> CheckResult:
        """验证配置。"""
        try:
            from src.config import settings

            # 检查必需配置
            required = ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]
            missing = [k for k in required if not getattr(settings, k, None)]

            if missing:
                return CheckResult(
                    name="配置检查",
                    status=CheckStatus.FAILED,
                    message=f"缺少必需配置: {', '.join(missing)}",
                )

            return CheckResult(
                name="配置检查",
                status=CheckStatus.PASSED,
                message="配置完整",
                details={"model": settings.LLM_MODEL},
            )
        except Exception as e:
            return CheckResult(
                name="配置检查",
                status=CheckStatus.ERROR,
                message=f"配置验证错误: {e}",
            )

    async def run_all_checks(self) -> list[CheckResult]:
        """运行所有验证检查。"""
        self.results = []

        # 并行运行独立检查
        tasks = [
            self.verify_types(),
            self.verify_lint(),
            self.verify_tests(),
            self.verify_constraints(),
            self.verify_feedback(),
            self.verify_config(),
        ]

        self.results = await asyncio.gather(*tasks)
        return self.results

    def get_summary(self) -> dict[str, Any]:
        """生成检查摘要。"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == CheckStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == CheckStatus.FAILED)
        errors = sum(1 for r in self.results if r.status == CheckStatus.ERROR)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "success_rate": passed / total if total > 0 else 0,
            "all_passed": failed == 0 and errors == 0,
        }

    def print_report(self) -> None:
        """打印检查报告。"""
        print("\n" + "=" * 60)
        print("Harness Verification Report")
        print("=" * 60)

        for result in self.results:
            status_icon = {
                CheckStatus.PASSED: "✅",
                CheckStatus.FAILED: "❌",
                CheckStatus.SKIPPED: "⏭️",
                CheckStatus.ERROR: "⚠️",
            }.get(result.status, "❓")

            print(f"\n{status_icon} {result.name}: {result.message}")

            if result.details and result.status != CheckStatus.PASSED:
                for key, value in result.details.items():
                    if key == "errors" and value:
                        print(f"   └─ {key}: {value[:200]}...")

        summary = self.get_summary()
        print("\n" + "-" * 60)
        print(f"Summary: {summary['passed']}/{summary['total']} passed")
        print(f"Success Rate: {summary['success_rate']:.1%}")
        print("=" * 60 + "\n")


# 便捷函数
async def run_all_checks() -> list[CheckResult]:
    """运行所有验证检查。"""
    verifier = HarnessVerifier()
    return await verifier.run_all_checks()


async def verify_types() -> CheckResult:
    """仅验证类型。"""
    verifier = HarnessVerifier()
    return await verifier.verify_types()


async def verify_tests() -> CheckResult:
    """仅验证测试。"""
    verifier = HarnessVerifier()
    return await verifier.verify_tests()


async def verify_constraints() -> CheckResult:
    """仅验证约束。"""
    verifier = HarnessVerifier()
    return await verifier.verify_constraints()


if __name__ == "__main__":
    # 命令行入口
    verifier = HarnessVerifier()
    asyncio.run(verifier.run_all_checks())
    verifier.print_report()
