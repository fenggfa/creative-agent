# Creative Agent

多智能体创意写作系统，基于 LangGraph 编排 + Neo4j 知识图谱。

## 项目架构

```
src/
├── main.py              # CLI 入口
├── config.py            # 配置管理
├── agents/              # 智能体
│   ├── researcher.py    # 研究师：检索素材
│   ├── writer.py        # 创作师：单篇创作
│   ├── reviewer.py      # 审核师：单篇审核
│   ├── director.py      # 总监制：统筹整书流程
│   ├── plot_architect.py # 故事架构师：生成大纲
│   ├── prose_writer.py  # 风格写稿师：撰写正文
│   ├── critic.py        # 批评审核师：评估质量
│   └── kg_builder.py    # 知识图谱构建师
├── workflow/            # 工作流编排
│   ├── orchestrator.py  # LangGraph 状态机
│   └── state.py         # 状态定义
├── tools/               # 工具模块
│   ├── kg_storage/      # 知识图谱存储 (Neo4j + SQLite FTS5)
│   ├── kg_extractor/    # 知识提取 (文档解析、实体提取、关系抽取)
│   ├── graph_service.py # 图谱服务
│   └── continuity.py    # 连贯性工具
├── harness/             # Harness Engineering
│   ├── provider.py      # 约束注入
│   ├── retry.py         # 重试机制
│   ├── learning.py      # 自我进化
│   └── agent_memory.py  # 经验记忆
├── feedback/            # 反馈工程
│   └── evaluator.py     # 五维评估器
├── output/              # 输出模块
│   └── __init__.py      # 保存到 Obsidian + 知识图谱
└── persistence/         # 持久化
    └── __init__.py      # 状态持久化
```

## 工作流模式

### 单篇模式

```
START → researcher → writer → reviewer → output → END
                            ↑          │
                            └──────────┘ (审核不通过时修改)
```

### 整书模式

```
START → director → plot_architect → [章节循环] → output → END
                                      ↓
                     ┌────────────────────────────────┐
                     │ plot_architect (细纲)          │
                     │ → prose_writer (撰写)          │
                     │ → critic (审核)                │
                     │ → save_chapter (保存+状态更新)  │
                     └────────────────────────────────┘
```

## 快速开始

### 1. 环境准备

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e .
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# LLM 配置 (必需)
LLM_BASE_URL=https://api.minimax.chat/v1
LLM_API_KEY=your-api-key-here
LLM_MODEL=MiniMax-M2.7

# Neo4j 图数据库 (必需)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# Obsidian 输出路径 (可选，默认已配置)
OBSIDIAN_VAULT=/path/to/your/obsidian/vault
CREATIVE_OUTPUT_DIR=二创作品
```

### 3. 启动 Neo4j

```bash
# Docker 方式 (推荐)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 访问 Web 界面: http://localhost:7474
```

### 4. 运行工作流

```bash
# 单篇创作模式
uv run python -m src.main "写一段孙悟空大闹天宫的故事"

# 使用工具调用模式 (LLM 自动选择工具)
uv run python -m src.main --tools "基于西游记素材写一段二创故事"

# 上传文档构建知识图谱
uv run python -m src.main --upload docs/西游记.txt --book 西游记
uv run python -m src.main --upload docs/二创.txt --book 西游记 --source creative

# 查询知识图谱
uv run python -m src.main --query "孙悟空的武器是什么"
uv run python -m src.main --query "孙悟空的朋友" --book 西游记

# 列出所有知识图谱
uv run python -m src.main --list
```

### 5. 运行测试

```bash
# 完整验证 (推荐)
uv run ruff check src/ && uv run mypy src/ && uv run pytest tests/ -v

# 仅运行测试
uv run pytest tests/ -v
```

## 智能体说明

| 智能体 | 模式 | 职责 |
|--------|------|------|
| researcher | 单篇 | 从知识图谱检索素材 |
| writer | 单篇 | 根据素材创作内容 |
| reviewer | 单篇 | 审核内容质量 |
| director | 整书 | 统筹全书创作流程 |
| plot_architect | 整书 | 生成整书大纲和章节细纲 |
| prose_writer | 整书 | 根据大纲撰写正文 |
| critic | 整书 | 评估内容质量、一致性 |
| kg_builder | 通用 | 将文档转化为知识图谱 |

## 知识图谱功能

### 构建知识图谱

```python
from src.agents.kg_builder import build_knowledge_graph

# 从文档构建知识图谱
result = await build_knowledge_graph(
    document="文档内容...",
    book="西游记",
    source="material",  # material 或 creative
)
print(f"提取 {len(result.entities)} 实体, {len(result.relations)} 关系")
```

### 查询知识图谱

```python
from src.tools.kg_storage import LocalKGService

service = LocalKGService()
await service.connect()

# 搜索实体
entities = await service.search_entities("孙悟空", book="西游记")

# 查询子图
subgraph = await service.query_subgraph("孙悟空", book="西游记", max_depth=2)

# 问答
answer = await service.query("孙悟空的武器是什么？", book="西游记")
```

## Harness Engineering

### 三大支柱

| 支柱 | 模块 | 说明 |
|------|------|------|
| 上下文工程 | `AGENTS.md` | 渐进式披露，按需加载知识树 |
| 约束工程 | `harness/provider.py` | 解析 MD 文件并注入约束规则 |
| 反馈工程 | `feedback/evaluator.py` | 五维评估 + 学习闭环 |

### 自我进化能力

```
Agent犯错 → analyze_violations() → 提取模式
                ↓
         propose_rules() → 提议新规则
                ↓
         sync_to_agents_md() → 更新约束文件
                ↓
         provider.reload() → 下次自动生效
```

## 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_BASE_URL` | `https://api.minimax.chat/v1` | LLM API 地址 |
| `LLM_MODEL` | `MiniMax-M2.7` | 模型名称 |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j 连接地址 |
| `NEO4J_USER` | `neo4j` | Neo4j 用户名 |
| `NEO4J_PASSWORD` | - | Neo4j 密码 |
| `ENTITY_INDEX_PATH` | `data/entity_index.db` | SQLite 索引路径 |
| `OBSIDIAN_VAULT` | - | Obsidian 库路径 |
| `MAX_REVISIONS` | `2` | 最大修改次数 |

## CLI 命令详解

```bash
# 查看帮助
uv run python -m src.main --help

# 创作模式
uv run python -m src.main "创作任务描述"
uv run python -m src.main "写一段孙悟空的故事" --tools

# 上传文档模式
uv run python -m src.main --upload <文件路径> --book <书名> [--source material|creative]

# 查询模式
uv run python -m src.main --query <问题> [--book <书名>]

# 列表模式
uv run python -m src.main --list
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `task` | 创作任务描述（位置参数） |
| `--tools` | 创作模式：启用工具调用 |
| `--upload FILE` | 上传文档并构建知识图谱 |
| `--book NAME` | 书名（上传/查询模式） |
| `--source TYPE` | 来源类型：material（素材）/ creative（二创） |
| `--query QUESTION` | 查询知识图谱 |
| `--list` | 列出所有知识图谱统计 |

## 开发命令

```bash
# 代码检查
uv run ruff check src/

# 类型检查
uv run mypy src/

# 运行测试
uv run pytest tests/ -v

# 完整验证
uv run ruff check src/ && uv run mypy src/ && uv run pytest tests/ -v
```

## 依赖说明

核心依赖：
- `langgraph` - 工作流编排
- `langchain-openai` - LLM 调用
- `neo4j` - 图数据库
- `aiosqlite` - 异步 SQLite
- `pydantic` - 数据验证
- `pydantic-settings` - 配置管理
