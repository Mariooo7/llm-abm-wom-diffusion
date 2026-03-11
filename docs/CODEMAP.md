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
│   └── cmd/main.go
├── python/
│   ├── agents/agent.py
│   ├── config/settings.py
│   ├── llm/decision_client.py
│   ├── models/model.py
│   ├── networks/generator.py
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
- Python 智能体规则：`python/agents/agent.py`
- Python 配置解析：`python/config/settings.py`
- Python LLM 决策客户端：`python/llm/decision_client.py`
- Python 网络生成：`python/networks/generator.py`
- Go 决策网关入口：`go/cmd/main.go`
- Go 请求/响应结构：`go/cmd/main.go` 中 `decisionRequest/decisionResponse`
- Go 重试与超时策略：`go/cmd/main.go` 中 `runDecision` 与 `runtimeTimeout`
- 预实验脚本：`scripts/run_pilot.sh`
- 批量实验脚本：`scripts/run_batch.sh`

## 4. 关键配置定位
- 实验组配置：`experiments/configs/group_a.yaml` ~ `group_d.yaml`
- 环境变量模板：`.env.example`
- Python 依赖：`python/requirements.txt`
- Go 依赖：`go/go.mod`

## 5. 当前配置策略
- 默认 `use_llm: true`，实验配置对齐阿里百炼 Qwen3.5-flash
- 默认 `n_nodes: 100`，对齐论文目标实验规模
- 默认 `avg_degree: 6`，用于降低强组过快饱和风险
- 默认 `llm.timeout_seconds: 180`（组配置）与 `TIMEOUT_SECONDS: 210`（批量脚本）
- 统一模型参数：`LLM_PROVIDER=aliyun_bailian`，`LLM_MODEL=qwen3.5-flash`
- 统一兼容地址：`LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- Python 决策入口：`python/llm/decision_client.py` 的 `DecisionClient.decide`
- Go 统一调用入口：`go/cmd/main.go` 的 `/decide` 服务模式（`LLM_SERVER_ADDR` 指定监听地址）
- 研究模式约束：`simulation.use_llm=true` 且 `llm_sampling_ratio=1.0`
- 语义边界：单次仿真保持随机异步更新，不在单步内做并发同步决策
- 工程优化边界：允许并行运行多个 repetition，不改变单次 run 的决策顺序

## 6. 常改文件清单
- 改实验参数：`experiments/configs/*.yaml`
- 改运行行为：`scripts/run_pilot.sh`, `scripts/run_batch.sh`
- 改仿真逻辑：`python/models/model.py`
- 改个体决策规则：`python/agents/agent.py`
- 改网络结构与指标：`python/networks/generator.py`
- 改配置字段映射：`python/config/settings.py`
- 改 Python LLM 决策：`python/llm/decision_client.py`
- 改 Go 决策网关策略：`go/cmd/main.go`
- 改项目决策：`../PROJECT_CONTEXT.md`

## 9. 文档职责分工
- `README.md`：面向使用者的入口文档，给出运行方式和当前默认参数
- `docs/ENV_SETUP.md`：环境搭建、`.env` 规范与常见问题排查
- `docs/ARCHITECTURE.md`：研究语义边界与系统分层设计
- `docs/PROJECT_PROGRESS.md`：阶段决策、参数调整证据与执行记录
- 本文档 `docs/CODEMAP.md`：代码定位与“改哪里看哪里”的索引

## 8. 教学式阅读入口
- 第一站（总流程）：`python/models/model.py`
- 第二站（个体决策）：`python/agents/agent.py`
- 第三站（网络影响）：`python/networks/generator.py`
- 第四站（Go 决策请求与解析）：`go/cmd/main.go`
- 第五站（Go 重试与容错）：`go/cmd/main.go`

## 7. 学术依据定位
- 实验设计：`../04_实验设计/实验设计与分析流程_v1.0.md`
- 文献综述：`../02_文献综述/文献综述_v1.0.md`
- 阅读笔记索引：`../03_阅读笔记/阅读笔记索引.md`
