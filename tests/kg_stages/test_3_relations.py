"""阶段 3: 关系抽取测试

测试从实体中抽取关系。

运行: python tests/kg_stages/test_3_relations.py
"""

import asyncio
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.kg_extractor.relation_extractor import extract_relations
from src.tools.kg_storage.models import DocumentChunk, Entity


# ============== 配置 ==============
CHUNKS_FILE = Path("data/kg_stages/1_chunks.json")
ENTITIES_FILE = Path("data/kg_stages/2_entities.json")
OUTPUT_FILE = Path("data/kg_stages/3_relations.json")
BOOK = "西游记测试"
SOURCE = "material"


def load_chunks() -> list[DocumentChunk]:
    """加载分块"""
    if not CHUNKS_FILE.exists():
        print(f"❌ 请先运行阶段 1: python tests/kg_stages/test_1_parse.py")
        return []

    with open(CHUNKS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    return [
        DocumentChunk(
            chunk_id=item["chunk_id"],
            content=item["content"],
            doc_id=item["doc_id"],
            book=item["book"],
            chunk_index=item["chunk_index"],
            start_char=item["start_char"],
            end_char=item["end_char"],
        )
        for item in data
    ]


def load_entities() -> list[Entity]:
    """加载实体"""
    if not ENTITIES_FILE.exists():
        print(f"❌ 请先运行阶段 2: python tests/kg_stages/test_2_entities.py")
        return []

    with open(ENTITIES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    return [
        Entity(
            name=item["name"],
            entity_type=item["entity_type"],
            book=item["book"],
            source=item["source"],
            description=item.get("description", ""),
            confidence=item.get("confidence", 1.0),
        )
        for item in data
    ]


async def test_extract_relations():
    """测试关系抽取"""
    print("=" * 60)
    print("阶段 3: 关系抽取测试")
    print("=" * 60)

    # 加载数据
    chunks = load_chunks()
    entities = load_entities()

    if not chunks or not entities:
        return []

    print(f"\n📥 加载了 {len(chunks)} 个分块")
    print(f"📥 加载了 {len(entities)} 个实体")

    # 显示实体列表
    print("\n实体列表:")
    for e in entities:
        print(f"   • [{e.entity_type}] {e.name}")

    # 执行关系抽取
    print(f"\n⏳ 正在抽取关系...")

    relations = await extract_relations(chunks, entities, BOOK, SOURCE)

    # 显示结果
    print(f"\n✅ 抽取完成，共 {len(relations)} 条关系\n")

    if relations:
        print("关系列表:")
        for r in relations:
            desc = f" ({r.description[:20]}...)" if r.description and len(r.description) > 20 else f" ({r.description})" if r.description else ""
            print(f"   • {r.source_entity_name} --[{r.relation_type}]--> {r.target_entity_name}{desc}")
    else:
        print("⚠️ 未抽取到任何关系")
        print("\n可能原因:")
        print("   1. 本地 LLM 服务未启动 (检查 http://localhost:8200/health)")
        print("   2. 实体类型没有对应的关系 schema")
        print("   3. 文本中没有明确的关系描述")

    # 保存结果
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    relations_data = [
        {
            "source_entity_name": r.source_entity_name,
            "target_entity_name": r.target_entity_name,
            "relation_type": r.relation_type,
            "book": r.book,
            "source": r.source,
            "description": r.description,
            "confidence": r.confidence,
        }
        for r in relations
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(relations_data, f, ensure_ascii=False, indent=2)

    print(f"\n📁 结果已保存: {OUTPUT_FILE}")

    return relations


if __name__ == "__main__":
    relations = asyncio.run(test_extract_relations())
