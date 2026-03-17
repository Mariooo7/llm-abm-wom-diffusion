# 项目架构设计文档

**版本**: 0.6.1  
**日期**: 2026-03-13  
**技术栈**: Go 1.23 + Python 3.11 + Mesa 3.3

---

## 📋 架构概述

### 设计原则

1. **关注点分离**: Python 负责仿真流程与数据分析，Go 负责统一 LLM 调用网关
2. **松耦合**: 模块间接口清晰，可独立测试和替换
3. **研究语义优先**: 单次仿真保持随机异步更新，不在单步内改为同步并发
4. **工程优化受约束**: 只做不改变因果解释的优化（如多 repetition 并行调度）
5. **研究严谨性**: 采用单一路径决策，LLM 失败即中止并显式报错

### 架构图（目标）

```
┌──────────────────────────────────────────────────────────────┐
│                        实验控制层                              │
│                     (Python scripts/)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ run_pilot   │  │ run_batch   │  │ analyze     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      ABM 仿真层 (Python)                       │
│                   (python/models/)                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              DiffusionModel (Mesa)                   │    │
│  │  - 网络生成 (NetworkX)                               │    │
│  │  - 随机异步激活 (Model 内部调度)                     │    │
│  │  - 数据采集 (DataCollector)                          │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                              │
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                     LLM 决策层 (Go/HTTP)                       │
│  - 直连 Chat Completions 决策                                  │
│  - /decide 统一入口                                            │
│  - token 统计与返回                                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 🐍 Python 模块设计

### python/models/

**核心类**: `DiffusionModel(Model)`

```python
class DiffusionModel(Model):
    """Mesa ABM 模型"""
    
    def __init__(self, config: SimulationConfig)
    def step(self) -> None
    def get_metrics(self) -> dict
    def get_neighbors(self, agent_id: int) -> list[int]
    def get_adopted_neighbors(self, agent_id: int) -> list[int]
```

**职责**:
- 网络生成和管理
- 智能体调度和激活
- 数据采集和存储
- 仿真流程控制

### python/agents/

**核心类型**:
```python
@dataclass
class AgentProfile:
    agent_id: int
    openness: float
    risk_tolerance: float
    sharing_tendency: float

class Agent:
    def step(self) -> None
```

**职责**:
- 智能体个体画像初始化
- 按单一路径调用 LLM 决策
- 记录采纳时刻与 WOM 接收状态

### python/llm/

**核心类型**:
```python
class DecisionClient:
    def decide(self, req: DecisionRequest, context_key: str) -> DecisionResult
```

**职责**:
- 封装仿真侧决策请求与结果结构
- 作为调用 Go 统一入口的客户端层
- 统计模型调用与 token 消耗
- 在模型异常时抛出错误并中止仿真

### python/networks/

**核心函数**:
```python
def generate_network(
    network_type: str,
    n_nodes: int,
    avg_degree: int,
    seed: int | None
) -> nx.Graph

def compute_network_metrics(G: nx.Graph) -> dict
```

### data/results/（分析输入）

**核心功能**:
- 汇总索引：`batch_summary.csv`
- 单 run 指标：`metrics_*.json`
- 过程曲线：`adoption_timeline_*.csv`
- 批次事件日志：`batch_events.jsonl`

---

## 🦫 Go 模块设计

### go/cmd/

**主程序**:
```go
func main() {
    // 1. 读取配置
    // 2. 启动 /health 与 /decide
    // 3. 直连模型接口
    // 4. 返回决策与 token
}
```

---

## 🔌 模块间通信

### 当前实现状态（2026-03-10）

- Python 仿真已接入 `DecisionClient`，并在 `Agent.step` 中触发 LLM 决策。
- `DecisionClient` 通过 HTTP 调用 Go 的 `/decide` 入口，由 Go 网关直连执行模型调用。
- 默认启用 `gateway_autostart`，网关未启动时由 Python 自动拉起 Go 决策服务。
- 失败场景采用 fail-fast：返回错误并中止当前仿真，避免污染实验数据。
- 已移除前缀缓存补齐相关逻辑，避免额外 token 成本与解释噪声。

### 唯一通信路径: HTTP API

```go
// Go 启动 HTTP 服务
http.HandleFunc("/decide", handleDecision)
http.ListenAndServe("127.0.0.1:18080", nil)
```

```python
# Python 侧由 DecisionClient 统一调用 /decide
result = decision_client.decide(req, context_key)
```

---

## 📊 数据流

### 仿真流程

```
1. 加载配置 (YAML)
   ↓
2. 生成网络 (NetworkX)
   ↓
3. 初始化智能体 (Agent)
   ↓
4. For each step:
   4.0 若有已采纳者，先执行 WOM 传播（按分享倾向广播离线语料）
   4.1 激活智能体（随机异步顺序）
   4.2 获取邻居状态 (Network)
   4.3 通过 Go `/decide` 执行 LLM 决策
   4.4 更新状态 (Memory)
   4.5 采集数据 (DataCollector)
   ↓
