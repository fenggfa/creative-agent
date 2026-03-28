"""知识图谱 LangChain 工具封装。

工具分类：
- 查询工具：从图谱获取信息
- 写入工具：保存内容到图谱
- 实体工具：管理图谱实体
- 关系工具：管理实体关系
- 图谱工具：查看图谱结构

工具选择指南：
1. 创作前研究设定 → query_dual_graphs（推荐）或 query_material_graph
2. 检查之前创作 → query_creative_graph
3. 保存创作内容 → save_to_creative_graph
4. 确认实体存在 → check_entity_exists
5. 了解图谱内容 → get_graph_labels
"""

from langchain_core.tools import tool

from src.tools.lightrag import creative_lightrag_client, lightrag_client

# ==================== 工具选择指南 ====================

TOOL_SELECTION_GUIDE = """
【工具选择快速指南】

场景 → 推荐工具：
- "我需要了解人物/设定" → query_dual_graphs（同时获取原作和二创设定）
- "只需要原作设定" → query_material_graph
- "检查之前写过什么" → query_creative_graph
- "保存我的创作" → save_to_creative_graph
- "这个角色存在吗" → check_entity_exists
- "图谱里有什么" → get_graph_labels

重要提示：
- 创作前务必查询二创图谱，避免与之前章节冲突
- query_dual_graphs 是最常用的查询工具
- save_to_creative_graph 会自动添加时间戳
"""

# ==================== 查询工具 ====================

VALID_QUERY_MIN_LENGTH = 2


@tool
async def query_material_graph(query: str) -> str:
    """
    查询素材图谱（原作设定）。

    【适用场景】
    - 只需要了解原作中的人物、背景、世界观设定
    - 不需要考虑之前创作的内容

    【不适用场景】
    - 需要对比原作和二创设定 → 请用 query_dual_graphs
    - 需要检查之前创作的设定 → 请用 query_creative_graph

    Args:
        query: 查询内容，如"孙悟空的性格特点"、"西游记的世界观"

    Returns:
        原作设定信息

    Examples:
        query_material_graph("孙悟空有什么能力")
        query_material_graph("唐僧的性格特点")
    """
    # 参数验证
    if not query or len(query.strip()) < VALID_QUERY_MIN_LENGTH:
        return "❌ 查询内容太短，请提供更具体的查询，如'孙悟空的性格特点'"

    try:
        result = await lightrag_client.query(query.strip())
        if not result:
            return f"未找到关于「{query}」的原作设定。建议换一个查询词试试。"
        return result
    except Exception as e:
        return f"❌ 查询素材图谱失败: {str(e)}"


@tool
async def query_creative_graph(query: str) -> str:
    """
    查询二创图谱（已创作内容）。

    【适用场景】
    - 检查之前创作中的人物设定
    - 确保新章节与之前章节设定一致
    - 了解当前创作的世界观演绎

    【重要】创作前务必调用此工具，避免设定冲突！

    Args:
        query: 查询内容，如"孙悟空在第1章的设定"、"主角的性格变化"

    Returns:
        已创作内容中的设定信息

    Examples:
        query_creative_graph("孙悟空的性格")
        query_creative_graph("第1章的情节")
    """
    if not query or len(query.strip()) < VALID_QUERY_MIN_LENGTH:
        return "❌ 查询内容太短，请提供更具体的查询"

    try:
        result = await creative_lightrag_client.query(query.strip())
        if not result:
            return f"二创图谱中暂无关于「{query}」的设定。这是新的设定点，可以自由创作。"
        return result
    except Exception as e:
        return f"❌ 查询二创图谱失败: {str(e)}"


