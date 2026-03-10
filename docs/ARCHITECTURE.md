# 项目架构设计文档

**版本**: 0.4.3  
**日期**: 2026-03-10  
**技术栈**: Go 1.23 + Eino v0.7.13 + Python 3.11 + Mesa 3.3

---

## 📋 架构概述

### 设计原则

1. **关注点分离**: Python 负责仿真流程与数据分析，Go(Eino)负责统一 LLM 调用
2. **松耦合**: 模块间接口清晰，可独立测试和替换
3. **性能优先**: 计算密集型用 Go，数据分析用 Python
4. **研究严谨性**: 采用单一路径决策，LLM 失败即中止并显式报错

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
│  │  - 智能体调度 (Scheduler)                            │    │
│  │  - 数据采集 (DataCollector)                          │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                              │
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                     LLM 决策层 (Go/Eino)                      │
│  - ChatModelAgent 决策                                        │
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
- 作为调用 Go(Eino) 统一入口的客户端层
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

### python/analysis/

**核心功能**:
- 扩散曲线拟合 (Bass 模型)
- 统计检验 (ANOVA, t-test)
- 效应量计算 (Cohen's d, η²)
- 可视化 (matplotlib/seaborn)

---

## 🦫 Go 模块设计

### go/internal/agents/

**核心类型**:
```go
type AgentConfig struct {
    ID              int
    Age             int
    Openness        float64
    Extraversion    float64
    RiskTolerance   float64
    // ...
}

type SimulationAgent struct {
    Config  AgentConfig
    Memory  *AgentMemory
    Runner  *adk.Runner
}
```

**职责**:
- 智能体画像管理
- 记忆状态维护
- LLM 决策服务与工具编排调用

### go/internal/tools/

**核心工具**:

1. **DiffusionTool**: 采纳决策分析
2. **SentimentTool**: 情感分析
3. **NetworkTool**: 网络指标计算 (可选)

```go
type DiffusionTool struct{}

func (t *DiffusionTool) Analyze(
    ctx context.Context, 
    input DiffusionInput
) (*DiffusionOutput, error)

func (t *DiffusionTool) ToTool() (tool.BaseTool, error)
```

### go/cmd/

**主程序**:
```go
func main() {
    // 1. 初始化 LLM
    // 2. 注册工具
    // 3. 创建智能体
    // 4. 运行仿真
    // 5. 输出结果
}
```

---

## 🔌 模块间通信

### 当前实现状态（2026-03-10）

- Python 仿真已接入 `DecisionClient`，并在 `Agent.step` 中触发 LLM 决策。
- `DecisionClient` 通过 HTTP 调用 Go(Eino) 的 `/decide` 入口，由 Eino 统一执行模型调用。
- 默认启用 `gateway_autostart`，网关未启动时由 Python 自动拉起 Go 决策服务。
- 失败场景采用 fail-fast：返回错误并中止当前仿真，避免污染实验数据。

### 唯一通信路径: HTTP API

```go
// Go 启动 HTTP 服务
http.HandleFunc("/decide", handleDecision)
http.ListenAndServe(":8080", nil)
```

```python
# Python HTTP 调用
import requests

def call_llm_decision(agent_state: dict) -> dict:
    response = requests.post(
        "http://localhost:8080/decide",
        json=agent_state
    )
    return response.json()
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
   4.1 激活智能体 (Scheduler)
   4.2 获取邻居状态 (Network)
   4.3 通过 Go `/decide` 执行 LLM 决策
   4.4 更新状态 (Memory)
   4.5 生成 WOM (LLM/Template)
   4.6 传播 WOM (Network)
   4.7 采集数据 (DataCollector)
   ↓
5. 输出结果 (CSV/JSON)
   ↓
6. 分析可视化 (pandas/matplotlib)
```

### 数据格式

**原始数据** (`data/raw/simulation_{group}_{rep}.csv`):
```csv
step,agent_id,has_adopted,adoption_time,wom_count,neighbor_adopted_ratio
0,0,False,,0,0.0
0,1,False,,0,0.0
1,0,True,1,2,0.15
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
LLM_MAX_TOKENS=700
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
2. `LLM_MAX_TOKENS=700`
   - 当前任务是“扩散风险 + 指标建议”的结构化短答，不需要长篇叙述。
   - 700 的上限可覆盖：结论、机制解释、指标列表、少量工具结果整合。
   - 该值同时控制单次调用成本与响应时延，减少批量实验中的 token 爆炸风险。
3. `LLM_SEED=42`
   - 在支持 seed 的模型实现中，能进一步降低同条件下的采样波动，增强复现实验一致性。
4. `N_REPETITIONS=15`
   - 与当前正式实验设计一致（4 组 × 15），总计 60 次。
   - 当参数校准后仍建议保持 15 次作为首轮统计基线，必要时再提升重复次数。

### `LLM_MAX_TOKENS=700` 会不会太少？

- 对当前指令模板与输出格式而言，一般不会太少。
- 如果出现以下信号，应提高到 900~1200：
  - 频繁出现截断或未完成结尾；
  - 工具调用后需要返回较长结构化列表；
  - 新增多段比较解释（例如跨组机制对照）。
- 如果只是常规决策解释，维持 700 更有利于成本和吞吐。

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

### 3) DiffusionTool.ToTool 为什么是桥接点

代码位置：`go/internal/tools/diffusion_tool.go`

```go
func (t *DiffusionTool) ToTool() (tool.BaseTool, error) {
    return utils.InferTool("analyze_diffusion", "分析产品扩散决策，返回采纳概率和原因", t.Analyze)
}
```

解读：
- `Analyze` 是业务逻辑函数，`ToTool` 把它转换成 Eino 可调用工具。
- 这样 Agent 只需关心“调用哪个工具”，不用关心参数解析和序列化细节。
- 该封装方式有利于保持 Go 侧决策接口稳定，并支撑统一入口演进。

### 4) 上下文缓存如何工作（阿里百炼前缀缓存 + 会话变量）

代码位置：`go/cmd/main.go`

```go
cache := newPromptCache()
sessionValues := cache.getOrBuild("pilot_a_context")
opts := []adk.AgentRunOption{
    adk.WithSessionValues(sessionValues),
    adk.WithChatModelOptions(buildModelOptions(cfg)),
}
```

解读：
- `WithSessionValues` 仍保留为模板变量注入机制，用于研究边界等固定字段复用。
- 真正的 LLM 前缀缓存由 `buildModelOptions(cfg)` 注入 `WithRequestPayloadModifier` 完成。
- 在请求发往阿里百炼前，会把 system message 的 `content` 改写为多段结构，并加上 `cache_control: {"type":"ephemeral"}`。
- 这会触发显式前缀缓存：首次创建缓存，后续同前缀命中缓存并降低输入 token 成本。

### 5) Token 消耗统计如何实现

代码位置：`go/cmd/main.go`

```go
type tokenUsageSummary struct {
    modelCalls       int
    promptTokens     int
    completionTokens int
    totalTokens      int
}

func collectTokenUsage(event *adk.AgentEvent, summary *tokenUsageSummary) {
    if event == nil || event.Output == nil || event.Output.MessageOutput == nil {
        return
    }
    msg, err := event.Output.MessageOutput.GetMessage()
    if err != nil || msg == nil || msg.ResponseMeta == nil {
        return
    }
    summary.add(msg.ResponseMeta.Usage)
}
```

解读：
- Eino 的消息对象会在 `ResponseMeta.Usage` 返回模型侧 token 用量（取决于供应商是否回传）。
- 运行过程中逐事件累加，得到：
  - `input_tokens`（prompt tokens）
  - `output_tokens`（completion tokens）
  - `total_tokens`
  - `model_calls`
- 程序末尾会打印总量与每次调用平均值，便于你直接估算实验成本。

### 6) 学术化提示词工程如何落地

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
