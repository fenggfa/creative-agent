"""配置管理模块，使用 pydantic-settings 加载环境变量。"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从环境变量加载。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # MiniMax 大模型配置（从环境变量加载）
    LLM_BASE_URL: str = "https://api.minimax.chat/v1"
    LLM_API_KEY: SecretStr = SecretStr("")  # 必须从 .env 文件加载
    LLM_MODEL: str = "MiniMax-M2.7"

    # Obsidian 输出配置
    OBSIDIAN_VAULT: str = "/Users/fenggf/Documents/project/obsidain/book"
    CREATIVE_OUTPUT_DIR: str = "二创作品"

    # 工作流配置
    MAX_REVISIONS: int = 2

    # Neo4j 图数据库配置
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr = SecretStr("")

    # SQLite 实体词典配置
    ENTITY_INDEX_PATH: str = "data/entity_index.db"

    # 图谱构建配置
    ENTITY_TYPES: list[str] = ["character", "location", "item", "event", "concept"]

    # 图谱构建参数
    KG_CHUNK_SIZE: int = 1000  # 文档分块大小
    KG_CHUNK_OVERLAP: int = 100  # 分块重叠

    # RexUniNLU 本地信息抽取服务配置
    USE_LOCAL_EXTRACTOR: bool = True  # 是否使用本地 RexUniNLU 服务
    LLM_SERVER_URL: str = "http://localhost:8200"  # RexUniNLU HTTP 服务地址
    REX_MODEL_PATH: str = "/Users/fenggf/Documents/modle/LLM/nlp_deberta_rex-uninlu_chinese-base"

    # 嵌入服务配置
    EMBED_SERVER_URL: str = "http://localhost:8100"  # 嵌入服务地址
    EMBED_DIMENSION: int = 1024  # 向量维度
    ENABLE_VECTOR_SEARCH: bool = True  # 是否启用向量搜索

    # 知识图谱构建调试配置
    KG_DEBUG_MODE: bool = False  # 调试开关
    KG_TRACE_OUTPUT_DIR: str = "data/traces"  # 输出目录
    KG_TRACE_MAX_CONTENT_LENGTH: int = 500  # 内容截断长度


# 全局配置实例
settings = Settings()
