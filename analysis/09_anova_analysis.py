import pandas as pd
import pingouin as pg
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from plot_config import configure_matplotlib, figure_path

configure_matplotlib()
sns.set_theme(style="whitegrid", context="paper", font_scale=1.5)

df = pd.read_csv('data/processed/analysis_dataset.csv')
# df has columns: run_id,group,network_type,wom_strength,final_adoption_rate,t_10,t_50,t_90,max_adoption_speed

# We need to rename for the previous ANOVA script logic
df_anova = df.rename(columns={
    'network_type': 'Network',
    'wom_strength': 'WOM',
    'final_adoption_rate': 'AdoptionRate'
})

print("=== True Group Means ===")
print(df_anova.groupby(['Network', 'WOM'])['AdoptionRate'].agg(['mean', 'std', 'count']))

# 1. ANOVA Table
anova_results = pg.anova(data=df_anova, dv='AdoptionRate', between=['Network', 'WOM'])
print('\n--- Two-way ANOVA Results ---')
print(anova_results)

# LaTeX Table Generation
tex_lines = [
    r"\begin{table}[H]",
    r"    \centering",
    r"    \caption{最终采纳率的双因素方差分析（Two-way ANOVA）结果}",
    r"    \label{tab:anova}",
    r"    \begin{tabular}{lrrrrr}",
    r"        \toprule",
    r"        方差来源 & $SS$ & $df$ & $MS$ & $F$ & $p$-value \\",
    r"        \midrule"
]

for _, row in anova_results.iterrows():
    source = row['Source']
    if source == 'Network': source = '网络拓扑 (Network)'
    elif source == 'WOM': source = '口碑强度 (WOM)'
    elif source == 'Network * WOM': source = '网络 $\times$ 口碑'
    elif source == 'Residual': source = '残差 (Residual)'
    
    ss = f"{row['SS']:.4f}"
    df_val = int(row['DF'])
    ms = f"{row['MS']:.4f}"
    
    if pd.isna(row['F']):
        f_val = "-"
        p_val = "-"
    else:
        f_val = f"{row['F']:.2f}"
        p_val = f"{row['p-unc']:.4f}"
        if row['p-unc'] < 0.001:
            p_val = "<0.001"
            
    tex_lines.append(f"        {source} & {ss} & {df_val} & {ms} & {f_val} & {p_val} \\\\")

tex_lines.extend([
    r"        \bottomrule",
    r"    \end{tabular}",
    r"\end{table}"
])

out_tex = Path('analysis/tables/table3_anova.tex')
out_tex.parent.mkdir(parents=True, exist_ok=True)
out_tex.write_text('\n'.join(tex_lines), encoding='utf-8')

# 2. Interaction Plot
plt.figure(figsize=(8, 6))
sns.pointplot(data=df_anova, x='WOM', y='AdoptionRate', hue='Network', 
              dodge=True, markers=['o', 's'], capsize=.1, err_kws={'linewidth': 1.5})
plt.title('Interaction Effect on Final Adoption Rate')
plt.ylabel('Final Adoption Rate')
plt.xlabel('WOM Strength')
plt.legend(title='Network Topology')
plt.tight_layout()
plt.savefig(figure_path('fig6_interaction_plot'))
