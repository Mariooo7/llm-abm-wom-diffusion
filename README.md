# 毕业论文仿真实验项目

论文题目：基于大模型智能体的新产品扩散机制研究：网络结构与口碑语义的交互效应  
作者：茅睿（Mariooo7）  
技术栈：Go（并发调度与网关） + Python（Mesa ABM 引擎）

## 项目简介

这个仓库用于复现论文中的仿真实验：在给定网络结构与口碑信息环境的条件下，让智能体读取 WOM 文本并做出“采纳 / 不采纳”的决策，然后汇总得到扩散过程与统计结果。

- Go：提供 `/decide` 网关，负责与 LLM 的 HTTP 调用、超时与重试等工程侧细节
- Python：负责 ABM 主流程、网络生成（NetworkX）与结果落盘（Mesa + pandas）

## 研究设计（2×2）

自变量：
- 网络拓扑：小世界网络 vs 随机网络
- 口碑强度：强口碑 vs 弱口碑（通过口碑语料的高唤醒度占比实现操纵）

主要检验点：
- 主效应：强口碑组的扩散显著强于弱口碑组
- 交互效应：在弱口碑条件下，随机网络更容易维持扩散（低聚类、更多跨社群连边）；强口碑条件下两种网络都可能快速接近饱和，结构差异被掩盖

## 项目结构

```text
llm-abm-wom-diffusion/
├── python/                     # Python ABM 仿真模块
│   ├── models/                 # Mesa 模型定义 (model.py)
│   ├── networks/               # 网络生成器 (generator.py)
│   ├── agents/                 # 智能体定义 (agent.py)
│   ├── llm/                    # Python 侧决策客户端
│   ├── config/                 # 配置解析逻辑
│   └── run_experiment.py       # 仿真实验启动器
│
├── go/                         # Go 并发网关
│   └── cmd/main.go             # /decide 决策网关服务
│
├── experiments/configs/        # 核心实验参数 (A/B/C/D 四组 YAML 配置)
├── data/                       # 实验数据 (由 .gitignore 排除结果文件)
├── docs/                       # 架构与开发文档
├── scripts/                    # 运行脚本
│   └── run_experiment.sh       # 统一仿真入口
│
└── README.md                   # 本文档
```

## 快速开始

### 1. 环境准备

- **Python**: 3.11+ (建议使用 `uv` 进行依赖管理)
- **Go**: 1.23+

```bash
# Python 依赖安装
uv venv .venv
source .venv/bin/activate
uv pip install -r python/requirements.txt

# Go 依赖安装
cd go
go mod download
go mod tidy
cd ..
```

### 2. API Key 配置

```bash
cp .env.example .env
```
在 `.env` 文件中填入你的 `LLM_API_KEY`。支持 OpenAI 兼容格式接口（默认配置指向阿里云百炼）。

### 3. 运行仿真（统一入口）

所有实验统一通过 `scripts/run_experiment.sh` 调度，脚本内置并发管理与网关自启。

场景 A：运行论文默认批次（4 组 × 15 次）
```bash
bash scripts/run_experiment.sh
```
默认以并发方式跑满 60 次 run，结果落盘到 `data/results/formal_<时间戳>`。

场景 B：自定义参数做小规模验证（避免影响正式数据）
```bash
EXP_GROUPS_OVERRIDE="A B" \
REPETITIONS=2 \
N_AGENTS=10 \
N_STEPS=5 \
bash scripts/run_experiment.sh
```
结果落盘到 `data/results/verify_<时间戳>`。

## 实验基线配置（当前生效）

基于预实验校准，正式批次采用如下参数矩阵确保平滑的 S 曲线与严谨的控制变量：

| 组别 | 网络拓扑 | 产品强度 | q (模仿系数) | initial_seed_ratio | High Arousal Ratio (高唤醒口碑占比) |
|------|----------|----------|--------------|--------------------|--------------------------------------|
| **A** | 小世界 | 强 | 0.20 | 0.04 | 60% (0.6) |
| **B** | 小世界 | 弱 | 0.20 | 0.04 | 30% (0.3) |
| **C** | 随机网络 | 强 | 0.20 | 0.04 | 60% (0.6) |
| **D** | 随机网络 | 弱 | 0.20 | 0.04 | 30% (0.3) |

**全局控制变量**:
- 智能体数量 ($N$): 100
- 仿真步数 ($T$): 60
- 网络平均度数 ($K$): 8
- 创新系数 ($p$): 0.003
- Monte Carlo 重复次数: 15

说明：`initial_seed_ratio` 用于控制开局的火种数量，避免“完全无口碑 → 全体低概率 → 全程贴地”的极端情形。

## 架构设计

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

- Python 通过 HTTP 调用 Go `/decide` 统一入口
- 失败策略：fail-fast（单步重试耗尽则中止当前 run，避免产生不可解释的数据）

### 研究语义与工程优化边界

- 研究语义不变：单次仿真保持随机异步更新，按 agent 顺序逐个决策
- 工程优化可做：允许在 repetition（重复实验）级别并行调度
- 明确不做：不在单步内并发同步决策，避免改变机制解释

## 开发规范

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

## License

本项目采用 MIT License，详见 LICENSE。

---

## 📚 相关文档

- [CodeMap](docs/CODEMAP.md)
- [架构设计](docs/ARCHITECTURE.md)
- [环境配置指南](docs/ENV_SETUP.md)
- [项目进展与演进日志](docs/PROJECT_PROGRESS.md)

---

## 👥 作者信息

**作者**: 茅睿 (Mariooo7 / IU_Roam)  
**机构**: 中山大学管理学院（SYSBS）  
**时间**: 2026 年 3 月

---

## 📄 许可证

本项目仅供学术研究使用。

---

*最后更新：2026-03-20*
