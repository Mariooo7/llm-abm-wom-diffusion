# 项目进展日志

## 当前阶段
- 阶段：正式实验前的研究与工程收敛
- 共识：不改变研究语义，只做不影响因果解释的工程优化
- 目标：以可复现、可统计检验、可追溯成本的方式启动正式实验

## 本轮推进（2026-03-16）
- UI 可用性增强（保持原布局）：
  - `formal_batch` 分组面板新增持续动态指标：`Rate μ/max`、`Calls(done)`
  - 非交互终端的 `compact` 摘要同步增加分组 `r=均值/最大`、`c=累计调用`，避免仅看进度条
  - 代码位置：`python/run_preflight.py`
- 高并发稳定性与最优参数探测：
  - `concurrency_sweep`（group=A，2~10，并发每档 2 轮）全部成功，`stable_max_no_failure=10`
  - `formal_batch` 实测（A/B/C/D）：
    - 4 runs（12 agents × 6 steps）：workers=3 `real=133.03s`；workers=4 `real=81.47s`
    - 8 runs（10 agents × 4 steps）：workers=4 `real=84.35s`；workers=5 `real=92.46s`；workers=6 `real=98.91s`
  - 结论：当前环境下 `REPETITION_WORKERS=4` 为稳定最优默认值
- 更大规模小重复验证（24 agents × 12 steps，repetitions=3）：
  - 路径：`data/results/trend_check_large_20260316_130541/batch_summary.csv`
  - 完成：12/12 成功，0 失败，`real=879.87s`
  - 分组均值：A=0.8611，B=0.0417，C=0.5833，D=0.0694（保持 A/C 高于 B/D）
  - 观察：D 组仍是主要长尾来源，后续正式批次需重点关注 D 组耗时波动

## 工程扫描与清理（2026-03-17）
- 范围：日志输出、过程记录、结果落盘、脚本有效性、空目录与无效历史产物
- 记录增强（`python/run_preflight.py`）：
  - `formal_batch` 增加批次事件日志 `batch_events.jsonl`（`batch_start/run_start/run_progress/run_done/run_failed/batch_done`）
  - 过程曲线落盘 `adoption_timeline_*.csv`，包含每步采纳率并标注 `is_checkpoint`（默认每 10 步与最终步）
  - 批次汇总新增速度与过程指标：`t10_step`、`t50_step`、`auc_adoption`
  - 汇总索引新增 `adoption_timeline_file`，便于从 `batch_summary.csv` 追溯到单 run 过程轨迹
- 脚本与文档一致性修复：
  - `scripts/run_batch.sh` 默认并行恢复并固定为 `REPETITION_WORKERS=4`
  - 批量脚本结束摘要改为打印实际输出路径：`batch_summary.csv`、`metrics_*.json`、`adoption_timeline_*.csv`、`batch_events.jsonl`、`simulation_*.csv`
  - 清理文档中的失效引用（如已删除的 `main.py`、不存在的 `scripts/analyze_results.py`、过期目录结构）
- 资产清理原则：
  - 仅清理空目录与无引用失效项，不删除任何非空正式实验输出目录
  - 不触碰进行中实验目录与其日志文件，避免影响正式实验链路

## 当前生效基线（2026-03-13）
- 当前正式基线参数：A/C `p=0.003, q=0.12`；B/D `p=0.003, q=0.095`
- 当前 WOM 机制：离线语料分桶 + 每步传播 + `memory_limit=5`
- 当前冷启动机制：`round(N*p)` 初始创新者，且 `p>0` 时至少 1 人
- 当前说明口径：本文件中更早的校准小节保留为历史过程，不作为当前生效参数

## 配置治理收敛（2026-03-13）
- 单一来源原则：
  - 研究参数仅在 `experiments/configs/group_*.yaml`（网络、WOM、Bass、simulation）
  - 模型/网关参数仅在 `.env`（provider/model/base_url/temperature/timeout/server）
  - 运行调度参数仅在 `scripts/run_batch.sh` 默认值与命令行覆盖（workers/retries/inflight）
- 已执行清理：
  - 移除四组配置中的 `llm:` 段，避免与 `.env` 重复
  - 精简 `.env/.env.example`：移除实验调度与无效项，仅保留长期稳定项
  - `python/config/settings.py` 改为环境变量优先读取模型参数，避免组配置与环境配置双源冲突