@tool
async def query_dual_graphs(query: str) -> str:
    """
    同时查询素材图谱和二创图谱，合并结果。

    【推荐使用】这是最常用的查询工具！

    【适用场景】
    - 创作前全面了解人物/设定（推荐首选）
    - 需要对比原作设定和二创设定
    - 发现潜在的设定冲突

    【返回格式】
    - 【素材图谱】原作设定
    - 【二创图谱】创作演绎（如有冲突，以此为准）

    Args:
        query: 查询内容

    Returns:
        合并后的查询结果，包含来源标注

    Examples:
        query_dual_graphs("孙悟空的性格特点")
        query_dual_graphs("红孩儿的背景")
    """
    import asyncio

    if not query or len(query.strip()) < VALID_QUERY_MIN_LENGTH:
        return "❌ 查询内容太短，请提供更具体的查询，如'孙悟空的性格特点'"

    query = query.strip()

    try:
        material_task = lightrag_client.query(query)
        creative_task = creative_lightrag_client.query(query)

        material_result, creative_result = await asyncio.gather(
            material_task, creative_task, return_exceptions=True
        )

        parts: list[str] = []

        if not isinstance(material_result, Exception) and material_result:
            parts.append("=== 【素材图谱】原作设定 ===")
            parts.append(str(material_result))

        if not isinstance(creative_result, Exception) and creative_result:
            if parts:
                parts.append("")
            parts.append("=== 【二创图谱】创作演绎 ===")
            parts.append("")
            parts.append("⚠️ 注意：以下为当前创作的演绎设定，如与原作冲突，以此为准。")
            parts.append("")
            parts.append(str(creative_result))

        if not parts:
            return f"❌ 素材图谱和二创图谱均未找到关于「{query}」的信息。\n\n建议：可以自由创作。"

        return "\n".join(parts)

    except Exception as e:
        return f"❌ 双图谱查询失败: {str(e)}"


# ==================== 写入工具 ====================


@tool
async def save_to_creative_graph(content: str, title: str = "创作内容") -> str:
    """
    保存创作内容到二创图谱。

    【适用场景】
    - 完成创作后，保存人物设定、情节发展
    - 记录重要设定变更
    - 为后续章节提供参考

    【重要】保存的内容会被后续创作查询到，请确保：
    - 内容准确、完整
    - 包含关键设定信息

    Args:
        content: 要保存的内容（必填）
        title: 内容标题，如"第1章 孙悟空出场"、"人物设定：唐僧"（可选）

    Returns:
        保存结果

    Examples:
        save_to_creative_graph("孙悟空在本章学会了新技能火眼金睛", "第3章 孙悟空技能")
        save_to_creative_graph("唐僧的性格变得更加坚定", "人物发展：唐僧")
    """
    # 参数验证
    if not content or len(content.strip()) < 10:
        return "❌ 保存失败：内容太短，请提供更完整的创作内容（至少10个字符）"

    if not title:
        title = "创作内容"

    from datetime import datetime

    enriched_content = f"""【{title}】
创作时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{content.strip()}"""

    try:
        success = await creative_lightrag_client.insert(enriched_content)
        if success:
            return f"✅ 已保存「{title}」到二创图谱，后续创作可查询参考"
        return "❌ 保存失败：LightRAG 服务返回失败"
    except Exception as e:
        return f"❌ 保存失败: {str(e)}"


# ==================== 实体管理工具 ====================

VALID_ENTITY_TYPES = ["CHARACTER", "LOCATION", "ITEM", "CONCEPT"]
VALID_GRAPH_TYPES = ["material", "creative"]


@tool
async def check_entity_exists(entity_name: str) -> str:
    """
    检查实体是否存在于图谱中。

    【适用场景】
    - 确认某个人物/地点是否存在
    - 判断是否需要创建新实体

    Args:
        entity_name: 实体名称（必填），如"孙悟空"、"花果山"

    Returns:
        实体在各图谱中的存在状态

    Examples:
        check_entity_exists("孙悟空")
        check_entity_exists("红孩儿")
    """
    if not entity_name or not entity_name.strip():
        return "❌ 请提供实体名称，如 check_entity_exists('孙悟空')"

    entity_name = entity_name.strip()

    try:
        material_exists = await lightrag_client.entity_exists(entity_name)
        creative_exists = await creative_lightrag_client.entity_exists(entity_name)

        results = []
        if material_exists:
            results.append(f"✅ 素材图谱中存在「{entity_name}」")
        if creative_exists:
            results.append(f"✅ 二创图谱中存在「{entity_name}」")

        if not results:
            return f"❌ 图谱中未找到「{entity_name}」\n\n提示：如需创建，请使用 create_entity 工具"

        return "\n".join(results)

    except Exception as e:
        return f"❌ 检查失败: {str(e)}"