5. 输出结果 (CSV/JSON)
   ↓
6. 分析可视化 (pandas/matplotlib)
```

### 数据格式

**原始数据** (`data/raw/simulation_{group}_{rep}.csv`):
```csv
step,agent_id,openness,risk_tolerance,adopted_ratio,emotion_arousal,innovation_coef,imitation_coef,wom_bucket,wom_count,probability,adopt_by_threshold,adopt_final,reasoning,source
0,0,0.51,0.42,0.0,0.2,0.002,0.08,strong_low,0,0.134,false,false,"当前风险感知偏高，先观望",llm_http_direct
0,1,0.63,0.56,0.17,0.2,0.002,0.08,strong_low,1,0.542,true,true,"邻居已有采纳，且我可接受风险，倾向尝试",llm_http_direct
1,0,0.51,0.42,0.17,0.2,0.002,0.08,strong_low,2,0.486,false,false,"仍低于阈值，继续等待",llm_http_direct
...
```

**聚合数据** (`data/processed/aggregated_{group}.csv`):
```csv
group,rep,final_adoption_rate,avg_adoption_time,peak_adoption_step
A,1,0.85,23.5,15
A,2,0.82,25.1,17
...
```

**指标数据** (`data/results/metrics.csv`):
```csv
group,mean_adoption_rate,std_adoption_rate,mean_adoption_time,mean_total_adopters
A,1.0,0.0,3.167333333333333,100.0
B,1.0,0.0,3.2333333333333334,100.0
C,1.0,0.0,3.1993333333333336,100.0
D,1.0,0.0,3.1959999999999997,100.0
```

---

## 🔒 配置管理

### 环境变量

```bash
# .env
LLM_PROVIDER=aliyun_bailian
LLM_API_KEY=sk-xxx
LLM_MODEL=qwen3.5-flash
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_TEMPERATURE=0.2
LLM_SEED=42

# 实验配置
EXPERIMENT_GROUP=A
N_REPETITIONS=15
USE_LLM=true
```

### 参数设计依据（为什么这样配）

1. `LLM_TEMPERATURE=0.2`
   - 目标是“可复核”和“跨次运行稳定”，不是创意写作。
   - 较低温度会显著减少答案漂移，便于把差异更多归因到实验条件，而不是采样随机性。
2. `LLM_SEED=42`
   - 在支持 seed 的模型实现中，能进一步降低同条件下的采样波动，增强复现实验一致性。
3. `N_REPETITIONS=15`
   - 与当前正式实验设计一致（4 组 × 15），总计 60 次。
   - 当参数校准后仍建议保持 15 次作为首轮统计基线，必要时再提升重复次数。

### 研究语义与工程优化边界

1. 单次仿真语义
   - 采用随机异步更新：每一步打乱顺序后逐个 Agent 决策。
   - 不进行“单步内并发同步决策”，避免改变扩散机制解释。
2. 工程优化策略
   - 允许并行运行多个 repetition，以缩短总墙钟时间。
   - 并行调度只作用于实验任务层，不改变单次 run 的决策顺序。
3. 参数管理原则
   - 系统运行参数（并发、重试、超时）以稳定为先，非必要不调整。
   - 研究参数（网络结构、情感强度、Bass 参数）按理论与文献约束校准。

### YAML 配置

```yaml
# experiments/configs/group_a.yaml
group: A
network:
  type: small_world
  n_nodes: 100
  avg_degree: 8
  rewiring_prob: 0.1

wom:
  strength: strong
  emotion_arousal: 0.8

bass:
  innovation_coef: 0.01
  imitation_coef: 0.3

simulation:
  n_steps: 60
  seed: 42
  n_repetitions: 15
  use_llm: true
  llm_sampling_ratio: 1.0
