# 数据分析与可视化执行计划 (Analysis Plan)

**状态**: 草案 (Draft)  
**目标**: 确保数据清洗、统计检验与可视化的全过程符合“可复现研究 (Reproducible Research)”标准。

## 1. 核心原则
- **数据不可变 (Immutable Data)**: 永远不要修改 `data/results/` 下的原始输出文件。所有的清洗和转换都必须通过代码完成，并将中间结果写入 `data/processed/`。
- **脚本化一切 (Script Everything)**: 从读取 CSV 到生成最终 PDF 图表，全部用 Python 脚本或 Jupyter Notebook 实现。坚决杜绝在 Excel 中手动复制粘贴或调整图表。
- **图表学术化 (Academic Plotting)**: 遵循 APA 格式规范（黑白灰为主，或高对比度色盲友好色系），提供高分辨率 (300 DPI) 的导出。

## 2. 目录规约
数据分析代码统一放置在根目录的 `notebooks/` 或 `analysis/` 中：
- `analysis/01_extract_metrics.py`: 读取原始 `adoption_timeline_*.csv` 和 `metrics_*.json`，计算 T50、最终规模等，合并输出宽表到 `data/processed/`。
- `analysis/02_statistical_tests.py`: 读取宽表，执行 Two-way ANOVA 检验，输出统计结果表格。
- `analysis/03_visualizations.py`: 绘制 S 曲线、箱线图，并将高清图片输出至 `analysis/figures/`。

## 3. 具体执行步骤

### 阶段一：数据清洗与降维 (Data Wrangling)
**目标产出**：`data/processed/analysis_dataset.csv`
- 字段应包括：`run_id`, `group`, `network_type`, `wom_strength`, `final_adoption_rate`, `t_10`, `t_50`, `t_90`, `max_adoption_speed`。

### 阶段二：统计检验 (Statistical Inference)
**目标产出**：终端打印或文本输出的 ANOVA 表格。
- **检验 1**: 最终采纳率的 Two-way ANOVA (Network Type × WOM Strength)。
- **检验 2**: T50 (扩散速度) 的 Two-way ANOVA (仅在强组 A/C 间重点比较)。

### 阶段三：学术可视化 (Data Visualization)
**目标产出**：直接用于论文的图表文件（存放在 `analysis/figures/` 下）。
- `fig1_adoption_curves.pdf`: 四组 S 曲线的时间序列均值与置信区间阴影图。
- `fig2_final_scale_boxplot.pdf`: 最终采纳率的分组箱线图 (展示分布方差)。

## 4. 约定与变更管理
本计划为基线参考。在实际处理数据时，如发现新的统计特征（如弱组的特殊双峰分布），可在代码中灵活追加探索性分析 (EDA)，但须保持代码结构的清晰模块化。