import pandas as pd
from pathlib import Path
from scipy.stats import ttest_ind

DATA_DIR = Path('data/raw/formal_20260319_174207')
groups = {'A': ('Small_World', 'Strong'), 'B': ('Small_World', 'Weak'), 'C': ('Random', 'Strong'), 'D': ('Random', 'Weak')}
records = []
for csv_path in DATA_DIR.glob('simulation_*.csv'):
    name = csv_path.name
    group = name.split('_')[1]
    df = pd.read_csv(csv_path)
    final_rate = df['adopt_final'].mean()
    net, wom = groups[group]
    records.append({'Network': net, 'WOM': wom, 'AdoptionRate': final_rate})

df_anova = pd.DataFrame(records)
print("=== Group Means & Std ===")
print(df_anova.groupby(['Network', 'WOM']).agg(['mean', 'std', 'count']))

group_b = df_anova[(df_anova['Network']=='Small_World') & (df_anova['WOM']=='Weak')]['AdoptionRate']
group_d = df_anova[(df_anova['Network']=='Random') & (df_anova['WOM']=='Weak')]['AdoptionRate']
t_stat, p_val = ttest_ind(group_b, group_d)
print(f'\nT-test B (SW-Weak) vs D (R-Weak): t={t_stat:.4f}, p={p_val:.4f}')

group_a = df_anova[(df_anova['Network']=='Small_World') & (df_anova['WOM']=='Strong')]['AdoptionRate']
group_c = df_anova[(df_anova['Network']=='Random') & (df_anova['WOM']=='Strong')]['AdoptionRate']
t_stat_str, p_val_str = ttest_ind(group_a, group_c)
print(f'T-test A (SW-Strong) vs C (R-Strong): t={t_stat_str:.4f}, p={p_val_str:.4f}')
