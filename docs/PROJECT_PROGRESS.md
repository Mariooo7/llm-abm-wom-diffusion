# 项目进展日志

## 当前阶段
- 阶段：正式实验前的工程收敛
- 目标：清理错误配置、统一文档、打通可复现实验链路

## 本轮已完成（2026-03-10）
- 清理了实验配置中的过时模型与供应商默认值
- 将 4 组配置默认 `use_llm` 调整为 `true`
- 统一 `.env.example` 为 Qwen3.5-flash 默认模板
- 更新 `PROJECT_CONTEXT.md` 以反映当前目录与决策
- 补充 `.traeignore` 与 Trae 搜索排除规则
- 新增 `docs/CODEMAP.md` 作为代码结构与关键配置索引
- 补齐 Python 模块骨架（agents/networks/config），修复导入路径
- 修复 Go 依赖版本与 API 迁移，`go test ./...` 通过
- 完成 Python 静态检查，`ruff` 与 `mypy` 通过
- 在 `docs/ARCHITECTURE.md` 增加教学式源码解读章节
- 已接入阿里百炼 `qwen3.5-flash`（OpenAI 兼容模式）并固化默认参数
- 在 Go Agent 入口实现上下文缓存槽位（`WithSessionValues`）与学术化提示词模板
- 完成一次 Go Agent 冒烟运行，确认模型配置可用
- 修复 Mesa 3.x 兼容性问题（移除 `mesa.time.RandomActivation` 与 `model.agents` 冲突）
- 完成组 A 20 步 pilot 冒烟，确认 Python 仿真链路可运行
- 已完成组 A 全步长 pilot 并落盘 `data/raw/pilot_A_1.csv`
- 已完成 4 组 × 15 次批量仿真并生成 `data/results/metrics.csv`
- 批量结果显示各组采纳率均为 1.0，需在下一轮校准参数区分度
- 在 `go/cmd/main.go` 增加 token 消耗统计（input/output/total/model_calls）
- 将 `docs/ARCHITECTURE.md` 升级到 v0.3.0，补充参数配置依据与缓存逻辑详解
- 将代码与研究设计对齐为 `100` 智能体默认规模，并修正文档中的 `N=200` 残留项
- 在 Python 侧接入消费者级 LLM 决策闭环（Qwen3.5-flash），实现单步 JSON 决策
- 建立 LLM 调用 fail-fast 机制，调用失败即中止并显式报错
- 在仿真指标中增加 LLM token 统计（model_calls/prompt/completion/total）
- 完成 Python→Go(Eino) 统一调用入口改造，移除 Python 直连模型调用路径
- 修正 Go 提示词角色定义：决策链路统一为“模拟消费者单步采纳决策”
- 在 Go 侧接入阿里百炼显式前缀缓存（cache_control=ephemeral）
- 新增 `LLM_PREFIX_CACHE_ENABLED` 环境开关并默认开启

## 下一步计划
- 基于现有结果校准参数，避免四组采纳率全部饱和
- 增加对比指标（峰值步数、半饱和时间）提升组间可解释性
- 复跑 4×15 并输出可用于论文统计检验的数据表
- 将 token 消耗统计接入批量实验汇总，形成成本-效果联动分析表
- 增加 LLM 决策日志抽样，支持论文中的机制解释章节
- 复跑 4×15 并对比缓存命中前后 token 成本差异

## 风险与阻塞
- 当前参数组合导致扩散过快，组间差异难以检验
- Python-Go 已完成统一入口改造，需在正式参数下补做端到端压力冒烟
- 阿里百炼显式缓存要求前缀长度达到阈值，需通过实测确认命中率

## 文档审查建议路径
1. 先读 `PROJECT_CONTEXT.md`，确认目标与约束不偏移  
2. 再读 `docs/CODEMAP.md`，定位代码入口与职责边界  
3. 重点读 `docs/ARCHITECTURE.md` 的“教学式源码解读”  
4. 最后回看本文件，确认“已完成/下一步/风险”是否与代码一致
