"""查看各阶段的测试结果

运行: python tests/kg_stages/view_results.py
"""

import json
from pathlib import Path

DATA_DIR = Path("data/kg_stages")


def view_results():
    """查看所有阶段的结果"""
    print("=" * 60)
    print("知识图谱构建 - 阶段结果查看")
    print("=" * 60)

    # 阶段 1: 分块结果
    chunks_file = DATA_DIR / "1_chunks.json"
    if chunks_file.exists():
        with open(chunks_file, encoding="utf-8") as f:
            chunks = json.load(f)
        print(f"\n📄 阶段 1: 文档分块 ({len(chunks)} 个)")
        print("-" * 40)
        for i, c in enumerate(chunks):
            content = c["content"]
            preview = content[:100] + "..." if len(content) > 100 else content
            print(f"   [{i}] {preview}")
    else:
        print(f"\n❌ 阶段 1 结果不存在: {chunks_file}")

    # 阶段 2: 实体结果
    entities_file = DATA_DIR / "2_entities.json"
    if entities_file.exists():
        with open(entities_file, encoding="utf-8") as f:
            entities = json.load(f)
        print(f"\n👤 阶段 2: 实体提取 ({len(entities)} 个)")
        print("-" * 40)

        # 按类型分组
        by_type: dict[str, list] = {}
        for e in entities:
            by_type.setdefault(e["entity_type"], []).append(e)

        for entity_type, items in sorted(by_type.items()):
            print(f"\n   [{entity_type}] ({len(items)} 个)")
            for e in items:
                print(f"      • {e['name']}")
    else:
        print(f"\n❌ 阶段 2 结果不存在: {entities_file}")

    # 阶段 3: 关系结果
    relations_file = DATA_DIR / "3_relations.json"
    if relations_file.exists():
        with open(relations_file, encoding="utf-8") as f:
            relations = json.load(f)
        print(f"\n🔗 阶段 3: 关系抽取 ({len(relations)} 条)")
        print("-" * 40)
        if relations:
            for r in relations:
                print(f"   {r['source_entity_name']} --[{r['relation_type']}]--> {r['target_entity_name']}")
        else:
            print("   (无关系)")
    else:
        print(f"\n❌ 阶段 3 结果不存在: {relations_file}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    view_results()
