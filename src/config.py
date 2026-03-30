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


# 全局配置实例
settings = Settings()
