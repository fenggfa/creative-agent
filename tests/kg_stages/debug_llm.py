"""调试 LLM 服务响应格式

运行: python tests/kg_stages/debug_llm.py
"""

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.kg_extractor.llm_client import get_llm_client


def debug_llm_response():
    """调试 LLM 响应格式"""
    print("=" * 60)
    print("LLM 服务响应格式调试")
    print("=" * 60)

    client = get_llm_client()

    # 检查服务
    if not client.health_check():
        print("❌ LLM 服务不可用")
        return

    # 测试文本
    text = """
孙悟空是花果山水帘洞的美猴王，他师从菩提祖师学习七十二变和筋斗云。
后来孙悟空大闹天宫，被如来佛祖压在五行山下五百年。
唐僧救出孙悟空后，师徒四人西天取经，一路上降妖除魔。
"""

    # 测试实体抽取
    print("\n1️⃣ 实体抽取测试")
    print("-" * 40)

    entity_schema = {"人物": None, "地理位置": None, "物品": None}
    print(f"Schema: {entity_schema}")

    result = client.extract(text, entity_schema)
    print(f"\n完整响应:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 测试关系抽取
    print("\n2️⃣ 关系抽取测试")
    print("-" * 40)

    relation_schema = {"师父": {"人物": None}}
    print(f"Schema: {relation_schema}")

    result = client.extract(text, relation_schema)
    print(f"\n完整响应:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    debug_llm_response()
