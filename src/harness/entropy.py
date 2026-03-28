"""熵管理模块 - AI 时代的垃圾回收（GC）。

Harness Engineering 核心要求：
- AI Slop 临床表现：过时文档、坏模式扩散、表面完成
- 用"黄金原则"与后台清理任务持续纠偏，防止坏模式扩散
- 扫描 → 重构 → 合并的持续清理流程
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class IssueSeverity(str, Enum):
    """问题严重程度。"""

    CRITICAL = "critical"  # 必须立即修复
    HIGH = "high"  # 高优先级
    MEDIUM = "medium"  # 中等优先级
    LOW = "low"  # 低优先级
    INFO = "info"  # 信息提示


@dataclass
class EntropyIssue:
    """熵问题。"""

    file_path: str
    line_number: int
    issue_type: str
    severity: IssueSeverity
    message: str
    suggestion: str
    auto_fixable: bool = False


@dataclass
class EntropyReport:
    """熵报告。"""

    timestamp: str
    total_files: int
    total_issues: int
    issues: list[EntropyIssue] = field(default_factory=list)

    @property
    def entropy_score(self) -> float:
        """计算熵分数（0-1，越高越混乱）。"""
        if self.total_files == 0:
            return 0.0

        # 根据问题数量和严重程度计算
        severity_weights = {
            IssueSeverity.CRITICAL: 1.0,
            IssueSeverity.HIGH: 0.5,
            IssueSeverity.MEDIUM: 0.2,
            IssueSeverity.LOW: 0.1,
            IssueSeverity.INFO: 0.05,
        }

        total_weight = sum(
            severity_weights.get(issue.severity, 0.1)
            for issue in self.issues
        )

        # 归一化到 0-1
        return min(1.0, total_weight / self.total_files)


# 黄金原则 Golden Principles
GOLDEN_PRINCIPLES = {
    "parse_not_validate": {
        "name": "Parse, don't validate",
        "description": "在边界处强制转换数据形状，拒绝隐式信任大模型的输出结构",
        "patterns": [
            r"if\s+\w+\s+is\s+None:\s*return",  # 过早返回
            r"try:\s*\.\.\.\s*except:\s*pass",  # 吞掉异常
        ],
    },
    "dry": {
        "name": "DRY (Don't Repeat Yourself)",
        "description": "严禁生成重复的 Helper 函数，强制复用共享工具链",
        "patterns": [
            r"def\s+(\w+)\s*\([^)]*\):[\s\S]*?def\s+\1\s*\(",  # 重复函数名
        ],
    },
    "explicit_over_implicit": {
        "name": "Explicit over Implicit",
        "description": "所有约定必须显式编码，压缩 AI 的幻觉空间",
        "patterns": [
            r"#\s*TODO",  # 未完成的 TODO
            r"#\s*HACK",  # 临时方案
            r"#\s*XXX",  # 问题标记
        ],
    },
}

# AI 典型表达模式（需要检测并清理）
AI_SLOP_PATTERNS = [
    r"首先，让我们",
    r"总之，",
    r"综上所述，",
    r"在当今社会",
    r"众所周知",
    r"值得注意的是",
    r"有趣的是",
    r"让我们来看看",
]


class EntropyScanner:
    """熵扫描器 - 检测 AI 垃圾代码。"""

    def __init__(self, src_dir: str = "src"):
        self.src_dir = Path(src_dir)

    def scan(self) -> EntropyReport:
        """执行全量扫描。"""
        from datetime import datetime

        issues: list[EntropyIssue] = []
        py_files = list(self.src_dir.rglob("*.py"))
        total_files = len(py_files)

        for file_path in py_files:
            issues.extend(self._scan_file(file_path))

        return EntropyReport(
            timestamp=datetime.now().isoformat(),
            total_files=total_files,
            total_issues=len(issues),
            issues=issues,
        )

    def _scan_file(self, file_path: Path) -> list[EntropyIssue]:
        """扫描单个文件。"""
        issues: list[EntropyIssue] = []
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # 1. 检查黄金原则违规
        issues.extend(self._check_golden_principles(file_path, content, lines))

        # 2. 检查 AI Slop
        issues.extend(self._check_ai_slop(file_path, content, lines))

        # 3. 检查代码质量
        issues.extend(self._check_code_quality(file_path, content, lines))

        # 4. 检查重复代码
        issues.extend(self._check_duplication(file_path, content, lines))

        return issues

    def _check_golden_principles(
        self,
        file_path: Path,
        _content: str,
        lines: list[str],
    ) -> list[EntropyIssue]:
        """检查黄金原则违规。"""
        issues: list[EntropyIssue] = []

        for principle_id, principle in GOLDEN_PRINCIPLES.items():
            for pattern in principle.get("patterns", []):
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        issues.append(EntropyIssue(
                            file_path=str(file_path),
                            line_number=i,
                            issue_type=f"golden_principle.{principle_id}",
                            severity=IssueSeverity.MEDIUM,
                            message=f"违反黄金原则: {principle['name']}",
                            suggestion=str(principle["description"]),
                            auto_fixable=False,
                        ))

        return issues

    def _check_ai_slop(
        self,
        file_path: Path,
        _content: str,
        lines: list[str],
    ) -> list[EntropyIssue]:
        """检查 AI 典型表达模式。"""
        issues: list[EntropyIssue] = []

        for i, line in enumerate(lines, 1):
            for pattern in AI_SLOP_PATTERNS:
                if re.search(pattern, line):
                    issues.append(EntropyIssue(
                        file_path=str(file_path),
                        line_number=i,
                        issue_type="ai_slop",
                        severity=IssueSeverity.LOW,
                        message=f"检测到 AI 典型表达: {pattern}",
                        suggestion="使用更自然的表达方式",
                        auto_fixable=False,
                    ))

        return issues

    def _check_code_quality(
        self,
        file_path: Path,
        _content: str,
        lines: list[str],
    ) -> list[EntropyIssue]:
        """检查代码质量。"""
        issues: list[EntropyIssue] = []

        # 1. 检查文件长度
        if len(lines) > 500:
            issues.append(EntropyIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type="file_too_long",
                severity=IssueSeverity.LOW,
                message=f"文件过长: {len(lines)} 行",
                suggestion="考虑拆分为多个模块",
                auto_fixable=False,
            ))

        # 2. 检查空行过多
        empty_line_count = sum(1 for line in lines if not line.strip())
        if empty_line_count > len(lines) * 0.3:
            issues.append(EntropyIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type="too_many_empty_lines",
                severity=IssueSeverity.INFO,
                message=f"空行过多: {empty_line_count} 行",
                suggestion="减少不必要的空行",
                auto_fixable=True,
            ))

        # 3. 检查 TODO/HACK/XXX
        for i, line in enumerate(lines, 1):
            if re.search(r"#\s*(TODO|HACK|XXX|FIXME)", line, re.IGNORECASE):
                issues.append(EntropyIssue(
                    file_path=str(file_path),
                    line_number=i,
                    issue_type="technical_debt_marker",
                    severity=IssueSeverity.INFO,
                    message=f"技术债标记: {line.strip()}",
                    suggestion="处理或记录到 issue tracker",
                    auto_fixable=False,
                ))

        return issues

    def _check_duplication(
        self,
        file_path: Path,
        _content: str,
        lines: list[str],
    ) -> list[EntropyIssue]:
        """检查重复代码。"""
        issues: list[EntropyIssue] = []

        # 简单的重复行检测
        line_counts: dict[str, int] = {}
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                line_counts[stripped] = line_counts.get(stripped, 0) + 1

        for line, count in line_counts.items():
            if count > 3 and len(line) > 20:  # 重复超过 3 次且长度 > 20
                issues.append(EntropyIssue(
                    file_path=str(file_path),
                    line_number=lines.index(line) + 1 if line in lines else 1,
                    issue_type="code_duplication",
                    severity=IssueSeverity.LOW,
                    message=f"代码重复: \"{line[:50]}...\" 出现 {count} 次",
                    suggestion="考虑提取为公共函数",
                    auto_fixable=False,
                ))

        return issues


class EntropyCleaner:
    """熵清理器 - 自动清理 AI 垃圾。"""

    def __init__(self, src_dir: str = "src"):
        self.src_dir = Path(src_dir)
        self.scanner = EntropyScanner(src_dir)

    def clean(self, auto_fix: bool = False) -> dict[str, Any]:
        """执行清理。

        Args:
            auto_fix: 是否自动修复可修复的问题

        Returns:
            清理报告
        """
        report = self.scanner.scan()

        fixed = []
        if auto_fix:
            for issue in report.issues:
                if issue.auto_fixable and self._fix_issue(issue):
                    fixed.append(issue)

        return {
            "entropy_score": report.entropy_score,
            "total_issues": report.total_issues,
            "fixed_count": len(fixed),
            "remaining_issues": report.total_issues - len(fixed),
            "details": [
                {
                    "file": issue.file_path,
                    "line": issue.line_number,
                    "type": issue.issue_type,
                    "severity": issue.severity.value,
                    "message": issue.message,
                }
                for issue in report.issues
                if issue not in fixed
            ],
        }

    def _fix_issue(self, issue: EntropyIssue) -> bool:
        """修复单个问题。"""
        if issue.issue_type == "too_many_empty_lines":
            return self._remove_excess_empty_lines(issue)

        return False

    def _remove_excess_empty_lines(self, issue: EntropyIssue) -> bool:
        """移除多余空行。"""
        try:
            file_path = Path(issue.file_path)
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # 移除连续超过 2 个的空行
            new_lines: list[str] = []
            empty_count = 0

            for line in lines:
                if not line.strip():
                    empty_count += 1
                    if empty_count <= 2:
                        new_lines.append(line)
                else:
                    empty_count = 0
                    new_lines.append(line)

            file_path.write_text("\n".join(new_lines), encoding="utf-8")
            return True

        except Exception:
            return False


def run_entropy_check() -> dict[str, Any]:
    """运行熵检查。"""
    scanner = EntropyScanner()
    report = scanner.scan()

    return {
        "entropy_score": report.entropy_score,
        "total_files": report.total_files,
        "total_issues": report.total_issues,
        "issues_by_severity": {
            severity.value: sum(
                1 for issue in report.issues
                if issue.severity == severity
            )
            for severity in IssueSeverity
        },
    }