@tool
async def create_entity(
    entity_name: str,
    description: str,
    entity_type: str = "CHARACTER",
    graph_type: str = "creative",
) -> str:
    """
    在图谱中创建新实体。

    【适用场景】
    - 创建新人物、新地点、新物品
    - 添加重要概念

    【注意】通常不需要手动创建实体，插入文档时会自动提取。

    Args:
        entity_name: 实体名称（必填）
        description: 实体描述（必填）
        entity_type: 实体类型（可选）
            - CHARACTER: 人物（默认）
            - LOCATION: 地点
            - ITEM: 物品
            - CONCEPT: 概念
        graph_type: 图谱类型（可选）
            - creative: 二创图谱（默认）
            - material: 素材图谱

    Returns:
        创建结果

    Examples:
        create_entity("小红帽", "一个戴红帽子的小女孩", "CHARACTER", "creative")
        create_entity("神秘森林", "一片充满魔法的森林", "LOCATION")
    """
    # 参数验证
    if not entity_name or not entity_name.strip():
        return "❌ 创建失败：实体名称不能为空"

    if not description or len(description.strip()) < 5:
        return "❌ 创建失败：描述内容太短，请提供更详细的描述（至少5个字符）"

    entity_type = entity_type.upper()
    if entity_type not in VALID_ENTITY_TYPES:
        valid_types = ", ".join(VALID_ENTITY_TYPES)
        return f"❌ 创建失败：无效的实体类型 '{entity_type}'\n请使用: {valid_types}"

    if graph_type not in VALID_GRAPH_TYPES:
        return f"❌ 创建失败：无效的图谱类型 '{graph_type}'\n请使用: material 或 creative"

    client = creative_lightrag_client if graph_type == "creative" else lightrag_client
    entity_name = entity_name.strip()
    description = description.strip()

    try:
        await client.create_entity(
            entity_name=entity_name,
            entity_data={
                "description": description,
                "entity_type": entity_type,
            },
        )
        graph_name = "二创图谱" if graph_type == "creative" else "素材图谱"
        return f"✅ 已在{graph_name}创建实体「{entity_name}」（{entity_type}）"

    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "已存在" in error_msg:
            return f"❌ 实体「{entity_name}」已存在，请使用 edit_entity 修改"
        return f"❌ 创建失败: {error_msg}"


@tool
async def edit_entity(
    entity_name: str,
    new_description: str,
    graph_type: str = "creative",
) -> str:
    """
    编辑图谱中的实体描述。

    【适用场景】
    - 修正实体描述错误
    - 更新实体设定

    Args:
        entity_name: 实体名称（必填）
        new_description: 新的描述内容（必填）
        graph_type: 图谱类型（可选，默认 creative）

    Returns:
        编辑结果

    Examples:
        edit_entity("孙悟空", "齐天大圣，曾大闹天宫，后保唐僧西天取经")
    """
    if not entity_name or not entity_name.strip():
        return "❌ 编辑失败：实体名称不能为空"

    if not new_description or len(new_description.strip()) < 5:
        return "❌ 编辑失败：描述内容太短"

    if graph_type not in VALID_GRAPH_TYPES:
        return "❌ 编辑失败：无效的图谱类型，请使用 material 或 creative"

    client = creative_lightrag_client if graph_type == "creative" else lightrag_client
    entity_name = entity_name.strip()

    try:
        await client.edit_entity(
            entity_name=entity_name,
            updated_data={"description": new_description.strip()},
        )
        graph_name = "二创图谱" if graph_type == "creative" else "素材图谱"
        return f"✅ 已更新{graph_name}中的实体「{entity_name}」"

    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "不存在" in error_msg:
            return f"❌ 实体「{entity_name}」不存在，请先使用 create_entity 创建"
        return f"❌ 更新失败: {error_msg}"


@tool
async def create_relation(
    source_entity: str,
    target_entity: str,
    relation_description: str,
    keywords: str = "",
    graph_type: str = "creative",
) -> str:
    """
    在两个实体间创建关系。

    【适用场景】
    - 建立人物关系（师徒、朋友、敌人）
    - 建立地点与人物的关系

    【注意】通常不需要手动创建关系，插入文档时会自动提取。

    Args:
        source_entity: 源实体名称（必填）
        target_entity: 目标实体名称（必填）
        relation_description: 关系描述（必填），如"孙悟空的师父是唐僧"
        keywords: 关系关键词（可选），如"师徒"
        graph_type: 图谱类型（可选，默认 creative）

    Returns:
        创建结果

    Examples:
        create_relation("孙悟空", "唐僧", "孙悟空拜唐僧为师", "师徒")
    """
    if not source_entity or not source_entity.strip():
        return "❌ 创建失败：源实体名称不能为空"

    if not target_entity or not target_entity.strip():
        return "❌ 创建失败：目标实体名称不能为空"

    if not relation_description or len(relation_description.strip()) < 5:
        return "❌ 创建失败：关系描述太短"

    if graph_type not in VALID_GRAPH_TYPES:
        return "❌ 创建失败：无效的图谱类型"

    client = creative_lightrag_client if graph_type == "creative" else lightrag_client
    source_entity = source_entity.strip()
    target_entity = target_entity.strip()

    try:
        await client.create_relation(
            source_entity=source_entity,
            target_entity=target_entity,
            relation_data={
                "description": relation_description.strip(),
                "keywords": keywords.strip(),
                "weight": 1.0,
            },
        )
        return f"✅ 已创建关系「{source_entity}」→「{target_entity}」"

    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "不存在" in error_msg:
            return "❌ 创建失败：实体不存在，请先使用 create_entity 创建实体"
        return f"❌ 创建失败: {error_msg}"


