"""多智能体创作工作流 CLI 入口。

支持两种模式：
1. 创作模式：python -m src.main "写一段孙悟空的故事"
2. 知识图谱构建：python -m src.main --upload book.txt --book 西游记
"""

import argparse
import asyncio
import re
from pathlib import Path
from typing import Any

from src.config import settings
from src.tools.kg_storage import EntityIndex, Neo4jClient
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


async def upload_document(
    file_path: str,
    book: str,
    source: str = "material",
    debug: bool = False,
) -> dict[str, Any]:
    """
    上传文档并构建知识图谱。

    Args:
        file_path: 文档文件路径
        book: 书名
        source: 来源类型 (material/creative)
        debug: 是否启用调试模式

    Returns:
        构建结果
    """
    from src.agents.kg_builder import build_knowledge_graph

    # 读取文件
    path = Path(file_path)
    if not path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return {"success": False, "error": "文件不存在"}

    print(f"\n{'='*60}")
    print(f"上传文档: {file_path}")
    print(f"书名: {book}")
    print(f"来源: {source}")
    if debug:
        print("调试模式: 启用")
    print(f"{'='*60}\n")

    # 读取内容
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="gbk")

    print(f"文档大小: {len(content)} 字符\n")

    # 连接服务
    neo4j_client = Neo4jClient()
    entity_index = EntityIndex()

    try:
        await neo4j_client.connect()
        await entity_index.connect()
    except Exception as e:
        print(f"❌ 服务连接失败: {e}")
        return {"success": False, "error": str(e)}

    # 构建知识图谱
    print("开始构建知识图谱...\n")

    try:
        result = await build_knowledge_graph(
            document=content,
            book=book,
            source=source,
            neo4j_client=neo4j_client,
            entity_index=entity_index,
            debug_mode=debug,
        )

        # 打印结果
        print(f"\n{'─'*60}")
        print("知识图谱构建完成")
        print(f"{'─'*60}")
        print(f"  文档 ID: {result.doc_id}")
        print(f"  处理分块: {result.chunks_processed}")
        print(f"  提取实体: {len(result.entities)} 个")
        print(f"  抽取关系: {len(result.relations)} 条")
        print(f"  耗时: {result.build_time_seconds:.2f}s")

        if result.success:
            print("\n✅ 构建成功")

            # 显示部分实体
            if result.entities:
                print("\n实体示例 (前5个):")
                for entity in result.entities[:5]:
                    print(f"  - [{entity.entity_type}] {entity.name}")
                    if entity.description:
                        desc_len = len(entity.description)
                        suffix = "..." if desc_len > 50 else ""
                        desc = entity.description[:50] + suffix
                        print(f"    {desc}")

            # 调试模式下提示报告位置
            if debug:
                from src.config import settings

                print(f"\n📄 调试报告已保存: {settings.KG_TRACE_OUTPUT_DIR}/{result.doc_id}.md")
        else:
            print(f"\n❌ 构建失败: {result.error_message}")

        return result.to_dict()

    except Exception as e:
        print(f"\n❌ 构建失败: {e}")
        return {"success": False, "error": str(e)}

    finally:
        await neo4j_client.close()
        await entity_index.close()


async def query_knowledge_graph(
    query: str,
    book: str | None = None,
) -> str:
    """
    查询知识图谱。

    Args:
        query: 查询问题
        book: 书名过滤

    Returns:
        查询结果
    """
    from src.tools.kg_storage import LocalKGService

    print(f"\n{'='*60}")
    print(f"查询: {query}")
    if book:
        print(f"书名: {book}")
    print(f"{'='*60}\n")

    service = LocalKGService()

    try:
        await service.connect()
        answer = await service.query(query, book=book)

        print(answer)
        return answer

    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return f"查询失败: {e}"

    finally:
        await service.close()


async def list_knowledge_graphs() -> list[str]:
    """列出所有知识图谱（按书名）。"""
    from src.tools.kg_storage import LocalKGService

    service = LocalKGService()

    try:
        await service.connect()

        # 获取统计
        stats = await service.get_stats()

        print(f"\n{'='*60}")
        print("知识图谱统计")
        print(f"{'='*60}\n")

        print(f"总实体数: {stats['neo4j'].get('entity_count', 0)}")
        print(f"总关系数: {stats['neo4j'].get('relation_count', 0)}")

        # 按书统计
        by_book = stats.get('index', {}).get('by_book', {})
        if by_book:
            print("\n按书统计:")
            for book_name, count in by_book.items():
                print(f"  - {book_name}: {count} 实体")

        # 按类型统计
        by_type = stats.get('index', {}).get('by_type', {})
        if by_type:
            print("\n按类型统计:")
            for entity_type, count in by_type.items():
                print(f"  - {entity_type}: {count}")

        return list(by_book.keys())

    except Exception as e:
        print(f"❌ 获取统计失败: {e}")
        return []

    finally:
        await service.close()


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


def main() -> Any:
    """CLI 入口函数。"""
    parser = argparse.ArgumentParser(
        description="多智能体创作工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 创作模式
  python -m src.main "写一段孙悟空大闹天宫的故事"

  # 上传文档构建知识图谱
  python -m src.main --upload docs/西游记.txt --book 西游记
  python -m src.main --upload docs/二创.txt --book 西游记 --source creative

  # 调试模式：查看详细构建过程
  python -m src.main --upload docs/test.txt --book 测试 --debug

  # 查询知识图谱
  python -m src.main --query "孙悟空的武器是什么"
  python -m src.main --query "孙悟空的朋友" --book 西游记

  # 列出所有知识图谱
  python -m src.main --list
        """,
    )

    # 互斥组：上传文档 vs 查询 vs 列表
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--upload",
        metavar="FILE",
        help="上传文档并构建知识图谱",
    )
    group.add_argument(
        "--query",
        metavar="QUESTION",
        help="查询知识图谱",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="列出所有知识图谱",
    )

    # 位置参数：创作任务（当没有指定其他模式时使用）
    parser.add_argument(
        "task",
        nargs="*",
        help="创作任务描述",
    )

    # 可选参数
    parser.add_argument(
        "--tools",
        action="store_true",
        help="创作模式：使用工具调用（LLM 自动选择工具）",
    )
    parser.add_argument(
        "--book",
        default="未命名",
        help="上传模式：书名（默认：未命名）",
    )
    parser.add_argument(
        "--source",
        choices=["material", "creative"],
        default="material",
        help="上传模式：来源类型（默认：material）",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="上传模式：启用调试模式，输出详细的构建过程报告",
    )

    args = parser.parse_args()

    # 检查是否提供了足够的参数
    if not (args.upload or args.query or args.list or args.task):
        parser.error("需要提供创作任务，或使用 --upload/--query/--list 之一")

    # 根据模式执行
    if args.upload:
        # 上传文档模式
        asyncio.run(upload_document(
            file_path=args.upload,
            book=args.book,
            source=args.source,
            debug=args.debug,
        ))
        return None

    elif args.query:
        # 查询模式
        asyncio.run(query_knowledge_graph(
            query=args.query,
            book=args.book if args.book != "未命名" else None,
        ))
        return None

    elif args.list:
        # 列表模式
        asyncio.run(list_knowledge_graphs())
        return None

    else:
        # 创作模式
        if not args.task:
            parser.error("创作模式需要提供任务描述")
        task = " ".join(args.task)
        return asyncio.run(run_workflow(task, use_tools=args.tools))


if __name__ == "__main__":
    main()
