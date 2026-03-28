# 质量评分

> 追踪技术债务，确保变更可安全回滚。

## 当前状态

| 指标 | 目标 | 当前 | 状态 |
|------|------|------|------|
| 测试覆盖率 | ≥80% | - | 待测量 |
| 类型覆盖 | 100% | - | 待测量 |
| Lint 错误 | 0 | - | 待测量 |
| 文档新鲜度 | ≤7天 | - | 待测量 |

## 黄金原则

### 1. Parse, don't validate
在边界处强制转换数据形状，拒绝隐式信任 LLM 输出。

```python
# ❌ 错误：隐式信任
data = llm_output["score"]

# ✅ 正确：显式解析
score = float(llm_output["score"])  # 强制类型转换
```

### 2. DRY (Don't Repeat Yourself)
严禁生成重复 Helper 函数，强制复用共享工具。

### 3. Explicit over Implicit
所有约定必须显式编码，压缩 AI 幻觉空间。

## 变更日志

| 日期 | 变更 | 影响 | 回滚命令 |
|------|------|------|----------|
| - | - | - | - |

## 回滚策略

```bash
# 查看最近变更
git log --oneline -5

# 回滚到上一版本
git revert HEAD

# 回滚到指定版本
git revert <commit-hash>
```
