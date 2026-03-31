"""阶段 2: 实体提取测试

测试从文档分块中提取实体。

运行: python tests/kg_stages/test_2_entities.py
"""

import asyncio
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.kg_extractor.entity_extractor import extract_entities
from src.tools.kg_storage.models import DocumentChunk


# ============== 配置 ==============
INPUT_FILE = Path("data/kg_stages/1_chunks.json")
OUTPUT_FILE = Path("data/kg_stages/2_entities.json")
BOOK = "西游记测试"
SOURCE = "material"


def load_chunks() -> list[DocumentChunk]:
    """加载上一阶段的分块结果"""
    if not INPUT_FILE.exists():
        print(f"❌ 请先运行阶段 1: python tests/kg_stages/test_1_parse.py")
        return []

    with open(INPUT_FILE, encoding="utf-8") as f:
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


async def test_extract_entities():
    """测试实体提取"""
    print("=" * 60)
    print("阶段 2: 实体提取测试")
    print("=" * 60)

    # 加载分块
    chunks = load_chunks()
    if not chunks:
        return []

    print(f"\n📥 加载了 {len(chunks)} 个分块")

    # 执行实体提取
    print(f"\n⏳ 正在提取实体...")
    print(f"   书名: {BOOK}")
    print(f"   来源: {SOURCE}")

    entities = await extract_entities(chunks, BOOK, SOURCE)

    # 显示结果
    print(f"\n✅ 提取完成，共 {len(entities)} 个实体\n")

    # 按类型分组显示
    by_type: dict[str, list] = {}
    for e in entities:
        by_type.setdefault(e.entity_type, []).append(e)

    for entity_type, items in sorted(by_type.items()):
        print(f"─── {entity_type} ({len(items)} 个) ───")
        for e in items:
            desc = f": {e.description[:30]}..." if e.description and len(e.description) > 30 else f": {e.description}" if e.description else ""
            print(f"   • {e.name}{desc}")
        print()

    # 保存结果
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    entities_data = [
        {
            "name": e.name,
            "entity_type": e.entity_type,
            "book": e.book,
            "source": e.source,
            "description": e.description,
            "confidence": e.confidence,
        }
        for e in entities
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entities_data, f, ensure_ascii=False, indent=2)

    print(f"📁 结果已保存: {OUTPUT_FILE}")

    return entities


if __name__ == "__main__":
    entities = asyncio.run(test_extract_entities())
