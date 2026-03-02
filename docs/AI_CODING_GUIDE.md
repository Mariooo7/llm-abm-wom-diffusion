# AI 辅助编程指南

**项目**: 毕业论文仿真实验  
**版本**: 0.1.0  
**最后更新**: 2026-03-02

---

## 📋 使用原则

### 核心原则

1. **依据事实** - 所有代码必须基于实验设计文档和已验证的理论
2. **降低幻觉** - 不确定的内容必须标注 TODO 或询问确认
3. **最佳实践** - 遵循 Python 最佳实践和项目规范
4. **可追溯性** - 关键决策需要注释说明来源

### 禁止行为

❌ 不要编造 API 接口或函数签名  
❌ 不要假设未定义的参数或配置  
❌ 不要跳过测试直接实现功能  
❌ 不要忽略错误处理  

---

## 📚 关键文档索引

### 实验设计

| 文档 | 位置 | 用途 |
|------|------|------|
| 实验设计流程 | `../../04_实验设计/实验设计与分析流程_v1.0.md` | 实验参数、流程、假设 |
| 文献综述 | `../../02_文献综述/文献综述_v1.0.md` | 理论基础、假设推导 |
| 阅读笔记 | `../../03_阅读笔记/阅读笔记索引.md` | 核心文献、关键发现 |

### 技术规范

| 文档 | 位置 | 用途 |
|------|------|------|
| 技术栈调研 | `../../毕业论文_技术栈调研与执行计划.md` | 框架选择、实现方案 |
| 执行计划 | `../../毕业论文_仿真实验详细执行计划_v1.0.md` | 详细步骤、时间安排 |
| 用户画像 | `../../用户画像报告.md` | 智能体画像设计 |

---

## 🏗️ 项目结构

```
thesis-simulation/
├── src/
│   ├── agents/          # 智能体模块
│   │   ├── agent.py    # Agent 类 (Profile + Memory)
│   │   └── ...
│   ├── networks/        # 网络生成模块
│   │   ├── generator.py # 网络生成函数
│   │   └── ...
│   ├── simulation/      # 仿真核心 (TODO)
│   ├── analysis/        # 数据分析 (TODO)
│   └── config/          # 配置管理
├── tests/               # 测试代码
├── scripts/             # 运行脚本
└── data/                # 数据目录
```

---

## 🔧 开发任务清单

### 阶段 1: 核心框架 (本周)

- [ ] **Agent 模块** (已完成 ✅)
  - [x] AgentProfile 数据类
  - [x] AgentMemory 数据类
  - [x] Agent 主类
  - [ ] LLM 集成 (待实现)

- [ ] **Network 模块** (已完成 ✅)
  - [x] 小世界网络生成
  - [x] 随机网络生成
  - [x] 网络指标计算
  - [ ] 网络可视化 (待实现)

- [ ] **Simulation 模块** (待实现)
  - [ ] Mesa Model 类
  - [ ] Agent 调度器
  - [ ] 数据采集器
  - [ ] 批量运行器

### 阶段 2: 实验实现 (下周)

- [ ] **预实验** (单组单次)
  - [ ] 配置加载
  - [ ] 网络生成
  - [ ] 智能体初始化
  - [ ] 仿真运行
  - [ ] 结果保存

- [ ] **正式实验** (4 组×20 次)
  - [ ] 批量运行脚本
  - [ ] 进度跟踪
  - [ ] 错误处理
  - [ ] 断点续跑

### 阶段 3: 分析可视化 (第 3 周)

- [ ] **数据处理**
  - [ ] 原始数据清洗
  - [ ] 指标计算
  - [ ] 数据聚合

- [ ] **可视化**
  - [ ] 扩散曲线图
  - [ ] 网络对比图
  - [ ] 交互效应图

- [ ] **统计检验**
  - [ ] 方差分析 (ANOVA)
  - [ ] 事后检验
  - [ ] 效应量计算

---

## 💬 与 AI 协作的最佳实践

