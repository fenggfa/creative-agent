"""二创内容输出模块 - 保存到 Obsidian 和知识图谱。

架构设计：
===========================================

使用服务层的直接调用函数，不依赖工具选择。

- save_creative_content() → 直接调用 graph_service
- 100% 可靠，不依赖 LLM 选择
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import settings
from src.tools.graph_service import save_creative_content as save_to_graph


def clean_final_output(content: str) -> str:
    """
    清理最终输出内容，移除思考过程、参考标记等。

    Args:
        content: 原始内容

    Returns:
        清理后的正文内容
    """
    if not content:
        return content

    # 移除 <think>...</think> 标签及其内容（思考过程）
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE)

    # 移除其他常见的思考标签
    cleaned = re.sub(r"<reasoning>[\s\S]*?</reasoning>", "", cleaned, flags=re.IGNORECASE)

    # 移除 References 部分（通常是模型生成的参考资料）
    cleaned = re.sub(
        r"\n---\s*\n###?\s*References?\s*\n.*$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # 移除写作说明部分
    cleaned = re.sub(
        r"\n---\s*\n\*\*写作说明\*\*.*$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # 移除连续的空行（超过2个）
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


class OutputManager:
    """二创内容输出管理器。"""

    def __init__(
        self,
        vault_path: str | None = None,
        output_dir: str | None = None,
    ):
        self.vault_path = Path(vault_path or settings.OBSIDIAN_VAULT)
        self.output_dir = output_dir or settings.CREATIVE_OUTPUT_DIR

    def _get_output_path(self, source_work: str, title: str) -> Path:
        """获取输出文件路径。"""
        work_dir = self.vault_path / self.output_dir / source_work / "章节"
        work_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = title.replace("/", "-").replace("\\", "-")[:50]
        filename = f"{safe_title}_{timestamp}.md"

        return work_dir / filename

    def _format_content(
        self,
        content: str,
        task: str,
        evaluation: dict[str, Any] | None = None,
    ) -> str:
        """格式化为 Obsidian Markdown。"""
        lines = [
            f"# {task}",
            "",
            f"> 创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
            "## 正文",
            "",
            content,
        ]

        if evaluation:
            lines.extend([
                "",
                "---",
                "",
                "## 评估结果",
                "",
                f"- **总分**: {evaluation.get('total_score', 'N/A')}",
                f"- **通过**: {'✅' if evaluation.get('passed') else '❌'}",
            ])

            scores = evaluation.get("scores", [])
            if scores:
                lines.append("")
                lines.append("### 维度评分")
                lines.append("")
                lines.append("| 维度 | 分数 |")
                lines.append("|------|------|")
                for score in scores:
                    dim = score.get("dimension", "N/A")
                    val = score.get("score", 0)
                    lines.append(f"| {dim} | {val:.2f} |")

        lines.extend([
            "",
            "---",
            "",
            "#二创作品 #AI创作",
        ])

        return "\n".join(lines)

    async def save_to_obsidian(
        self,
        content: str,
        task: str,
        source_work: str = "西游记",
        evaluation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """保存二创内容到 Obsidian。"""
        result: dict[str, Any] = {
            "success": False,
            "path": None,
            "error": None,
        }

        try:
            output_path = self._get_output_path(source_work, task)
            # 清理内容，只保留正文
            cleaned_content = clean_final_output(content)
            formatted = self._format_content(cleaned_content, task, evaluation)

            output_path.write_text(formatted, encoding="utf-8")

            result["success"] = True
            result["path"] = str(output_path)

        except Exception as e:
            result["error"] = str(e)

        return result

    async def save_to_kg(
        self,
        content: str,
        task: str,
        source_work: str = "西游记",
    ) -> dict[str, Any]:
        """保存二创内容到知识图谱。"""
        # 清理内容，只保留正文
        cleaned_content = clean_final_output(content)
        # 使用服务层的直接调用函数
        title = f"【{source_work}】{task}"
        return await save_to_graph(cleaned_content, title, book=source_work)

    async def save_all(
        self,
        content: str,
        task: str,
        source_work: str = "西游记",
        evaluation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """保存到所有目标（Obsidian + 知识图谱）。"""
        import asyncio

        obsidian_task = self.save_to_obsidian(content, task, source_work, evaluation)
        kg_task = self.save_to_kg(content, task, source_work)

        obsidian_result, kg_result = await asyncio.gather(
            obsidian_task, kg_task
        )

        return {
            "obsidian": obsidian_result,
            "kg": kg_result,
            "success": obsidian_result["success"] or kg_result["success"],
        }


# 全局输出管理器实例
output_manager = OutputManager()


async def save_creative_output(
    content: str,
    task: str,
    source_work: str = "西游记",
    evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """便捷函数：保存二创内容。"""
    return await output_manager.save_all(content, task, source_work, evaluation)
