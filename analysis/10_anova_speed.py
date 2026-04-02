"""
10_anova_speed.py - 峰值扩散速度的双因素方差分析

对 max_adoption_speed 变量进行 Two-way ANOVA，
检验网络拓扑对扩散峰值速度的独立主效应（H3）。

输出:
  - analysis/tables/table4_anova_speed.tex  (LaTeX 表格)
  - 终端打印 ANOVA 结果与描述性统计
"""

import pandas as pd
import pingouin as pg
from pathlib import Path

df = pd.read_csv('data/processed/analysis_dataset.csv')

df_anova = df.rename(columns={
    'network_type': 'Network',
    'wom_strength': 'WOM',
    'max_adoption_speed': 'Speed'
})

# Descriptive statistics
print("=== 各组峰值扩散速度描述性统计 ===")
print(df_anova.groupby(['Network', 'WOM'])['Speed'].agg(['mean', 'std', 'count']).round(2))

# Two-way ANOVA
anova_results = pg.anova(data=df_anova, dv='Speed', between=['Network', 'WOM'])
print('\n--- Two-way ANOVA: max_adoption_speed ---')
print(anova_results)

# LaTeX Table Generation
tex_lines = [
    r"\begin{table}[H]",
    r"    \centering",
    r"    \caption{峰值扩散速度的双因素方差分析（Two-way ANOVA）结果}",
    r"    \label{tab:anova_speed}",
    r"    \begin{tabular}{lrrrrr}",
    r"        \toprule",
    r"        方差来源 & $SS$ & $df$ & $MS$ & $F$ & $p$-value \\",
    r"        \midrule"
]

for _, row in anova_results.iterrows():
    source = row['Source']
    if source == 'Network': source = '网络拓扑 (Network)'
    elif source == 'WOM': source = '口碑强度 (WOM)'
    elif source == 'Network * WOM': source = r'网络 $\times$ 口碑'
    elif source == 'Residual': source = '残差 (Residual)'

    ss = f"{row['SS']:.4f}"
    df_val = int(row['DF'])
    ms = f"{row['MS']:.4f}"

    if pd.isna(row['F']):
        f_val = "-"
        p_val = "-"
    else:
        f_val = f"{row['F']:.2f}"
        p_val = f"{row['p_unc']:.4f}"
        if row['p_unc'] < 0.001:
            p_val = "<0.001"

    tex_lines.append(f"        {source} & {ss} & {df_val} & {ms} & {f_val} & {p_val} \\\\")

tex_lines.extend([
    r"        \bottomrule",
    r"    \end{tabular}",
    r"\end{table}"
])

out_tex = Path('analysis/tables/table4_anova_speed.tex')
out_tex.parent.mkdir(parents=True, exist_ok=True)
out_tex.write_text('\n'.join(tex_lines), encoding='utf-8')
print(f'\nLaTeX table saved to {out_tex}')