### 提问模板

**实现功能**:
```
请实现 [模块/函数名]，功能是 [描述]。

参考文档：
- [文档路径]
- [关键参数/要求]

注意事项：
- [特殊要求]
- [边界条件]
```

**调试问题**:
```
代码出现错误：
[错误信息]

相关代码：
[代码片段]

已尝试：
- [尝试 1]
- [尝试 2]

预期行为：[描述]
实际行为：[描述]
```

**代码审查**:
```
请审查以下代码：
[代码]

关注点：
- 是否符合实验设计
- 是否有潜在 bug
- 是否有优化空间
- 是否需要补充测试
```

### 验证清单

AI 生成的代码必须经过以下验证：

- [ ] 参数与实验设计文档一致
- [ ] 边界条件已处理
- [ ] 错误处理完善
- [ ] 有单元测试覆盖
- [ ] 代码注释清晰
- [ ] 性能可接受

---

## 📝 编码规范

### 命名规范

```python
# 类：大驼峰
class AgentProfile:
    pass

# 函数/变量：小写 + 下划线
def generate_network():
    n_agents = 200

# 常量：大写 + 下划线
DEFAULT_N_AGENTS = 200

# 私有：前缀下划线
def _internal_helper():
    pass
```

### 注释规范

```python
def calculate_adoption_probability(
    agent: Agent,
    neighbors: list[int],
    config: SimulationConfig,
) -> float:
    """
    计算智能体采纳概率.
    
    基于 Bass 模型和社交影响理论：
    P(adopt) = p + q * (adopted_neighbors / total_neighbors)
    
    Args:
        agent: 当前智能体
        neighbors: 邻居智能体 ID 列表
        config: 仿真配置
        
    Returns:
        采纳概率 (0-1)
        
    References:
        - Bass (1969): A New Product Growth for Model Consumer Durables
        - 实验设计文档 Section 2.3.1
    """
    pass
```

### 测试规范

```python
def test_generate_small_world_network():
    """测试小世界网络生成。"""
    G = generate_small_world(n_nodes=200, avg_degree=8, seed=42)
    
    # 验证节点数
    assert G.number_of_nodes() == 200
    
    # 验证平均度数接近目标值
    avg_degree = sum(dict(G.degree()).values()) / G.number_of_nodes()
    assert 7.5 <= avg_degree <= 8.5
    
    # 验证连通性
    assert nx.is_connected(G)
```

---

## 🚨 常见问题

### Q: 如何处理 LLM API 调用失败？

A: 实现重试机制和降级策略：
```python
@retry(max_attempts=3, delay=1.0)
def call_llm(prompt: str) -> str:
    try:
        return llm_client.generate(prompt)
    except APIError:
        logger.warning("LLM API failed, using heuristic fallback")
        return heuristic_decision(prompt)
```

### Q: 如何确保仿真可复现？

A: 严格管理随机种子：
```python
def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    # 如果使用 PyTorch/TensorFlow
    # torch.manual_seed(seed)
```

### Q: 如何处理大规模批量实验？

A: 使用断点续跑和并行处理：
```python
# 保存进度
def save_checkpoint(group: str, completed: list[int]) -> None:
    with open(f"checkpoint_{group}.json", "w") as f:
        json.dump({"completed": completed}, f)

# 恢复进度
def load_checkpoint(group: str) -> list[int]:
    try:
        with open(f"checkpoint_{group}.json", "r") as f:
            return json.load(f)["completed"]
    except FileNotFoundError:
        return []
```

---

## 📞 需要人工确认的事项

以下情况必须停止并询问用户：

1. ⚠️ 实验参数变更 (N、T、p、q 等)
2. ⚠️ 网络生成算法选择
3. ⚠️ LLM Prompt 设计
4. ⚠️ 统计检验方法选择
5. ⚠️ 可视化图表类型
6. ⚠️ 性能优化方案 (可能影响结果)

---

*本指南应随项目进展持续更新*
