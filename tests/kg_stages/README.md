# 知识图谱构建分阶段测试

## 测试脚本说明

| 脚本 | 功能 | 运行命令 |
|------|------|----------|
| `test_1_parse.py` | 文档解析测试 | `python tests/kg_stages/test_1_parse.py` |
| `test_2_entities.py` | 实体提取测试 | `python tests/kg_stages/test_2_entities.py` |
| `test_3_relations.py` | 关系抽取测试 | `python tests/kg_stages/test_3_relations.py` |
| `test_all.py` | 运行所有阶段 | `python tests/kg_stages/test_all.py` |
| `view_results.py` | 查看中间结果 | `python tests/kg_stages/view_results.py` |
| `debug_llm.py` | 调试 LLM 服务 | `python tests/kg_stages/debug_llm.py` |
| `debug_relations.py` | 调试关系抽取 | `python tests/kg_stages/debug_relations.py` |

## 中间结果文件

运行测试后，结果保存在 `data/kg_stages/` 目录：

```
data/kg_stages/
├── 1_chunks.json    # 阶段1：文档分块
├── 2_entities.json  # 阶段2：提取的实体
└── 3_relations.json # 阶段3：抽取的关系
```

## 运行示例

```bash
# 单独运行某个阶段
python tests/kg_stages/test_1_parse.py
python tests/kg_stages/test_2_entities.py
python tests/kg_stages/test_3_relations.py

# 运行完整流程
python tests/kg_stages/test_all.py

# 查看结果
python tests/kg_stages/view_results.py
```

## 当前发现的问题

### 关系抽取返回 0 条

**原因**: `server/nlu_server.py` 中的关系抽取功能尚未实现，当前总是返回空数组。

**验证**:
```bash
python tests/kg_stages/debug_llm.py
```

查看输出，`relations` 字段始终为 `[]`。

**解决方案**: 需要在 `nlu_server.py` 中实现关系抽取逻辑。

## 测试数据

测试数据在 `test_1_parse.py` 中定义：

```python
TEST_DOCUMENT = """
孙悟空是花果山水帘洞的美猴王，他师从菩提祖师学习七十二变和筋斗云。
后来孙悟空大闹天宫，被如来佛祖压在五行山下五百年。
...
"""
```

可以修改此数据进行不同测试。
