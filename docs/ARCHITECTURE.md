# 项目架构设计文档

**版本**: 0.1.0  
**日期**: 2026-03-02  
**技术栈**: Go 1.23 + Eino v0.7 + Python 3.11 + Mesa 3.3

---

## 📋 架构概述

### 设计原则

1. **关注点分离**: Go 负责 LLM 智能体决策，Python 负责 ABM 仿真流程
2. **松耦合**: 模块间接口清晰，可独立测试和替换
3. **性能优先**: 计算密集型用 Go，数据分析用 Python
4. **可扩展**: 支持从纯启发式到全 LLM 的平滑过渡

### 架构图

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
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   启发式决策 (Python)     │    │   LLM 决策 (Go/Eino)      │
│  (快速、可复现)          │    │  (真实、复杂)            │
│  - Bass 模型             │    │  - ChatModelAgent        │
│  - 阈值规则              │    │  - Tool 系统              │
│  - 概率采样              │    │  - 中断/恢复             │
└──────────────────────────┘    └──────────────────────────┘
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
- LLM 决策调用

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

### 方案 1: 本地调用 (推荐初期)

```python
# Python 调用 Go 二进制
import subprocess

def call_llm_decision(agent_state: dict) -> dict:
    result = subprocess.run(
        ["go-agent-decision"],
        input=json.dumps(agent_state),
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)
```

### 方案 2: gRPC (推荐后期)

```protobuf
// proto/agent.proto
service AgentService {
    rpc Decide(DecisionRequest) returns (DecisionResponse);
    rpc GenerateWOM(WOMRequest) returns (WOMResponse);
}
```

### 方案 3: HTTP API (折中方案)

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
   4.3 决策:
       - 启发式 (Python) 或
       - LLM (Go/RPC)
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
group,mean_adoption_rate,std_adoption_rate,mean_adoption_time,hypothesis_support
A,0.84,0.03,24.2,H1:Yes,H2:Yes,H3:Yes
B,0.65,0.05,35.8,H1:Yes,H2:No,H3:Partial
...
```

---

## 🔒 配置管理

### 环境变量

```bash
# .env
LLM_PROVIDER=dashscope
LLM_API_KEY=sk-xxx
LLM_MODEL=qwen3.5-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 实验配置
EXPERIMENT_GROUP=A
N_REPETITIONS=20
USE_LLM=false  # true=使用 LLM, false=使用启发式
```

### YAML 配置

```yaml
# experiments/configs/group_a.yaml
group: A
network:
  type: small_world
  n_nodes: 200
  avg_degree: 8
  rewiring_prob: 0.1

wom:
  strength: strong
  emotion_arousal: 0.8

bass:
  p: 0.01
  q: 0.3

simulation:
  n_steps: 100
  seed: 42
  repetitions: 20
```

---

## 🧪 测试策略

### 单元测试

```python
# tests/test_model.py
def test_diffusion_model_initialization():
    config = get_config("A")
    model = DiffusionModel(config)
    
    assert len(model.agents) == 200
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
4. **渐进式 LLM**: 初期用启发式，关键阶段用 LLM

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
| LLM API 不稳定 | 高 | 中 | 降级到启发式 + 重试机制 |
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
