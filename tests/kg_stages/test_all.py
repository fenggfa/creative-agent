"""运行所有阶段的测试

依次运行: 文档解析 → 实体提取 → 关系抽取

运行: python tests/kg_stages/test_all.py
"""

import asyncio
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def run_all_stages():
    """运行所有阶段"""
    print("=" * 60)
    print("知识图谱构建 - 完整流程测试")
    print("=" * 60)

    total_start = time.time()

    # 阶段 1: 文档解析
    print("\n" + "─" * 40)
    print("阶段 1/3: 文档解析")
    print("─" * 40)

    from tests.kg_stages.test_1_parse import test_parse
    start = time.time()
    chunks = await test_parse()
    stage1_time = time.time() - start

    if not chunks:
        print("❌ 阶段 1 失败，停止测试")
        return

    # 阶段 2: 实体提取
    print("\n" + "─" * 40)
    print("阶段 2/3: 实体提取")
    print("─" * 40)

    from tests.kg_stages.test_2_entities import test_extract_entities
    start = time.time()
    entities = await test_extract_entities()
    stage2_time = time.time() - start

    if not entities:
        print("⚠️ 阶段 2 未提取到实体")

    # 阶段 3: 关系抽取
    print("\n" + "─" * 40)
    print("阶段 3/3: 关系抽取")
    print("─" * 40)

    from tests.kg_stages.test_3_relations import test_extract_relations
    start = time.time()
    relations = await test_extract_relations()
    stage3_time = time.time() - start

    # 汇总
    total_time = time.time() - total_start

    print("\n" + "=" * 60)
    print("测试完成 - 汇总")
    print("=" * 60)
    print(f"\n📊 结果统计:")
    print(f"   文档分块: {len(chunks)} 个")
    print(f"   提取实体: {len(entities)} 个")
    print(f"   抽取关系: {len(relations)} 条")

    print(f"\n⏱️ 耗时统计:")
    print(f"   阶段 1 (文档解析): {stage1_time:.2f}s")
    print(f"   阶段 2 (实体提取): {stage2_time:.2f}s")
    print(f"   阶段 3 (关系抽取): {stage3_time:.2f}s")
    print(f"   总耗时: {total_time:.2f}s")

    print(f"\n📁 中间结果保存位置:")
    print(f"   data/kg_stages/1_chunks.json")
    print(f"   data/kg_stages/2_entities.json")
    print(f"   data/kg_stages/3_relations.json")


if __name__ == "__main__":
    asyncio.run(run_all_stages())