- 预实验入口收敛：
  - `scripts/run_pilot.sh` 保留为便捷入口，但内部统一调用 `python/run_preflight.py --mode smoke`
  - 结论：`run_pilot` 不是第二套实验逻辑，而是 `run_preflight` 的薄包装入口

## 工程优化记录（2026-03-13）
- 目标：提升批量运行可观测性，避免只能等待 `log_interval` 才看到进度
- 改动文件：`python/run_preflight.py`
- 实施内容：
  - `formal_batch` 新增 1 秒刷新看板：总览（queued/running/retrying/done/failed）+ 分组进度 + 活跃任务
  - 单 run 增加 progress hook，将 `step/rate/attempt/status` 实时回传到看板
  - 失败重试状态显式化：`starting -> running/retrying -> done/failed`
  - 保持落盘口径不变：`batch_summary.csv`、`metrics_*.json`、`simulation_*.csv`
- 并发配置记录（本轮目标口径）：`REPETITION_WORKERS=4`、`LLM_MAX_INFLIGHT=4`、`RUN_RETRIES=4`
- 失败明细：本次代码检查与构建阶段无新增失败；运行态失败仍按 `failed` 计入汇总
- 验证命令与结果：
  - `uv run ruff check python`
  - `uv run mypy python`
  - `cd go && go test ./...`
  - 结果：全部通过
- 下一步：执行 100x60 小重复（每组 3-5 次）观察趋势是否翻转，并记录至本文件

## 工程维护记录（2026-03-13，续）
- 目标：清理冗余实现、降低重试语义分叉风险，并提升代码可读性
- 冗余/矛盾治理：
  - 将“可重试错误判定”统一收敛为 `python/llm/decision_client.py::is_retriable_decision_error_message`
  - `run_preflight.py` 与 `model.py` 不再各自维护一套关键字，避免后续一处更新另一处遗漏
- 运行容错语义补强：
  - `model.step` 中新增“单步决策级重试”路径，失败先在当前 step 局部重试
  - 仅在局部重试耗尽后，才向上触发 run 级重试，减少弱组长跑时整轮重跑概率
- 命名与可读性改进：
  - 拆分 `_run_agent_step_with_retry` 与 `_decision_retry_sleep_seconds`，替代内联重试分支
  - 保留 run 内随机异步更新语义不变，确保研究可比性
- 新增运行参数（脚本已接入并打印）：
  - `LLM_DECISION_RETRY_ATTEMPTS`（默认 2）
  - `LLM_DECISION_RETRY_BACKOFF_SECONDS`（默认 1）

## 终端可视化升级（2026-03-13，续）
- 目标：解决批量实验输出刷屏问题，改为清晰、简洁、可视化的单屏面板
- 改动文件：
  - `python/run_preflight.py`
  - `scripts/run_batch.sh`
  - `python/requirements.txt`
- 实施内容：
-  - `formal_batch` 新增 Rich Live 面板，原地刷新，不追加滚动日志
  - 面板固定展示：总览状态、分组进度条、活跃任务表、最近事件
-  - 增加 UI 参数：`UI_REFRESH_SECONDS`
-  - 非交互终端或 Rich 不可用时自动回退低频 `compact` 摘要输出，保证兼容与可读性
  - `run_batch.sh` 在 `live` 模式使用 `script -q` 记录终端输出到日志文件，避免 `tee` 破坏动态渲染
- 极小规模验证：
  - 命令：A/B 两组，`n_agents=8`，`n_steps=4`，`repetitions=1`，`workers=2`
  - 结果：`success_runs=2`，`failed_runs=0`，面板稳定显示且无刷屏

## p/q 校准脉络（从理论预设到当前基线）
- 语义锚点（理论口径）：
  - Bass (1969)：`p`=外生创新（无社交线索也可能发生的自发采纳），`q`=内生模仿（随已采纳比例放大）
  - 研究设计要求：保持 `q > p`，并保持强刺激组 `q_strong > q_weak`，否则“强/弱 WOM”处理语义会被参数抵消
  - 方法学约束：校准只调整研究参数（`p/q/emotion_arousal/K`），不改研究语义（阈值采纳、离线语料、传播机制、异步调度）
