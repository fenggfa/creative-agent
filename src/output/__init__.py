"""二创内容输出模块 - 保存到 Obsidian 和 LightRAG。

架构设计：
===========================================

使用服务层的直接调用函数，不依赖工具选择。

- save_creative_content() → 直接调用 graph_service
- 100% 可靠，不依赖 LLM 选择
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import settings
from src.tools.graph_service import save_creative_content as save_to_graph


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
            formatted = self._format_content(content, task, evaluation)

            output_path.write_text(formatted, encoding="utf-8")

            result["success"] = True
            result["path"] = str(output_path)

        except Exception as e:
            result["error"] = str(e)

        return result

    async def save_to_lightrag(
        self,
        content: str,
        task: str,
        source_work: str = "西游记",
    ) -> dict[str, Any]:
        """保存二创内容到 LightRAG 二创图谱（直接调用服务层）。"""
        # 使用服务层的直接调用函数
        title = f"【{source_work}】{task}"
        return await save_to_graph(content, title)

    async def save_all(
        self,
        content: str,
        task: str,
        source_work: str = "西游记",
        evaluation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """保存到所有目标（Obsidian + LightRAG）。"""
        import asyncio

        obsidian_task = self.save_to_obsidian(content, task, source_work, evaluation)
        lightrag_task = self.save_to_lightrag(content, task, source_work)

        obsidian_result, lightrag_result = await asyncio.gather(
            obsidian_task, lightrag_task
        )

        return {
            "obsidian": obsidian_result,
            "lightrag": lightrag_result,
            "success": obsidian_result["success"] or lightrag_result["success"],
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
