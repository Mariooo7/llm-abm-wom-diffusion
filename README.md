# 毕业论文仿真实验项目

**论文题目**: 基于大模型智能体的新产品扩散机制研究：网络结构与口碑语义的交互效应

**英文名称**: LLM-Agent-Based New Product Diffusion Simulation

**技术栈**: Go (Eino) + Python (Mesa) 混合架构

---

## 📋 项目简介

本项目采用 **Go + Python 混合架构** 进行基于大语言模型 (LLM) 的智能体新产品扩散仿真实验：

- **Go (Eino 框架)**: LLM 智能体决策、口碑内容生成、情感分析
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
thesis-simulation/
├── python/                     # Python ABM 仿真模块
│   ├── models/                 # Mesa 模型定义
│   │   ├── __init__.py
│   │   └── model.py           # DiffusionModel
│   ├── networks/               # 网络生成 (NetworkX)
│   ├── analysis/               # 数据分析
│   └── requirements.txt        # Python 依赖
│
├── go/                         # Go Eino 智能体模块
│   ├── cmd/
│   │   └── main.go            # 主程序入口
│   ├── internal/
│   │   ├── agents/            # 智能体定义
│   │   │   └── agent.go
│   │   └── tools/             # LLM 工具
│   │       └── diffusion_tool.go
│   └── go.mod                 # Go 模块配置
│
├── experiments/                # 实验配置与结果
│   ├── configs/               # 实验配置文件
│   ├── results/               # 实验结果
│   └── logs/                  # 运行日志
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
cd thesis-simulation/python

# 使用 uv (推荐)
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 或使用 pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Go 环境安装 (可选)

```bash
# 安装 Go (macOS)
brew install go@1.23

# 进入 Go 目录
cd thesis-simulation/go

# 下载依赖
go mod download
go mod tidy
```

### 运行仿真

```bash
# Python: 运行预实验 (单组单次)
cd thesis-simulation/python
python -c "
from models import DiffusionModel
from config.settings import get_config

config = get_config('A')  # 组 A: 小世界 + 强情感
model = DiffusionModel(config)

while model.running:
    model.step()

metrics = model.get_metrics()
print(f'最终采纳率：{metrics[\"final_adoption_rate\"]:.2%}')
"

# Go: 运行 LLM 智能体测试 (需要配置 API Key)
cd thesis-simulation/go
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
| github.com/cloudwego/eino | v0.7.0 | LLM 编排框架 |
| github.com/cloudwego/eino-ext | latest | Eino 扩展 (OpenAI 兼容接口) |

---

## 🧪 实验配置

### 默认参数

| 参数 | 值 | 说明 |
|------|-----|------|
| N | 200 | 智能体数量 |
| T | 60 | 仿真步数 |
| p | 0.01 | 创新系数 (Bass 模型) |
| q | 0.3 | 模仿系数 (Bass 模型) |
| K | 8 | 网络平均度数 |
| repetitions | 15 | Monte Carlo 重复次数 |

### 实验组

| 组别 | 网络结构 | 口碑语义 | 预期效果 |
|------|----------|----------|----------|
| A | 小世界 | 强情感 | 最强扩散 |
| B | 小世界 | 弱情感 | 中等扩散 |
| C | 随机 | 强情感 | 中等扩散 |
| D | 随机 | 弱情感 | 最弱扩散 |

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
│                  智能体决策层 (Go/Eino)                   │
│  - LLM 调用与编排                                         │
│  - 采纳决策分析                                          │
│  - 口碑内容生成                                          │
│  - 情感分析                                              │
└─────────────────────────────────────────────────────────┘
```

### 通信方式

1. **本地模式**: Python 直接调用 Go 编译的二进制文件
2. **RPC 模式**: Go 作为 gRPC 服务，Python 通过 RPC 调用
3. **混合模式**: 关键决策调用 Go，简单决策使用 Python 启发式规则

---

## 📝 开发规范

### 代码风格

- **Python**: 遵循 PEP 8，使用 type hints
- **Go**: 遵循 Effective Go，使用 gofmt 格式化

### 测试要求

```bash
# Python 测试
cd thesis-simulation/python
pytest tests/ -v --cov=models

# Go 测试
cd thesis-simulation/go
go test ./... -v -cover
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