- Round 0（最初预设，作为启动点）：
  - 目标：先让四组能跑出扩散曲线，再谈结构效应与交互项
  - 设定：`p≈0.003`（保证有外生火种），强组 `q≈0.12`，弱组 `q≈0.08`（保证强弱差异），并配合更高的强组唤醒度（当时版本）
  - 风险预期：强组可能过快饱和（天花板），弱组可能在部分种子下贴地（地板）
- Round 1（2026-03-11：压天花板、补地板的第一次收敛）：
  - 触发：极小规模校验中 A/C 过快接近或达到 100%，结构差异不可辨识
  - 调整：
    - `p 0.003 -> 0.001`：降低外生噪声，避免“随机点火”掩盖网络与 WOM 处理效应
    - 强组：`q 0.12 -> 0.10` 且 `emotion_arousal 0.25 -> 0.20`：抑制强刺激导致的快速冲顶
    - 弱组：`q 0.08 -> 0.09` 且 `emotion_arousal 0.10 -> 0.12`：降低弱组贴地概率
  - 结果（记录摘要）：强弱梯度出现，但 A 仍偏快，需继续监控速度指标而非只看最终值（见下方历史记录）
- Round 2（2026-03-11 深夜：再标定，兼顾结构窗口与弱组可扩散性）：
  - 动机：在保持 2×2 不变下，让曲线进入“结构效应可观察区间”（避免全满/全零）
  - 调整：
    - A/C：`p 0.001 -> 0.002`，`q 0.10 -> 0.085`
    - B/D：`p 0.001 -> 0.002`，`q 0.09 -> 0.07`
  - 结果：弱组更可扩散，但正式规模试跑中 B/D 仍发生超时风险（工程侧），且强组仍可能偏快（研究侧）
- Round 3（2026-03-11 晚间：弱组冷启动专项修复，随后发现“过强”副作用）：
  - 动机：弱组偶发“零扩散”贴地（冷启动失败）
  - 调整（仅弱组）：B/D `p 0.002 -> 0.003`，`q` 维持 `0.07`
  - 结果（记录摘要）：弱组不再贴地，但均值上升到接近强组，B≈D，弱组差异不足，且有“过冲”风险（地板解决但结构效应被点火项淹没）
- Round 4（2026-03-12：WOM 机制落地后的关键拐点，重做冷启动语义）：
  - 触发：WOM 真正传播后，早期全体未采纳会导致“无近期口碑消息→一致低概率→全程贴地”
  - 处理（不改变研究语义，仅补足 Bass 语义在离散 ABM 的实现）：引入初始创新者 `round(N*p)`（`p>0` 至少 1）
  - 随之重设基线（保持强弱语义与 2×2 设计）：A/C `p=0.002,q=0.08`；B/D `p=0.002,q=0.06`
  - 小规模验证：20 agents×12 steps（seed=25101）A=0.60，C=0.40，B/D=0.05；且 WOM 传播统计不为零（说明链路生效）

## 下一阶段校准：如何继续（以“收敛”为硬约束）
- 校准目标（必须同时满足）：
  - 结构主效应可检验：A>C 且 B>D（至少在速度指标或最终规模其中之一上稳定出现）
  - 避免极端：强组不应频繁 10~20 步内冲到 1.0；弱组不应大量重复接近 0
  - `q > p`、`q_strong > q_weak` 语义不被破坏
- 推荐执行顺序（只动一个旋钮，逐步收敛）：
  - 固定 `p=0.002` 与强组 `q_strong=0.08` 不动，先把弱组从贴地边缘拉回：B/D `q_weak: 0.06 -> {0.065, 0.07}` 二选一
  - 评估判据（正式实验同口径）：最终采纳率 + 速度指标（t10/t50/峰值步），并以多种子/多重复的稳健性为选择依据
  - 若强组再次出现天花板：再把强组 `q_strong` 以 0.005 为步长下调（例如 0.08->0.075），弱组保持不动，避免双向同时改导致不可归因

## 本轮直接执行结果（2026-03-13）
- 弱组 `q_weak` 候选对比（B/D，2 seeds，12 agents×8 steps）：
  - `q=0.065`：4/4 成功，B 与 D 各 run 最终采纳率均为 `0.0833`（仅初始创新者）
  - `q=0.07`：4/4 成功，B 与 D 各 run 最终采纳率均为 `0.0833`（仅初始创新者）
  - 对比结论：在该尺度下两档 `q_weak` 无可辨识差异；为保持强弱处理差异并避免抬高弱组上限，采用更保守的 `q_weak=0.065`
