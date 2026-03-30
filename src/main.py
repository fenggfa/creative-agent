"""多智能体创作工作流 CLI 入口。"""

import asyncio
import re

from src.config import settings
from src.tools.kg_storage.neo4j_client import Neo4jClient
from src.workflow.orchestrator import app
from src.workflow.state import AgentState


def _clean_display_content(content: str, max_length: int = 500) -> str:
    """清理并截断显示内容。"""
    if not content:
        return ""

    # 移除 <...> 标签
    cleaned = re.sub(r"<>", "", content)
    cleaned = re.sub(r"</>", "", cleaned)

    # 移除连续空行
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # 截断
    if len(cleaned) > max_length:
        return cleaned[:max_length] + "...\n"

    return cleaned


async def check_services() -> bool:
    """检查必要服务连接。"""
    print("检查服务连接...")

    # 检查 Neo4j
    neo4j_client = Neo4jClient()
    try:
        await neo4j_client.connect()
        is_healthy = await neo4j_client.health_check()
        await neo4j_client.close()

        if is_healthy:
            print("✅ Neo4j 图数据库连接正常\n")
            return True
        print("❌ Neo4j 连接失败\n")
        return False
    except Exception as e:
        print(f"❌ Neo4j 连接错误: {e}\n")
        return False


async def run_workflow(task: str, use_tools: bool = False) -> str:
    """
    运行完整的创作工作流。

    Args:
        task: 创作任务描述
        use_tools: 是否使用工具调用模式

    Returns:
        最终创作输出
    """
    print(f"\n{'='*60}")
    print(f"创作任务: {task}")
    if use_tools:
        print("模式: 工具调用 (ReAct Agent)")
    print(f"{'='*60}\n")

    # 检查服务连接
    await check_services()

    # 初始化状态
    initial_state: AgentState = {
        "task": task,
        "revision_count": 0,
        "use_tools": use_tools,
    }

    # 运行工作流
    print("开始执行工作流...\n")
    final_state = await app.ainvoke(initial_state)

    # 打印进度
    print(f"\n{'─'*60}")
    print("素材收集完成")
    print(f"{'─'*60}")
    materials = final_state.get("materials", "")
    print(_clean_display_content(materials) + "\n")

    print(f"{'─'*60}")
    print(f"创作完成 (修改次数: {final_state.get('revision_count', 0)})")
    print(f"{'─'*60}")

    if final_state.get("approved", False):
        print("审核: 通过 ✓")
    else:
        print(f"审核: 达到最大修改次数 ({settings.MAX_REVISIONS})")
        print(f"最后反馈: {final_state.get('review_feedback', '')[:200]}...")

    print(f"\n{'='*60}")
    print("最终输出")
    print(f"{'='*60}\n")

    output = final_state.get("final_output") or final_state.get("draft", "")
    output_str = str(output) if output else ""

    print(output_str)

    return output_str


def main() -> str:
    """CLI 入口函数。"""
    import argparse

    parser = argparse.ArgumentParser(description="多智能体创作工作流")
    parser.add_argument("task", nargs="+", help="创作任务描述")
    parser.add_argument(
        "--tools",
        action="store_true",
        help="使用工具调用模式（LLM 自动选择工具）",
    )

    args = parser.parse_args()
    task = " ".join(args.task)
    result = asyncio.run(run_workflow(task, use_tools=args.tools))
    return result


if __name__ == "__main__":
    main()
