# 毕业论文仿真实验项目

**论文题目**: 基于大模型智能体的新产品扩散机制研究：网络结构与口碑语义的交互效应

**英文名称**: LLM-Agent-Based New Product Diffusion Simulation

**技术栈**: Go(HTTP 网关) + Python (Mesa) 混合架构

---

## 📋 项目简介

本项目采用 **Go + Python 混合架构** 进行基于大语言模型 (LLM) 的智能体新产品扩散仿真实验：

- **Go (HTTP 网关)**: LLM 决策调用、重试退避、Token 统计
- **Python (Mesa 框架)**: ABM 仿真主流程、网络生成、数据分析
- **混合架构优势**: Go 的类型安全 + Python 的科学生态

### 核心研究问题

| 编号 | 问题 | 对应假设 |
|------|------|----------|
| RQ1 | 网络结构如何影响新产品扩散速度？ | H1 |
| RQ2 | 口碑语义如何影响扩散规模？ | H2 |
| RQ3 | 网络结构与口碑语义是否存在交互效应？ | H3 |

### 实验设计

**2×2 因子设计**:
- **自变量 1**: 网络结构 (小世界网络 vs 随机网络)
- **自变量 2**: 口碑语义 (强情感 vs 弱情感)
- **因变量**: 扩散速度、扩散规模、扩散曲线

---

## 🏗️ 项目结构

```
thesis-diffusion-simulation/
├── python/                     # Python ABM 仿真模块
│   ├── models/                 # Mesa 模型定义
│   │   ├── __init__.py
│   │   └── model.py           # DiffusionModel
│   ├── networks/               # 网络生成 (NetworkX)
│   ├── llm/                    # LLM 决策客户端
│   ├── config/                 # 配置解析
│   └── requirements.txt        # Python 依赖
│
├── go/                         # Go LLM 网关模块
│   ├── cmd/
│   │   └── main.go            # /decide HTTP 服务入口
│   └── go.mod                 # Go 模块配置
│
├── experiments/                # 实验配置
│   └── configs/               # 实验配置文件
│
├── data/                       # 数据目录
│   ├── raw/                   # 原始仿真数据
│   ├── processed/             # 处理后的数据
│   └── results/               # 分析结果
│
├── docs/                       # 文档
│   ├── AI_CODING_GUIDE.md     # AI 辅助编程指南
│   └── ARCHITECTURE.md        # 架构设计文档
│
├── scripts/                    # 运行脚本
│   ├── run_pilot.sh           # 预实验脚本
│   └── run_batch.sh           # 批量实验脚本
│
├── README.md                   # 项目说明
└── .gitignore                  # Git 忽略文件
```

---

## 🚀 快速开始

### 环境要求

- **Python**: 3.11+
- **Go**: 1.23+ (可选，仅用于 LLM 智能体)
- **uv** (推荐) 或 pip

### Python 环境安装

```bash
# 进入 Python 目录
cd thesis-diffusion-simulation/python

# 使用 uv (推荐)
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 或使用 pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Go 环境安装

```bash
# 安装 Go (macOS)
brew install go@1.23

# 进入 Go 目录
cd thesis-diffusion-simulation/go

# 下载依赖
go mod download
go mod tidy
```

### API Key 配置

```bash
cd thesis-diffusion-simulation
cp .env.example .env
```

将 `.env` 中的 `LLM_API_KEY` 填写为你的实际密钥。
模型相关配置（provider/model/base_url/temperature/timeout）统一在 `.env` 管理；实验调度参数统一由脚本默认值或命令行覆盖。

### 一键运行当前正式实验

Linux / macOS:

```bash
cd thesis-diffusion-simulation
bash scripts/run_batch.sh
```

Windows PowerShell:

```powershell
cd thesis-diffusion-simulation
$runTag = "formal_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$env:REPETITION_WORKERS="4"
$env:TIMEOUT_SECONDS="210"
$env:RUN_RETRIES="2"
$env:RETRY_BACKOFF_SECONDS="3"
$env:LLM_MAX_INFLIGHT="50"
uv run python python/run_preflight.py --mode formal_batch --groups A B C D --repetitions 15 --seed-start 12001 --repetition-workers 4 --run-retries 2 --retry-backoff-seconds 3 --timeout-seconds 210 --log-interval 10 --output-dir "data/results/$runTag" --raw-dir "data/raw/$runTag" --summary-file "data/results/$runTag/batch_summary.csv"
```

可选运行时覆盖变量（建议在命令行设置，不建议写入 `.env`）:

```bash
REPETITION_WORKERS=4
TIMEOUT_SECONDS=210
RUN_RETRIES=2
RETRY_BACKOFF_SECONDS=3
LLM_MAX_INFLIGHT=50
LLM_DECISION_RETRY_ATTEMPTS=2
LLM_DECISION_RETRY_BACKOFF_SECONDS=1
UI_REFRESH_SECONDS=1
```

运行完成后，结果默认落在带时间戳目录中：
- `data/results/formal_时间戳/batch_summary.csv`
- `data/results/formal_时间戳/metrics_*.json`
- `data/results/formal_时间戳/adoption_timeline_*.csv`
- `data/results/formal_时间戳/batch_events.jsonl`
- `data/raw/formal_时间戳/simulation_*.csv`

`formal_batch` 运行中会每秒刷新终端看板，实时显示总览与分组进度：
- 总览：`queued / running / retrying / done / failed`
- 分组：每组完成数、步数进度条、`Rate μ/max`、`Calls(done)`、活跃任务数与失败数
- 活跃任务：最多显示 4 条，包含 `group/rep/seed/step/rate/try`
- 默认使用 Rich Live 原地刷新，不刷屏；若非交互终端会自动回退 `compact` 摘要输出
- 当前并发建议：`REPETITION_WORKERS=4` 作为稳定默认值；继续提高通常会增加长尾抖动

run 内部默认启用“失败点续跑”（单步决策级重试）：
- 当某个 agent 决策调用出现可重试错误时，优先在当前 step 内局部重试
- 仅在局部重试耗尽后，才触发 run 级重试

### 运行单次快速验证（可选）

```bash
# Python: 运行预实验（统一入口）
cd thesis-diffusion-simulation
bash scripts/run_pilot.sh