- 接近正式规模“预注册式”验证（A/B/C/D，固定 seed=28101，20 agents×12 steps）：
  - 4/4 完成，无缺组缺次；A/B/C/D 最终采纳率均为 `0.05`（仅初始创新者）
  - 解释：当前瓶颈不在弱组 `q` 微调，而在该运行窗口内外生点火与后续扩散链未形成
- 数据路径：
  - 弱组候选：`data/results/batch_summary.csv`（q=0.065）与 `data/results/calibration_qweak_20260313/q07_summary.csv`（q=0.07）
  - 预注册验证：`data/results/preregister_validation_20260313_summary.csv`
- 下一动作（保持单旋钮原则）：
  - 暂不改 `q`，先在固定 `q` 下做 `p` 的小步校准（建议 `0.002 -> {0.0025, 0.003}`）并复用同一固定种子策略

## 从现在到“完成实验 + 完成论文写作”的冻结 TODO（后续严格按此执行）
- 研究参数收敛
  - [x] 完成弱组 `q_weak` 校准，输出选择依据与拒绝理由（写入本文件）
  - [x] 用接近正式规模做 1 次“预注册式”验证：固定种子策略与重复次数，确认无明显天花板/贴地
  - [ ] 冻结研究参数：写明最终 `p/q/emotion_arousal/K/N/T`，并标注“冻结后不再改研究参数”
- 工程稳定性与复现
  - [ ] 固化正式运行命令与输出路径（run_tag、results/raw 目录结构、失败重跑规则）
  - [ ] 生成一次 token/耗时预算区间（基于预跑结果），写入本文件供论文与执行参考
  - [ ] 正式批次前做 1 次端到端空跑（少重复）：确认网关、超时、重试、落盘一致
- 正式实验执行
  - [ ] 运行正式批次：4 组 × 15 repetitions × 100 agents × 60 steps
  - [ ] 完整性检查：每组 repetition 数量齐全、无缺失文件、汇总表与分 run 文件可追溯
  - [ ] 冻结原始结果：记录 run_tag 与 git commit hash（用于论文可复现）
- 分析与论文写作
  - [ ] 明确主因变量与统计方案：最终规模 + 速度指标（t50/早期斜率），并写入方法章节口径
  - [ ] 跑统计检验与效应量：主效应（网络、WOM）、交互效应（2×2），并输出可复用表格
  - [ ] 出图：扩散曲线（均值±置信区间）、箱线图/雨云图（最终规模与 t50）、网络对比图（可选）
  - [ ] 写作落地（逐章交付）
    - [ ] Method：实验设计、变量操作化、WOM 语料生成与质检、参数校准过程（含本文件时间线）
    - [ ] Results：主效应/交互效应 + 稳健性检查
    - [ ] Discussion：机制解释、局限性、外推边界
    - [ ] Appendix：提示词模板、关键配置、运行命令、版本与随机种子策略

## 当前共识（2026-03-11）
- 研究语义保持不变：单次仿真采用随机异步更新，`Agent.step` 逐个调用 LLM 决策
- 工程优化边界明确：允许并行运行多个 repetition；不做单步内同步并发决策
- 系统运行参数暂时冻结：以稳定为先，不做非必要调优
- 研究参数按学术规范确定：以理论机制、文献证据、研究问题为约束
- 文档与代码必须一致：任何路径、参数、策略变更需同步更新文档

## WOM 语料库与传播机制定稿（2026-03-12）
- 定稿方案：采用“离线 LLM 生成 WOM 语料库 + 仿真内抽取传播”，不在仿真主循环中在线生成 WOM 文本
- 方法口径：WOM 作为实验刺激材料（stimulus）而非过程内生成变量，确保处理变量可控、可复现、可追溯
- 机制实现：
  - 新增 `wom.corpus_path`、`wom.memory_limit`、`wom.share_multiplier` 配置字段
  - 模型启动时加载 `data/wom/wom_corpus.csv`，按 `strength × arousal_bin` 建立四个桶：`strong_low`、`strong_high`、`weak_low`、`weak_high`
  - 每个时间步先执行传播：已采纳者按 `sharing_tendency`（经归一化并乘以 `share_multiplier`）决定是否分享，分享后向邻居广播一条对应桶消息
  - 接收者仅保留最近 `memory_limit` 条 WOM 文本，并在后续决策时作为 `wom_messages` 输入
