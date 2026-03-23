import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols
from pathlib import Path

DATA_FILE = Path("data/processed/analysis_dataset.csv")

def run_two_way_anova(df: pd.DataFrame, dependent_var: str, title: str):
    print(f"\n{'='*50}")
    print(f"=== {title} ===")
    print(f"{'='*50}")
    
    # 构造公式，例如 'final_adoption_rate ~ C(network_type) + C(wom_strength) + C(network_type):C(wom_strength)'
    formula = f'{dependent_var} ~ C(network_type) + C(wom_strength) + C(network_type):C(wom_strength)'
    
    model = ols(formula, data=df).fit()
    anova_table = sm.stats.anova_lm(model, typ=2)
    
    # 为了更好看，重命名列和行
    anova_table.columns = ['Sum of Sq', 'df', 'F-value', 'PR(>F)']
    anova_table.index = ['Network Type', 'WOM Strength', 'Network × WOM', 'Residual']
    
    print(anova_table.round(4))
    
    # 显著性判断
    p_interaction = anova_table.loc['Network × WOM', 'PR(>F)']
    if p_interaction < 0.05:
        print("\n=> 结论: 存在显著的【交互效应】 (p < 0.05)。网络结构的作用取决于口碑强度！")
    else:
        print("\n=> 结论: 交互效应不显著 (p >= 0.05)。")

def run_one_way_anova_for_strong(df: pd.DataFrame):
    print(f"\n{'='*50}")
    print(f"=== One-way ANOVA: T50 in Strong WOM Groups (A vs C) ===")
    print(f"{'='*50}")
    
    df_strong = df[df['wom_strength'] == 'strong']
    model = ols('t_50 ~ C(network_type)', data=df_strong).fit()
    anova_table = sm.stats.anova_lm(model, typ=2)
    
    anova_table.columns = ['Sum of Sq', 'df', 'F-value', 'PR(>F)']
    anova_table.index = ['Network Type', 'Residual']
    
    print(anova_table.round(4))
    
    p_val = anova_table.loc['Network Type', 'PR(>F)']
    if p_val < 0.05:
        print("\n=> 结论: 在强产品中，不同网络结构的扩散速度 (T50) 有显著差异 (p < 0.05)。")
    else:
        print("\n=> 结论: 在强产品中，网络结构对扩散速度的影响不显著。")

def main():
    if not DATA_FILE.exists():
        print(f"找不到数据文件 {DATA_FILE}，请先运行 01_extract_metrics.py")
        return
        
    df = pd.read_csv(DATA_FILE)
    
    print("各组均值概览:")
    summary = df.groupby(['network_type', 'wom_strength']).agg({
        'final_adoption_rate': ['mean', 'std'],
        't_50': ['mean', 'std']
    }).round(3)
    print(summary)
    
    # 1. 检验最终采纳率的主效应和交互效应
    run_two_way_anova(df, 'final_adoption_rate', "Two-way ANOVA: Final Adoption Rate")
    
    # 2. 检验扩散速度的主效应和交互效应
    run_two_way_anova(df, 't_50', "Two-way ANOVA: Time to 50% Adoption (T50)")
    
    # 3. 单独检验强组中的 T50 差异 (H2a)
    run_one_way_anova_for_strong(df)

if __name__ == "__main__":
    main()