# Go: 运行 LLM 智能体测试 (需要配置 API Key)
cd thesis-diffusion-simulation/go
export LLM_API_KEY="your-api-key"
go run cmd/main.go
```

---

## 📦 核心依赖

### Python

| 包 | 版本 | 用途 |
|----|------|------|
| mesa | 3.3.1 | ABM 仿真框架 |
| networkx | 3.6.1 | 网络生成与分析 |
| numpy | 2.4.2 | 数值计算 |
| pandas | 3.0.1 | 数据处理 |
| matplotlib | 3.10.8 | 数据可视化 |
| seaborn | 0.13.2 | 统计可视化 |
| scipy | 1.17.1 | 统计检验 |

### Go

| 包 | 版本 | 用途 |
|----|------|------|
| 标准库 net/http | go1.23 | OpenAI 兼容接口调用与网关服务 |

---

## 🧪 实验配置

### 默认参数

| 参数 | 值 | 说明 |
|------|-----|------|
| N | 100 | 智能体数量 |
| T | 60 | 仿真步数 |
| p | 0.003 | 创新系数 (Bass 模型，四组一致) |
| q(强组) | 0.12 | 模仿系数 (A/C) |
| q(弱组) | 0.095 | 模仿系数 (B/D) |
| emotion_arousal(强组) | 0.25 | 口碑情绪唤醒度 (A/C) |
| emotion_arousal(弱组) | 0.10 | 口碑情绪唤醒度 (B/D) |
| K | 6 | 网络平均度数 |
| repetitions | 15 | Monte Carlo 重复次数 |

### Bass 创新项的实现说明
- 初始创新者：按 `round(N * p)` 设定，且当 `p > 0` 时至少为 1
- 目的：对应 Bass 模型中“外生创新者”的含义，避免早期完全没有采纳导致 WOM 无法传播

### 实验组

| 组别 | 网络结构 | 口碑语义 | 预期效果 |
|------|----------|----------|----------|
| A | 小世界 | 强情感 | 高扩散 |
| B | 小世界 | 弱情感 | 中扩散 |
| C | 随机 | 强情感 | 中扩散 |
| D | 随机 | 弱情感 | 最弱扩散 |

### 参数校准过程（2026-03-11）

- 触发原因：极小规模校验中，强组出现过快饱和（A/C 在 12 步内接近或达到 100%），削弱了网络结构因子的可辨识性
- 校准原则：保持 2×2 因子设计不变，只调整研究参数，不改研究语义与调度机制
- 证据摘要：
  - A 组（30 agents, 12 steps）：`final_adoption_rate=1.0`
  - C 组（30 agents, 12 steps）：`final_adoption_rate=1.0`
  - B 组（30 agents, 12 steps）：`final_adoption_rate=0.1333`
  - D 组：早期进度显示低采纳（step=3 时为 0），按你的要求停止重试
- 无重试复核（20 agents, 8 steps, seed=13101）：
  - A=0.90，B=0.45，C=0.95，D=0.05
- 强组补充复核（A/C 两次种子，20 agents, 8 steps）：
  - A 组均值=1.00（2/2 饱和）
  - C 组均值=0.825（0.70~0.95）
- 调参动作：
  - 统一下调创新项：`p 0.003 -> 0.001`，降低外生采纳噪声
  - 强组降温：`emotion_arousal 0.25 -> 0.20`，`q 0.12 -> 0.10`
  - 弱组回调：`emotion_arousal 0.10 -> 0.12`，`q 0.08 -> 0.09`
- 当前判断：强弱组分层已拉开，A 对 C 的结构优势可见，但 A 组仍偏快，正式批次需重点监控 t50 与早期斜率

### 参数再校准（2026-03-12）
- 触发原因：WOM 完整实现后，LLM 在“无邻里采纳 + 无近期口碑”条件下系统性低估采纳概率，导致贴地
- 校准原则：保留 2×2 设计与 WOM 语义，仅调整 Bass 参数并补充创新项语义的初始创新者
- 调整动作：
  - 创新项：`p 0.001 -> 0.002`（维持极小外生采纳，配合初始创新者）
  - 强组：`q 0.10 -> 0.08`
  - 弱组：`q 0.09 -> 0.06`
- 近期验证（20 agents, 12 steps, seed=25101）：
  - A=0.60，B=0.05，C=0.40，D=0.05

### 正式规模试跑（2026-03-11）

- 目的：在正式规模（100 agents × 60 steps）下同时验证参数形态与工程稳定性
- 配置：A/B/C/D，repetitions=2，repetition_workers=4，timeout_seconds=180，run_retries=2
- 结果（终端汇总）：
  - 成功 4/8：A×2、C×2，均 `final_adoption_rate=1.0`
  - 失败 4/8：B×2、D×2，均为 `gateway timeout: timed out`
  - token 消耗（含失败）：total_tokens=882,440
- 含义：
  - 强组在正式规模下仍可能 10~18 步内饱和，最终采纳率存在上限效应风险
  - 弱组更容易触发超时，正式实验前需先确保 B/D 稳定可跑完

### 运行参数更新（2026-03-16）

- 网络平均度：四组统一 `avg_degree: 6`（由 8 下调），用于降低早期扩散过快带来的天花板效应
- YAML LLM 超时：四组统一 `timeout_seconds: 180`
- 批量脚本默认：`REPETITION_WORKERS=4`、`TIMEOUT_SECONDS=210`
- 批量脚本保护：当 `REPETITION_WORKERS > LLM_MAX_INFLIGHT` 时自动下调到 `LLM_MAX_INFLIGHT`
- 预实验脚本：`scripts/run_pilot.sh` 现已对齐批量脚本，自动加载 `.env` 并检查 `LLM_API_KEY` 与 `go`

---

## 📊 架构设计

### 混合架构说明

```
┌─────────────────────────────────────────────────────────┐
│                    实验控制层 (Python)                    │
│  - 实验配置管理                                          │
│  - 批量实验调度                                          │
│  - 数据采集与存储                                        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   ABM 仿真层 (Python/Mesa)                │
│  - 智能体调度                                            │
│  - 网络拓扑管理                                          │
│  - 扩散流程控制                                          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  智能体决策层 (Go/HTTP)                   │
│  - LLM 调用网关                                           │
│  - 采纳决策分析                                          │
│  - 重试与错误处理                                        │
│  - token 统计                                            │
└─────────────────────────────────────────────────────────┘
```

### 通信方式

- **唯一模式**: Python 通过 HTTP 调用 Go `/decide` 统一入口
- **失败策略**: fail-fast，调用失败立即中止当前仿真并报错

### 研究语义与工程优化边界

- **研究语义不变**: 单次仿真保持随机异步更新，按 agent 顺序逐个决策
- **工程优化可做**: 允许在调度层并行运行多个 repetition
- **明确不做**: 不在单步内并发同步决策，避免改变机制解释

---

## 📝 开发规范

### 代码风格

- **Python**: 遵循 PEP 8，使用 type hints
- **Go**: 遵循 Effective Go，使用 gofmt 格式化

### 测试要求

```bash
# Python 静态检查
uv run ruff check python
uv run mypy python

# Go 测试
cd go
go test ./...
```

### 提交规范

- `feat: ` 新功能
- `fix: ` 修复 bug
- `docs: ` 文档更新
- `refactor: ` 代码重构
- `test: ` 测试相关
- `chore: ` 其他

---

## 📚 相关文档

- [项目上下文](../PROJECT_CONTEXT.md)
- [CodeMap](docs/CODEMAP.md)
- [项目进展](docs/PROJECT_PROGRESS.md)
- [实验设计文档](../../04_实验设计/实验设计与分析流程_v1.0.md)
- [文献综述](../../02_文献综述/文献综述_v1.0.md)
- [技术栈调研](../../毕业论文_技术栈调研与执行计划.md)
- [执行计划](../../毕业论文_仿真实验详细执行计划_v1.0.md)

---

## 👥 作者信息

**作者**: 7mariooo (iu_roam)  
**机构**: 上海临港绝影智能科技有限公司  
**时间**: 2026 年 2 月

---

## 📄 许可证

本项目仅供学术研究使用。

---

*最后更新：2026-03-02*
