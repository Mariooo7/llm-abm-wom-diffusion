import pandas as pd
from pathlib import Path

PROCESSED_DATA_FILE = Path("data/processed/analysis_dataset.csv")
OUTPUT_DIR = Path("analysis/tables")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("正在生成描述性统计表格...")
    
    if not PROCESSED_DATA_FILE.exists():
        print(f"找不到 {PROCESSED_DATA_FILE}，请先运行 01_extract_metrics.py")
        return
        
    df = pd.read_csv(PROCESSED_DATA_FILE)
    
    # 按照论文规范，我们关注 Final Adoption Rate, T_50, 和 Max Adoption Speed
    # 计算均值 (Mean) 和标准差 (SD)
    desc_stats = df.groupby(['group', 'network_type', 'wom_strength']).agg({
        'final_adoption_rate': ['mean', 'std', 'min', 'max'],
        't_50': ['mean', 'std'],
        'max_adoption_speed': ['mean', 'std']
    }).round(3)
    
    # 重命名列以符合学术论文习惯
    desc_stats.columns = [
        'Final Scale (Mean)', 'Final Scale (SD)', 'Final Scale (Min)', 'Final Scale (Max)',
        'T50 (Mean)', 'T50 (SD)',
        'Max Speed (Mean)', 'Max Speed (SD)'
    ]
    
    # 重置索引以便导出好看
    desc_stats = desc_stats.reset_index()
    
    # 为了更好读，把组别信息格式化一下
    desc_stats['network_type'] = desc_stats['network_type'].map({'small_world': 'Small-World', 'random': 'Random'})
    desc_stats['wom_strength'] = desc_stats['wom_strength'].map({'strong': 'Strong', 'weak': 'Weak'})
    desc_stats.rename(columns={'group': 'Group', 'network_type': 'Network', 'wom_strength': 'WOM'}, inplace=True)
    
    # 导出 CSV
    csv_path = OUTPUT_DIR / 'table1_descriptive_statistics.csv'
    desc_stats.to_csv(csv_path, index=False)
    
    # 导出 LaTeX 代码 (方便直接贴进 Overleaf 或者 LaTeX 格式的论文中)
    latex_path = OUTPUT_DIR / 'table1_descriptive_statistics.tex'
    latex_code = desc_stats.to_latex(index=False, float_format="%.3f")
    with open(latex_path, 'w') as f:
        f.write(latex_code)
        
    print("\n==== 描述性统计表预览 ====")
    print(desc_stats.to_string())
    print("\n✅ 表格已保存至:")
    print(f"  - {csv_path}")
    print(f"  - {latex_path}")

if __name__ == "__main__":
    main()