# ==================== 图谱管理工具 ====================


@tool
async def get_graph_labels(limit: int = 50) -> str:
    """
    获取图谱中的热门标签（实体名称）。

    【适用场景】
    - 了解图谱中已有的主要实体
    - 确认某实体是否存在

    Args:
        limit: 返回数量，默认50，最多100

    Returns:
        标签列表

    Examples:
        get_graph_labels()
        get_graph_labels(20)
    """
    # 参数验证
    limit = max(1, min(limit, 100))

    try:
        labels = await creative_lightrag_client.get_popular_labels(limit)
        if labels:
            formatted = "\n".join(f"- {label}" for label in labels[:20])
            return f"二创图谱中的主要实体（共{len(labels)}个）：\n{formatted}"
        return "二创图谱暂无实体"

    except Exception as e:
        return f"❌ 获取标签失败: {str(e)}"


@tool
async def get_entity_subgraph(
    entity_name: str,
    max_depth: int = 2,
    graph_type: str = "creative",
) -> str:
    """
    获取以某实体为中心的知识图谱子图。

    【适用场景】
    - 查看实体周边的关系网络
    - 了解人物之间的关联

    Args:
        entity_name: 中心实体名称（必填）
        max_depth: 关系深度，默认2（可选）
        graph_type: 图谱类型（可选，默认 creative）

    Returns:
        子图信息

    Examples:
        get_entity_subgraph("孙悟空")
        get_entity_subgraph("唐僧", 3)
    """
    if not entity_name or not entity_name.strip():
        return "❌ 请提供实体名称"

    if graph_type not in VALID_GRAPH_TYPES:
        return "❌ 无效的图谱类型"

    max_depth = max(1, min(max_depth, 5))
    client = creative_lightrag_client if graph_type == "creative" else lightrag_client
    entity_name = entity_name.strip()

    try:
        result = await client.get_knowledge_graph(
            label=entity_name,
            max_depth=max_depth,
            max_nodes=50,
        )

        nodes = result.get("nodes", [])
        edges = result.get("edges", [])

        if not nodes:
            return f"❌ 未找到以「{entity_name}」为中心的图谱"

        output = [f"以「{entity_name}」为中心的图谱："]
        output.append(f"节点数: {len(nodes)}，关系数: {len(edges)}")

        if edges:
            output.append("\n主要关系：")
            for edge in edges[:10]:
                src = edge.get("src_id", "?")
                tgt = edge.get("tgt_id", "?")
                desc = edge.get("description", "")[:30]
                output.append(f"  {src} → {tgt}: {desc}")

        return "\n".join(output)

    except Exception as e:
        return f"❌ 获取图谱失败: {str(e)}"


# ==================== 工具集合 ====================

# 研究阶段使用的工具
RESEARCH_TOOLS = [
    query_material_graph,
    query_creative_graph,
    query_dual_graphs,
    check_entity_exists,
    get_graph_labels,
]

# 创作阶段使用的工具
WRITER_TOOLS = [
    query_material_graph,
    query_creative_graph,
    query_dual_graphs,
    save_to_creative_graph,
    check_entity_exists,
    get_entity_subgraph,
]

# 管理阶段使用的工具
MANAGEMENT_TOOLS = [
    create_entity,
    edit_entity,
    create_relation,
    save_to_creative_graph,
    get_graph_labels,
    get_entity_subgraph,
]

# 所有工具
ALL_GRAPH_TOOLS = [
    query_material_graph,
    query_creative_graph,
    query_dual_graphs,
    save_to_creative_graph,
    check_entity_exists,
    create_entity,
    edit_entity,
    create_relation,
    get_graph_labels,
    get_entity_subgraph,
]