- 决策语义统一：最终采纳规则已统一为阈值采纳（`adopt`）并同步落盘 `adopt_final`
- 数据落盘增强：
  - 决策级原始数据新增 `wom_bucket`、`adopt_final` 等字段
  - 运行汇总新增 `wom_usage.messages_sent/messages_delivered` 指标
- 冷启动补足：
  - 采用 Bass 模型语义的“外生创新者”初始化：按 `round(N * p)` 设定初始采纳者（`p > 0` 时至少 1）
  - 目的：避免早期全体未采纳导致 WOM 无法传播、LLM 一致性给出低概率而出现贴地
- 论文写作建议固定表述：
  - “WOM 文本由生成式模型在实验前按处理条件离线构造并冻结，仿真运行中仅执行条件化抽取与网络传播，从而控制语义处理的一致性与可复现实验路径。”
- 参考依据（用于文献综述与方法论支撑）：
  - Bass, F. M. (1969). A New Product Growth for Model Consumer Durables.
  - Rogers, E. M. (2003). Diffusion of Innovations (5th ed.).
  - Granovetter, M. (1978). Threshold Models of Collective Behavior.
  - Watts, D. J., & Strogatz, S. H. (1998). Collective dynamics of 'small-world' networks.
  - Centola, D. (2010). The Spread of Behavior in an Online Social Network Experiment.
  - Berger, J., & Milkman, K. L. (2012). What Makes Online Content Viral?
  - Shadish, W. R., Cook, T. D., & Campbell, D. T. (2002). Experimental and Quasi-Experimental Designs.

## WOM 语料库生成记录（2026-03-12）
- 生成平台：Google AI Studio（网页端对话）
- 生成模型：Gemini 3.1 Pro Preview
- 生成参数：默认参数（按平台默认值）
- 已生成批次：
  - Batch 1：`strong_high`（`data/wom/wom_corpus.csv`，message_id `strong_high_002`~`strong_high_051`）
  - 备注：当前批次覆盖产品类别较广，后续批次建议尽量收敛到统一产品域或抽象为“通用新产品/新工具”以减少内容域混杂对采纳判断的潜在干扰

## WOM 提示词模板标准化（2026-03-12）
- 目的：将四组 WOM 语料生成规则固定为统一模板，支持论文复现、过程追踪与后续批量生成
- 范围：`strong_low`、`strong_high`、`weak_low`、`weak_high` 四个桶统一采用同一“抽象代称+约束清单+自检规则”框架
- 固定输出格式：`message_id,strength,arousal_bin,text`
- 固定抽象代称：仅允许 `新工具/这款工具/该产品/新版本/旧版本`
- 固定禁用项：
  - 禁止可推断产品类别的具象词（硬件、软件、行业功能词）
  - 禁止绝对化词（如“零错误”“永远”“每次都”“100%”）

### 四组通用模板（当前定稿口径）
- `strong_low`（高强度 + 低唤起）：
  - 要求：正向结论明确、必须新旧对比、语气冷静克制
  - 建议词：`更稳定一些/更顺畅/时间更可控/错误更少`
  - 禁止词：`完美/颠覆/爆炸式/革命性`
- `strong_high`（高强度 + 高唤起）：
  - 要求：正向结论明确、必须新旧对比、允许高情绪表达
  - 约束：允许兴奋语气但禁止绝对化承诺与品类暗示
- `weak_low`（低强度 + 低唤起）：
  - 要求：仅表达小幅改进，语气平淡谨慎
  - 建议词：`稍微/有一点/在部分场景`
- `weak_high`（低强度 + 高唤起）：
  - 要求：主观情绪偏高，但客观改进幅度必须保持“小”
  - 约束：禁止把效果写成“显著提升”或“翻倍跃升”

### 预填参数规范（用于网页端分批生成）
- 文件：`data/wom/wom_corpus.csv`
- 表头：第 1 行固定 `message_id,strength,arousal_bin,text`
- 当前分段约定：
  - `L2-L51`：`strong_low_001~050`
  - `L52-L101`：`strong_high_001~050`
  - `L102-L151`：`weak_low_001~050`
  - `L152-L201`：`weak_high_001~050`
