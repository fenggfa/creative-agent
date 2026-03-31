"""阶段 1: 文档解析测试

测试文档分块功能，查看分块结果。

运行: python tests/kg_stages/test_1_parse.py
"""

import asyncio
import json
from pathlib import Path

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.kg_extractor.document_parser import parse_document
from src.config import settings


# ============== 测试数据 ==============
TEST_DOCUMENT = """
孙悟空是花果山水帘洞的美猴王，他师从菩提祖师学习七十二变和筋斗云。
后来孙悟空大闹天宫，被如来佛祖压在五行山下五百年。
唐僧救出孙悟空后，师徒四人西天取经，一路上降妖除魔。

猪八戒原是天蓬元帅，因调戏嫦娥被贬下凡，错投猪胎。
沙僧原是卷帘大将，因打碎琉璃盏被贬到流沙河。

白龙马是西海龙王三太子，因纵火烧了殿上明珠，被父亲告了忤逆。
观音菩萨点化他变作白马，驮着唐僧西天取经。
"""

OUTPUT_DIR = Path("data/kg_stages")


async def test_parse():
    """测试文档解析"""
    print("=" * 60)
    print("阶段 1: 文档解析测试")
    print("=" * 60)

    # 配置
    doc_id = "test_doc_001"
    book = "西游记测试"
    chunk_size = settings.KG_CHUNK_SIZE
    overlap = settings.KG_CHUNK_OVERLAP

    print(f"\n📝 配置:")
    print(f"   文档 ID: {doc_id}")
    print(f"   书名: {book}")
    print(f"   分块大小: {chunk_size}")
    print(f"   重叠大小: {overlap}")

    # 执行解析
    print(f"\n📄 原始文档 ({len(TEST_DOCUMENT)} 字符):")
    print("-" * 40)
    print(TEST_DOCUMENT[:200] + "..." if len(TEST_DOCUMENT) > 200 else TEST_DOCUMENT)
    print("-" * 40)

    print("\n⏳ 正在解析文档...")
    chunks = await parse_document(
        content=TEST_DOCUMENT,
        doc_id=doc_id,
        book=book,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    # 显示结果
    print(f"\n✅ 解析完成，共 {len(chunks)} 个分块\n")

    for i, chunk in enumerate(chunks):
        print(f"─── 分块 {i + 1} ───")
        print(f"ID: {chunk.chunk_id}")
        print(f"位置: [{chunk.start_char}, {chunk.end_char}]")
        print(f"内容 ({len(chunk.content)} 字符):")
        print(chunk.content)
        print()

    # 保存结果
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "1_chunks.json"

    chunks_data = [
        {
            "chunk_id": c.chunk_id,
            "content": c.content,
            "doc_id": c.doc_id,
            "book": c.book,
            "chunk_index": c.chunk_index,
            "start_char": c.start_char,
            "end_char": c.end_char,
        }
        for c in chunks
    ]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, ensure_ascii=False, indent=2)

    print(f"📁 结果已保存: {output_file}")

    return chunks


if __name__ == "__main__":
    chunks = asyncio.run(test_parse())
