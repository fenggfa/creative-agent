# Claude Code 指令

> 此文件为 Claude Code CLI 提供特定执行指令。

## 执行原则

### CIVC 循环

```
Constrain(约束) → Inform(告知) → Verify(验证) → Correct(纠正)
```

1. **约束优先**：检查是否在允许范围内
2. **上下文注入**：确保了解 AGENTS.md 和约束规则
3. **验证后完成**：修改后必须运行 `uv run ruff check && uv run mypy && uv run pytest`
4. **自动纠错**：验证失败 → 分析 → 修复 → 再验证

## 代码风格

```python
# ✅ 正确
async def process(task: str) -> dict[str, Any]:
    """处理任务。"""
    ...

# ❌ 错误
def process(task):  # 缺少类型注解
    ...
```

## 验证检查清单

- [ ] `uv run ruff check src/` 通过
- [ ] `uv run mypy src/` 通过
- [ ] `uv run pytest tests/ -v` 通过

## 错误处理

- **约束违规**：查看 `suggestion` 修复
- **评估不通过**：查看 `improvement_suggestions` 改进