- 生成时每批固定 50 条，按分段覆盖写入，避免跨桶覆盖和 message_id 冲突

### 质量评估与修订记录（用于论文方法透明化）
- v1 问题：出现“屏幕/电池/外壳/接口”等具象属性，存在产品类别暗示，可能引入内容域混杂变量
- v2（`strong_low`）改进：抽象化与低唤起基本达标，可作为可用版本
- v3（`strong_high`）问题：情绪强度过高且含绝对化表达（如“零错误”“彻底”“完美无缺”），超出受控语料边界，需按模板重生
- 判定标准：
  - 先判“语义抽象性”（是否可推断产品类别）
  - 再判“桶一致性”（强弱与唤起是否匹配）
  - 最后判“文本多样性”（句式与语义是否过度同质）

### 论文写作可直接复用表述
- “本研究在实验前通过统一提示词模板离线生成 WOM 语料，并按 `strength × arousal` 分桶冻结。仿真运行阶段仅执行条件化抽样与网络传播，不再在线生成文本，以控制刺激一致性并提高复现性。”
- “语料质检采用三步规则：抽象性筛查、桶一致性筛查、同质化筛查；不符合规则的批次整体回炉重生，以避免后验挑选造成偏差。”

## 已完成
- Go 决策网关统一为 `/decide` 入口，保留重试与 token 统计能力
- Python 仿真固定为 LLM 单一路径决策，失败即中止（fail-fast）
- 四组配置统一为 `use_llm: true` 与 `llm_sampling_ratio: 1.0`
- 已移除前缀缓存补齐方案，避免额外 token 成本与解释噪声
- 已完成并发稳定性压测，确认 200 并发可作为调度层安全上限
- 代码检查通过：`go test ./...`、`ruff check`、`mypy`
- 已完成极小规模参数校验（30 agents × 12 steps）并记录分组行为差异
- 已停止额外重试流程，按当前证据推进参数二次校准

## 参数调整记录（2026-03-11）
- 观测结果：
  - A 组（小世界+强语义）：12 步内达到 100% 采纳
  - C 组（随机+强语义）：12 步内达到 100% 采纳
  - B 组（小世界+弱语义）：12 步最终采纳率约 0.1333
  - D 组（随机+弱语义）：早期进度低采纳，重试已中止
- 无重试复核（20 agents × 8 steps，seed=13101）：
  - A=0.90，B=0.45，C=0.95，D=0.05
- 强组补充复核（A/C，各 2 次 seed）：
  - A 均值 1.00，C 均值 0.825，A 对 C 的结构优势开始出现
- 问题判定：
  - 强组存在天花板效应，网络结构主效应被口碑强度淹没
  - 弱组存在贴地风险，可能导致交互项解释不稳定
- 二次校准（保持 2×2 设计不变）：
  - 强组（A/C）：`emotion_arousal=0.20`，`q=0.10`
  - 弱组（B/D）：`emotion_arousal=0.12`，`q=0.09`
  - 全组统一：`p=0.001`
- 校准目标：
  - 避免“强组秒满”与“弱组长时间贴地”
  - 提升 `A > C > B > D` 分层出现概率
  - 保持可解释性：网络效应与语义效应同时可见

## 参数与工程优化落实（2026-03-11，晚间）
- 先做参数与稳定性优化，随后按需求替换 Go 网关系统提示词
- 四组配置统一调整：
  - `avg_degree: 8 -> 6`
  - `llm.timeout_seconds: 120 -> 180`
- 批量脚本稳态优化（`scripts/run_batch.sh`）：
  - 默认 `REPETITION_WORKERS: 4 -> 3`
  - 默认 `TIMEOUT_SECONDS: 180 -> 210`
  - 新增保护：当 `REPETITION_WORKERS > LLM_MAX_INFLIGHT` 时自动下调，避免调度层过载
- 预实验脚本一致性优化（`scripts/run_pilot.sh`）：
  - 与批量脚本对齐，自动加载 `.env`
  - 启动前检查 `LLM_API_KEY` 与 `go` 可用性，减少“跑到中途才失败”的无效开销
