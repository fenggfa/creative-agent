"""多智能体创作工作流 CLI 入口。"""

import asyncio
import sys

from src.config import settings
from src.tools.lightrag import lightrag_client
from src.workflow.orchestrator import app


async def run_workflow(task: str) -> str:
    """
    运行完整的创作工作流。

    Args:
        task: 创作任务描述

    Returns:
        最终创作输出
    """
    print(f"\n{'='*60}")
    print(f"创作任务: {task}")
    print(f"{'='*60}\n")

    # 检查 LightRAG 连接
    print("检查 LightRAG 服务连接...")
    if not await lightrag_client.health_check():
        print("警告: LightRAG 服务不可用，请确保服务已启动")
    else:
        print("LightRAG 服务连接正常\n")

    # 初始化状态
    initial_state: dict = {
        "task": task,
        "revision_count": 0,
    }

    # 运行工作流
    print("开始执行工作流...\n")
    final_state = await app.ainvoke(initial_state)

    # 打印进度
    print(f"\n{'─'*60}")
    print("素材收集完成")
    print(f"{'─'*60}")
    print(final_state.get("materials", "")[:500] + "...\n")

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
    print(output)

    return output


def main():
    """CLI 入口函数。"""
    if len(sys.argv) < 2:
        print("用法: python -m src.main <创作任务>")
        print("示例: python -m src.main '写一段孙悟空大战红孩儿的精彩场景'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    result = asyncio.run(run_workflow(task))
    return result


if __name__ == "__main__":
    main()
