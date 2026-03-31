"""关系抽取调试脚本

检查关系抽取过程中发生了什么。

运行: python tests/kg_stages/debug_relations.py
"""

import asyncio
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.kg_extractor.llm_client import get_llm_client
from src.tools.kg_extractor.schema_manager import get_schema_manager


async def debug_relations():
    """调试关系抽取"""
    print("=" * 60)
    print("关系抽取调试")
    print("=" * 60)

    # 1. 检查 LLM 服务
    print("\n1️⃣ 检查 LLM 服务")
    print("-" * 40)
    client = get_llm_client()
    is_healthy = client.health_check()
    print(f"   服务状态: {'✅ 正常' if is_healthy else '❌ 不可用'}")

    if not is_healthy:
        print("\n   请先启动 LLM 服务:")
        print("   python server/nlu_server.py")
        return

    # 2. 加载实体
    print("\n2️⃣ 加载实体")
    print("-" * 40)
    entities_file = Path("data/kg_stages/2_entities.json")
    if not entities_file.exists():
        print("   ❌ 请先运行阶段 2")
        return

    with open(entities_file, encoding="utf-8") as f:
        entities = json.load(f)

    entity_types = {e["entity_type"] for e in entities}
    print(f"   实体数量: {len(entities)}")
    print(f"   实体类型: {sorted(entity_types)}")

    # 3. 获取关系 Schema
    print("\n3️⃣ 关系 Schema")
    print("-" * 40)
    schema_manager = get_schema_manager()
    schemas = schema_manager.get_relation_schemas_separate(subject_types=list(entity_types))

    print(f"   可用关系 schema 数量: {len(schemas)}")

    for schema in schemas:
        rel_name = list(schema.keys())[0]
        args = schema[rel_name]
        print(f"   - {rel_name}: {list(args.keys())}")

    if not schemas:
        print("   ⚠️ 没有匹配的关系 schema!")
        print("   实体类型需要匹配 schema 中的主体类型:")
        print(f"   当前实体类型: {entity_types}")
        print(f"   Schema 支持的主体类型: {list(schema_manager._relation_types.keys())}")

    # 4. 测试抽取
    print("\n4️⃣ 测试关系抽取")
    print("-" * 40)

    # 加载文本
    chunks_file = Path("data/kg_stages/1_chunks.json")
    with open(chunks_file, encoding="utf-8") as f:
        chunks = json.load(f)

    text = chunks[0]["content"]
    print(f"   文本长度: {len(text)} 字符")

    # 逐个测试关系 schema
    for schema in schemas[:3]:  # 只测试前3个
        rel_name = list(schema.keys())[0]
        print(f"\n   测试关系: {rel_name}")
        print(f"   Schema: {schema}")

        try:
            result = client.extract(text, schema)
            print(f"   原始响应: {json.dumps(result, ensure_ascii=False)[:200]}...")

            data = result.get("data", [])
            if data:
                relations = data[0].get("relations", [])
                print(f"   抽取结果: {len(relations)} 条")
                for r in relations[:3]:
                    print(f"      - {r}")
            else:
                print("   抽取结果: 0 条")

        except Exception as e:
            print(f"   ❌ 错误: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(debug_relations())