- 文档同步：
  - `.env.example` 已补齐批量运行常用覆盖变量
  - `README.md`、`docs/ENV_SETUP.md` 已同步最新默认值和脚本行为

## 研究参数再设定（2026-03-12）
- 调整动因：WOM 完整实现后，LLM 在“无邻里采纳 + 无近期口碑消息”条件下倾向给出低采纳概率，出现贴地
- 理论依据：
  - Bass (1969) 中创新项 `p` 对应早期外生采纳，允许在零社交线索条件下出现少量创新者
  - Rogers (2003) 的创新者类型与早期采用逻辑，支持设定极小比例的初始采纳者
  - Watts & Strogatz (1998) 的结构效应需在“扩散阻力存在”时才可观察
- 新参数（保持 2×2 设计不变）：
  - A/C（强情感）：`p=0.002`，`q=0.08`
  - B/D（弱情感）：`p=0.002`，`q=0.06`
  - 其余保持：`emotion_arousal`、`avg_degree` 与网络类型不变
- 小规模验证（20 agents, 12 steps, seed=25101）：
  - A=0.60，B=0.05，C=0.40，D=0.05

## 提示词更新落实（2026-03-11，晚间）
- 已替换 Go 网关系统提示词，核心变化：
  - 角色改为“有限理性、默认维持现状”的普通消费者
  - 强化 `openness`、`risk_tolerance`、`innovation_coef`、`imitation_coef`、`adopted_ratio`、`emotion_arousal` 的参数语义解释
  - 强制输出 JSON 顺序为 `reasoning -> probability -> adopt`
  - 强制约束：`probability>=0.5` 时 `adopt=true`，其余为 `false`
  - 禁止 Markdown 与额外文本，保留一到两句第一人称 reasoning
- 为保证输入与提示词取值范围一致，Python 侧把 `openness/risk_tolerance` 从内部量表分数映射到 `[0,1]` 后再送入网关
- 目标：在保留可解释文本的前提下，减少“顺从式采纳”，提升机制有效性与学术可解释性

## 正式规模试跑记录（2026-03-11）
- 目的：用接近正式实验的规模验证两件事：工程稳定性（并发/超时/重试）与参数形态（是否天花板/贴地）
- 试跑配置：
  - 四组齐全：A/B/C/D
  - 规模：100 agents × 60 steps
  - 重复次数：repetitions=2（试跑）
  - 调度：repetition_workers=4，timeout_seconds=180，run_retries=2
  - 输出：`data/results/formal_try_20260311/batch_summary.csv`
- 试跑结果（终端汇总）：
  - 成功：4/8（A×2、C×2），失败：4/8（B×2、D×2）
  - 失败原因：B/D 均为 `gateway timeout: timed out`（重试后仍失败）
  - 强组形态：A/C 在 10~18 步内达到 100%（强烈天花板趋势仍存在）
  - token 消耗（含失败）：total_tokens=882,440，elapsed_seconds_total=1242.95s
- 数据落盘（成功 run）：
  - A rep1：final=1.0，model_calls=422，total_tokens=226,694
  - A rep2：final=1.0，model_calls=424，total_tokens=226,399
  - C rep1：final=1.0，model_calls=359，total_tokens=191,922
  - C rep2：final=1.0，model_calls=443，total_tokens=237,425
- 结论：
  - 研究侧：当前强组仍偏快，若以最终采纳率为主指标易上限效应；正式实验需把速度类指标列为主输出
  - 工程侧：弱组更易触发超时风险，必须先解决 B/D 的稳定完成问题，否则全量正式实验将出现缺组/缺重复

## 正式实验前的最小必做项
- 明确主因变量口径：最终采纳率之外，加入速度类指标（如 t50、峰值步）
- 固化正式实验预算：给出 token 与总耗时区间并写入批量运行计划
- 固化运行与恢复流程：失败重跑规则、日志与结果落盘路径统一

## 风险与应对
- 风险：当前参数可能导致四组快速饱和，组间差异不足
- 应对：优先调整研究参数而非系统参数，保持方法学一致性
- 风险：文档与代码漂移影响复现
- 应对：以 `docs/CODEMAP.md` 与 `docs/ARCHITECTURE.md` 为唯一结构基准

