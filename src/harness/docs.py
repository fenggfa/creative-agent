"""文档治理模块 - 告别"死文档"。

Harness Engineering 核心要求：
- 文档 Linter：强制格式规约
- 链接检查器：阻断死链蔓延
- 新鲜度监控：追踪生命周期
- Doc-Gardening Agent：智能文档园丁
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class DocIssueType(str, Enum):
    """文档问题类型。"""

    BROKEN_LINK = "broken_link"  # 死链
    MISSING_FRONTMATTER = "missing_frontmatter"  # 缺少元数据
    OUTDATED = "outdated"  # 过时文档
    FORMAT_ERROR = "format_error"  # 格式错误
    MISSING_SECTIONS = "missing_sections"  # 缺少必要章节


@dataclass
class DocIssue:
    """文档问题。"""

    file_path: str
    issue_type: DocIssueType
    message: str
    severity: str  # critical, high, medium, low
    suggestion: str = ""
    line_number: int = 0


@dataclass
class DocHealthReport:
    """文档健康报告。"""

    total_docs: int
    healthy_docs: int
    issues: list[DocIssue] = field(default_factory=list)

    @property
    def health_score(self) -> float:
        """计算文档健康分数（0-1）。"""
        if self.total_docs == 0:
            return 1.0
        return self.healthy_docs / self.total_docs


# 文档新鲜度阈值（天）
FRESHNESS_THRESHOLD_DAYS = 30

# 必须包含的章节（针对特定文档）
REQUIRED_SECTIONS = {
    "AGENTS.md": ["核心原则", "架构地图", "约束边界"],
    "CLAUDE.md": ["执行原则"],
    "README.md": ["安装", "使用"],
}


class DocLinter:
    """文档 Linter - 强制格式规约。"""

    def __init__(self, docs_dir: str = "."):
        self.docs_dir = Path(docs_dir)

    def lint(self) -> DocHealthReport:
        """执行文档 Lint 检查。"""
        issues: list[DocIssue] = []
        md_files = list(self.docs_dir.rglob("*.md"))

        # 排除 node_modules、.git 等
        md_files = [
            f for f in md_files
            if not any(part.startswith(".") for part in f.parts)
            and "node_modules" not in str(f)
        ]

        total_docs = len(md_files)
        healthy_docs = total_docs

        for file_path in md_files:
            file_issues = self._lint_file(file_path)
            if file_issues:
                issues.extend(file_issues)
                healthy_docs -= 1

        return DocHealthReport(
            total_docs=total_docs,
            healthy_docs=healthy_docs,
            issues=issues,
        )

    def _lint_file(self, file_path: Path) -> list[DocIssue]:
        """Lint 单个文档。"""
        issues: list[DocIssue] = []
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # 1. 检查格式问题
        issues.extend(self._check_format(file_path, content, lines))

        # 2. 检查链接
        issues.extend(self._check_links(file_path, content))

        # 3. 检查必要章节
        issues.extend(self._check_sections(file_path, content))

        # 4. 检查新鲜度
        issues.extend(self._check_freshness(file_path))

        return issues

    def _check_format(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
    ) -> list[DocIssue]:
        """检查格式问题。"""
        issues: list[DocIssue] = []

        # 1. 检查标题层级（不允许跳级）
        prev_level = 0
        for i, line in enumerate(lines, 1):
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                if level > prev_level + 1 and prev_level > 0:
                    issues.append(DocIssue(
                        file_path=str(file_path),
                        issue_type=DocIssueType.FORMAT_ERROR,
                        message=f"标题层级跳跃: H{prev_level} → H{level}",
                        severity="low",
                        suggestion="保持标题层级连续",
                        line_number=i,
                    ))
                prev_level = level

        # 2. 检查代码块是否闭合
        code_block_count = content.count("```")
        if code_block_count % 2 != 0:
            issues.append(DocIssue(
                file_path=str(file_path),
                issue_type=DocIssueType.FORMAT_ERROR,
                message="代码块未正确闭合",
                severity="high",
                suggestion="确保所有 ``` 都成对出现",
            ))

        # 3. 检查列表格式
        for i, line in enumerate(lines, 1):
            # 检查列表项后是否有内容
            if re.match(r"^\s*[-*+]\s*$", line):
                issues.append(DocIssue(
                    file_path=str(file_path),
                    issue_type=DocIssueType.FORMAT_ERROR,
                    message="空列表项",
                    severity="low",
                    suggestion="删除空列表项或添加内容",
                    line_number=i,
                ))

        return issues

    def _check_links(self, file_path: Path, content: str) -> list[DocIssue]:
        """检查链接是否有效。"""
        issues: list[DocIssue] = []

        # 提取所有链接
        # Markdown 链接格式: [text](url)
        md_links = re.findall(r"\[([^\]]*)\]\(([^)]+)\)", content)

        # Wikilink 格式: [[page]] 或 [[page|text]]
        wiki_links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)

        for text, url in md_links:
            # 跳过外部链接和锚点
            if url.startswith("http") or url.startswith("#"):
                continue

            # 检查内部链接是否存在
            if not self._resolve_link(file_path, url):
                issues.append(DocIssue(
                    file_path=str(file_path),
                    issue_type=DocIssueType.BROKEN_LINK,
                    message=f"死链: [{text}]({url})",
                    severity="high",
                    suggestion=f"修复或删除链接: {url}",
                ))

        for page in wiki_links:
            if not self._resolve_wikilink(file_path, page):
                issues.append(DocIssue(
                    file_path=str(file_path),
                    issue_type=DocIssueType.BROKEN_LINK,
                    message=f"死链: [[{page}]]",
                    severity="medium",
                    suggestion=f"创建页面或修复链接: {page}",
                ))

        return issues

    def _resolve_link(self, file_path: Path, url: str) -> bool:
        """解析内部链接。"""
        # 处理相对路径
        target = (file_path.parent / url).resolve()

        # 检查文件或目录
        if target.exists():
            return True

        # 检查 .md 后缀
        if not url.endswith(".md"):
            md_target = target.with_suffix(".md")
            if md_target.exists():
                return True

        return False

    def _resolve_wikilink(self, _file_path: Path, page: str) -> bool:
        """解析 wikilink。"""
        # 在文档目录中搜索
        return any(
            page.lower() in md_file.stem.lower()
            for md_file in self.docs_dir.rglob("*.md")
        )

    def _check_sections(self, file_path: Path, content: str) -> list[DocIssue]:
        """检查必要章节。"""
        issues: list[DocIssue] = []
        file_name = file_path.name

        if file_name not in REQUIRED_SECTIONS:
            return issues

        required = REQUIRED_SECTIONS[file_name]
        for section in required:
            if section not in content:
                issues.append(DocIssue(
                    file_path=str(file_path),
                    issue_type=DocIssueType.MISSING_SECTIONS,
                    message=f"缺少必要章节: {section}",
                    severity="medium",
                    suggestion=f"添加 {section} 章节",
                ))

        return issues

    def _check_freshness(self, file_path: Path) -> list[DocIssue]:
        """检查文档新鲜度。"""
        issues: list[DocIssue] = []

        # 获取文件修改时间
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        age_days = (datetime.now() - mtime).days

        if age_days > FRESHNESS_THRESHOLD_DAYS:
            issues.append(DocIssue(
                file_path=str(file_path),
                issue_type=DocIssueType.OUTDATED,
                message=f"文档可能过时: {age_days} 天未更新",
                severity="low",
                suggestion="检查内容是否需要更新",
            ))

        return issues


class DocGardener:
    """文档园丁 - 自动维护文档健康。"""

    def __init__(self, docs_dir: str = "."):
        self.docs_dir = Path(docs_dir)
        self.linter = DocLinter(docs_dir)

    def garden(self) -> dict[str, Any]:
        """执行文档园艺。"""
        report = self.linter.lint()

        # 分类问题
        by_type: dict[str, int] = {}
        for issue in report.issues:
            by_type[issue.issue_type.value] = by_type.get(issue.issue_type.value, 0) + 1

        # 生成建议
        suggestions = self._generate_suggestions(report)

        return {
            "health_score": report.health_score,
            "total_docs": report.total_docs,
            "healthy_docs": report.healthy_docs,
            "issues_by_type": by_type,
            "suggestions": suggestions,
            "issues": [
                {
                    "file": issue.file_path,
                    "type": issue.issue_type.value,
                    "message": issue.message,
                    "severity": issue.severity,
                }
                for issue in report.issues[:20]  # 只返回前 20 个
            ],
        }

    def _generate_suggestions(self, report: DocHealthReport) -> list[str]:
        """生成改进建议。"""
        suggestions = []

        if report.health_score < 0.5:
            suggestions.append("⚠️ 文档健康分数过低，建议优先处理高严重度问题")

        # 统计问题类型
        type_counts: dict[str, int] = {}
        for issue in report.issues:
            type_counts[issue.issue_type.value] = type_counts.get(issue.issue_type.value, 0) + 1

        if type_counts.get("broken_link", 0) > 0:
            suggestions.append(f"🔗 发现 {type_counts['broken_link']} 个死链，需要修复")

        if type_counts.get("outdated", 0) > 0:
            suggestions.append(f"📅 {type_counts['outdated']} 个文档可能过时，需要检查更新")

        if type_counts.get("format_error", 0) > 0:
            suggestions.append(f"📝 {type_counts['format_error']} 个格式问题，建议统一规范")

        return suggestions


def run_doc_lint() -> dict[str, Any]:
    """运行文档 Lint 检查。"""
    gardener = DocGardener()
    return gardener.garden()
