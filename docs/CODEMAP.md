# 项目 CodeMap

## 1. 目标与范围
- 本项目用于完成毕业论文正式仿真（4 组 × 15 次 = 60 次）
- 代码层目标是交付可复现实验链路：配置加载、仿真运行、结果落盘、分析输入

## 2. 目录总览
```text
thesis-diffusion-simulation/
├── docs/
├── experiments/configs/
├── go/
│   ├── cmd/main.go
│   └── internal/
│       ├── agents/agent.go
│       └── tools/diffusion_tool.go
├── python/
│   ├── models/model.py
│   └── requirements.txt
├── scripts/
│   ├── run_pilot.sh
│   └── run_batch.sh
├── data/
│   ├── raw/
│   ├── processed/
│   └── results/
├── .env.example
└── README.md
```

## 3. 核心代码定位
- Python ABM 模型入口：`python/models/model.py`
- Go Agent 入口：`go/cmd/main.go`
- Go Agent 数据结构：`go/internal/agents/agent.go`
- Go 工具逻辑：`go/internal/tools/diffusion_tool.go`
- 预实验脚本：`scripts/run_pilot.sh`
- 批量实验脚本：`scripts/run_batch.sh`

## 4. 关键配置定位
- 实验组配置：`experiments/configs/group_a.yaml` ~ `group_d.yaml`
- 环境变量模板：`.env.example`
- Python 依赖：`python/requirements.txt`
- Go 依赖：`go/go.mod`

## 5. 当前配置策略
- 默认 `use_llm: false`，先确保启发式链路稳定
- `LLM_PROVIDER` / `LLM_MODEL` / `LLM_BASE_URL` 保持待定
- 正式实验前统一锁定模型与供应商，并在 `PROJECT_CONTEXT.md` 记录

## 6. 常改文件清单
- 改实验参数：`experiments/configs/*.yaml`
- 改运行行为：`scripts/run_pilot.sh`, `scripts/run_batch.sh`
- 改仿真逻辑：`python/models/model.py`
- 改 LLM 工具策略：`go/internal/tools/diffusion_tool.go`
- 改项目决策：`../PROJECT_CONTEXT.md`

## 7. 学术依据定位
- 实验设计：`../04_实验设计/实验设计与分析流程_v1.0.md`
- 文献综述：`../02_文献综述/文献综述_v1.0.md`
- 阅读笔记索引：`../03_阅读笔记/阅读笔记索引.md`