## 参数再标定（2026-03-11，深夜）
- 调整目标：在保持 2×2 设计结构不变的前提下，降低强组过快饱和并减少弱组贴地
- 本轮仅调整 Bass 参数，不改稳定性参数：
  - A/C：`p 0.001 -> 0.002`，`q 0.10 -> 0.085`
  - B/D：`p 0.001 -> 0.002`，`q 0.09 -> 0.07`
- 理论依据（参数方向）：
  - `p` 提升用于降低“全程无人自发采纳”的概率，减少弱组首批扩散起点缺失
  - `q` 下调用于抑制模仿驱动过强导致的快速冲顶，提升组间曲线可比性
  - 仍满足 `q > p` 的经典扩散关系，保持创新驱动弱、模仿驱动主导的文献一致方向

## 第三轮校准与冒烟测试（2026-03-11，晚间）
- 调整动因：
  - 第二轮校准（p=0.002）后，弱组 B/D 仍偶发“零扩散”贴地现象
  - 强组 A/C 仍存在过快饱和风险，但首要任务是解决弱组的冷启动问题
- 参数微调（仅针对弱组）：
  - B/D 组：`p` 进一步微调 `0.002 -> 0.003`，`q` 保持 `0.07` 不变
  - A/C 组：保持 `p=0.002, q=0.085` 不变（作为基准对照）
- 测试验证（30 agents × 18 steps × 2 reps）：
  - 结果：全组成功扩散，无零值贴地
  - 均值分布：A(0.98), C(0.97), B(0.80), D(0.80)
  - 结论：`p=0.003` 成功解决了弱组冷启动问题，且未破坏组间强弱梯队关系
- 论文写作建议：
  - 在 "Methodology" 章节专门设立 "Parameter Calibration" 小节
  - 明确交代从文献经验值到最终值的校准过程，重点阐述为解决 "Cold Start Problem"（弱组）和 "Ceiling Effect"（强组）所做的结构性微调
  - 强调该过程遵循 ABM 的 "Pattern-oriented Modeling" 规范，而非后验数据凑配

## 第四轮校准策略：结构效应分离（2026-03-12，计划）
- 理论背景：
  - **Bass 参数语义**：$p$ 代表外部自发采纳，$q$ 代表内部模仿压力 (Mahajan et al., 1995)。在强情感刺激下，若 $q$ 过高，会导致网络瞬间饱和，掩盖小世界网络的“局部聚类加速”优势 (Watts & Strogatz, 1998)。
  - **结构效应区间**：网络拓扑对扩散的影响通常在“弱连接优势区间”最为显著 (Goldenberg et al., 2001)。若传播阻力过小（$q$ 过大），结构差异将被全局噪声淹没。
- 当前问题：
  - **强组饱和 (Ceiling Effect)**：A/C 均值逼近 1.0，差异消失，无法验证 H1 (Small-World Advantage)。
  - **弱组过强 (Overshoot)**：B/D 均值升至 0.8，且无显著差异，说明 `p=0.003` 的点火效应掩盖了 D 组（随机网络）本应存在的“扩散困难”。
- 调整方案（Targeted Structural Calibration）：
  - **A/C (强组)**：大幅下调 `q` (`0.085 -> 0.055`)。
    - **目的**：增加人际传播阻力，拉长扩散周期，给小世界网络发挥“局部强化”优势的时间窗口。
  - **B/D (弱组)**：回调 `p` (`0.003 -> 0.002`)，微调 `q` (`0.07 -> 0.06`)。
    - **目的**：降低自发点火率，制造“生存压力”。在低 $p$ 下，只有具备局部聚类的 B 组能维持火种，而 D 组应更易熄火，从而拉开 B/D 差异。
- 预期结果：
  - **H1 (结构效应)**：A > C (在中期爬坡阶段显著)，B > D (在最终采纳率上显著)。
  - **H2 (情感效应)**：(A, C) > (B, D) 的阶梯效应依然显著。
  - **H3 (交互效应)**：强情感下结构差异主要体现在速度（Slope），弱情感下结构差异主要体现在广度（Final Size）。

## 文档审查路径
1. 先读 `docs/CODEMAP.md`，确认代码入口与职责边界
2. 再读 `docs/ARCHITECTURE.md`，确认研究语义与工程边界
3. 最后回看本文件，确认阶段目标与下一步执行一致