```

---

## 🎓 教学式源码解读

### 1) DiffusionModel 如何串起一次仿真

代码位置：`python/models/model.py`

```python
self.network = generate_network(...)
self.network_metrics = compute_network_metrics(self.network)
self._initialize_agents()
self.population = {...}
self.datacollector = DataCollector(...)
```

解读：
- 先生成网络，再创建智能体，最后挂载数据采集器，这是典型的 ABM 初始化顺序。
- Mesa 3.x 中 `Model.agents` 为框架保留字段，因此项目使用 `population` 存放自定义智能体。
- 每一步通过随机打乱 `population` 的键并逐个执行 `step`，达到随机激活效果。
- `DataCollector` 将模型级指标与个体级指标统一收集，为后续统计分析直接提供输入。

### 2) Agent.step 如何执行单一路径 LLM 决策

代码位置：`python/agents/agent.py`

```python
adopted_ratio = len(adopted_neighbors) / len(total_neighbors) if total_neighbors else 0.0
decision = self.model.decision_client.decide(req, self.model.context_key)
prob = decision.probability
```

解读：
- 每次智能体决策都通过 `DecisionClient` 请求 Go `/decide`，不存在本地启发式分支。
- `use_llm=true` 与 `llm_sampling_ratio=1.0` 被视为研究模式硬约束，配置不满足即抛错。
- 当 API 不可用或解析失败时立即抛错并中止仿真，避免继续产生无效数据。
- 决策客户端累计 `model_calls/prompt_tokens/completion_tokens/total_tokens`，用于成本统计。

### 3) 上下文缓存如何工作（阿里百炼前缀缓存）

代码位置：`go/cmd/main.go`

```go
systemContent := []map[string]any{
    {
        "type": "text",
        "text": buildDecisionInstruction(),
        "cache_control": map[string]any{"type": "ephemeral"},
    },
}
```

解读：
- 系统提示词会在显式缓存模式下改写为 content block，并打上 `cache_control` 标记。
- 网关对同一固定前缀重复请求时，模型侧会尽量复用缓存，减少重复前缀 token 计费。
- 通过响应中的 `usage.prompt_tokens_details.cached_tokens` 可观察缓存命中效果。

### 4) Token 消耗统计如何实现

代码位置：`go/cmd/main.go`

```go
type tokenUsageSummary struct {
    modelCalls       int
    promptTokens     int
    completionTokens int
    totalTokens      int
}
```

解读：
- 每次 `/decide` 调用会从响应 `usage` 中提取 prompt/completion/total 并写入统一返回。
- 网关会额外返回 `cached_tokens`，用于验证前缀缓存是否生效。
- 程序末尾会打印总量与每次调用平均值，便于你直接估算实验成本。

### 5) 学术化提示词工程如何落地

代码位置：`go/cmd/main.go`

```go
func buildDecisionInstruction() string {
    researchProtocol := strings.Join([]string{
        "研究协议固定前缀：",
        "1) 研究对象是新产品扩散中的普通消费者个体，不是研究员、顾问或营销文案作者。",
        "...",
        "18) 该前缀用于稳定实验语义边界，并作为可缓存公共前缀。",
    }, "\n")
    return strings.Join([]string{
        researchProtocol,
        "你正在模拟一名普通消费者在当前时间步是否采纳新产品。",
        "你会收到一个JSON对象，包含个体特质、社会影响和口碑信息。",
        "请仅输出JSON对象，字段必须是 adopt(boolean), probability(number), reasoning(string)。",
    }, "\n")
}
```

解读：
- 角色已改为“模拟消费者单步决策”，与研究设计文档中的微观行为主体一致。
- 固定前缀明确限制输出边界，避免模型漂移到“研究助理/策略顾问”语气。
- 固定前缀同时作为可复用公共前缀，配合阿里百炼显式缓存降低批量实验成本。

---

## 🧪 测试策略

### 单元测试

```python
# tests/test_model.py
def test_diffusion_model_initialization():
    config = get_config("A")
    model = DiffusionModel(config)
    
    assert len(model.population) == 200
    assert model.network.number_of_nodes() == 200
    assert model.current_step == 0
```

```go
// internal/agents/agent_test.go
func TestNewSimulationAgent(t *testing.T) {
    config := AgentConfig{ID: 1, Age: 30}
    agent, err := NewSimulationAgent(context.Background(), config, nil)
    
    if err != nil {
        t.Fatalf("Failed to create agent: %v", err)
    }
    if agent.Config.ID != 1 {
        t.Errorf("Expected ID 1, got %d", agent.Config.ID)
    }
}
```

### 集成测试

```python
# tests/test_integration.py
def test_full_simulation():
    config = get_config("A")
    model = DiffusionModel(config)
    
    while model.running:
        model.step()
    
    metrics = model.get_metrics()
    assert 0 < metrics["final_adoption_rate"] <= 1.0
```

---

## 📈 性能优化

### 优化策略

1. **批量 LLM 调用**: 多个智能体决策合并为一次 API 调用
2. **缓存机制**: 相同状态的决策结果缓存
3. **并行仿真**: 不同 repetition 并行运行
4. **网关稳态运行**: 统一 Go 服务配置与健康检查，避免路径分叉

### 性能目标

| 指标 | 目标 | 测量方式 |
|------|------|----------|
| 单次仿真时间 | < 5 分钟 | 200  agents, 100 steps |
| 批量实验时间 | < 2 小时 | 4 groups × 20 reps |
| LLM 调用延迟 | < 500ms | P95 latency |
| 内存占用 | < 1GB | Peak RSS |

---

## 🚨 风险管理

### 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| LLM API 不稳定 | 高 | 中 | 失败即中止并记录失败批次，后续补跑 |
| Go-Python 通信开销 | 中 | 中 | 本地调用 + 批量处理 |
| 仿真时间过长 | 高 | 低 | 并行化 + 性能优化 |

### 数据风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 结果不可复现 | 高 | 低 | 固定随机种子 + 版本控制 |
| 数据丢失 | 高 | 低 | 实时保存 + 断点续跑 |
| 异常值影响 | 中 | 中 | 统计检验 + 敏感性分析 |

---

*文档应随项目进展持续更新*
