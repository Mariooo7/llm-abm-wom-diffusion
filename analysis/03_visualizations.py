import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# 设置路径
RESULTS_DIR = Path("data/results/formal_20260319_174207")
PROCESSED_DATA_FILE = Path("data/processed/analysis_dataset.csv")
FIGURES_DIR = Path("analysis/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# 设置学术风格绘图
sns.set_theme(style="whitegrid", context="paper", font_scale=1.5)
# 使用色盲友好的调色板，并指定特定颜色以区分组别
palette = sns.color_palette("colorblind")
group_colors = {
    'A (Small-World / Strong)': palette[0],
    'C (Random / Strong)': palette[1],
    'B (Small-World / Weak)': palette[2],
    'D (Random / Weak)': palette[3]
}

def load_timeline_data():
    """读取所有成功的 Run 的时序数据并合并为一个长表"""
    summary_df = pd.read_csv(RESULTS_DIR / "batch_summary.csv")
    
    all_timelines = []
    for _, row in summary_df.iterrows():
        group = row['group']
        seed = row['seed']
        timeline_file = Path(row['adoption_timeline_file'])
        
        if timeline_file.exists():
            df = pd.read_csv(timeline_file)
            df['run_id'] = f"{group}_r{row['rep']}_s{seed}"
            df['group'] = group
            
            # 为了图例好看，我们映射出人类可读的组名
            if group == 'A':
                df['group_label'] = 'A (Small-World / Strong)'
            elif group == 'B':
                df['group_label'] = 'B (Small-World / Weak)'
            elif group == 'C':
                df['group_label'] = 'C (Random / Strong)'
            elif group == 'D':
                df['group_label'] = 'D (Random / Weak)'
                
            all_timelines.append(df)
            
    return pd.concat(all_timelines, ignore_index=True)

def plot_s_curves(timeline_df: pd.DataFrame):
    """绘制带置信区间的 S 曲线 (Time Series Plot)"""
    print("正在绘制 S 曲线...")
    plt.figure(figsize=(10, 6))
    
    # lineplot 会自动计算每个 step 的均值，并画出 95% 置信区间 (ci=95)
    ax = sns.lineplot(
        data=timeline_df,
        x='step',
        y='adoption_rate',
        hue='group_label',
        palette=group_colors,
        linewidth=2.5,
        errorbar=('ci', 95)
    )
    
    plt.title('Diffusion of Innovation over Time', pad=20, fontweight='bold')
    plt.xlabel('Simulation Steps')
    plt.ylabel('Adoption Rate')
    plt.ylim(0, 1.05)
    plt.xlim(0, 60)
    
    # 调整图例
    plt.legend(title='Experimental Groups', loc='lower right', frameon=True, fancybox=True)
    
    # 保存高分辨率图片
    out_path = FIGURES_DIR / 'fig1_adoption_s_curves.png'
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 图表已保存: {out_path}")

def plot_boxplots(metrics_df: pd.DataFrame):
    """绘制最终规模和速度的箱线图"""
    print("正在绘制箱线图...")
    
    # 我们需要为 metrics_df 增加一个人类可读的 label
    def get_label(row):
        if row['group'] == 'A': return 'A (Small-World / Strong)'
        if row['group'] == 'B': return 'B (Small-World / Weak)'
        if row['group'] == 'C': return 'C (Random / Strong)'
        if row['group'] == 'D': return 'D (Random / Weak)'
    metrics_df['group_label'] = metrics_df.apply(get_label, axis=1)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # 图 1：最终采纳率
    sns.boxplot(
        data=metrics_df,
        x='group_label',
        y='final_adoption_rate',
        palette=group_colors,
        ax=ax1,
        width=0.6,
        fliersize=5
    )
    sns.stripplot(
        data=metrics_df,
        x='group_label',
        y='final_adoption_rate',
        color='black',
        alpha=0.4,
        jitter=True,
        ax=ax1
    )
    ax1.set_title('Final Adoption Rate by Group', fontweight='bold')
    ax1.set_xlabel('')
    ax1.set_ylabel('Final Adoption Rate')
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45, ha='right')
    ax1.set_ylim(-0.05, 1.05)
    
    # 图 2：扩散速度 (T50) - 注意只画强组，因为弱组根本没达到 50%
    strong_df = metrics_df[metrics_df['wom_strength'] == 'strong']
    sns.boxplot(
        data=strong_df,
        x='group_label',
        y='t_50',
        palette=[group_colors['A (Small-World / Strong)'], group_colors['C (Random / Strong)']],
        ax=ax2,
        width=0.4
    )
    sns.stripplot(
        data=strong_df,
        x='group_label',
        y='t_50',
        color='black',
        alpha=0.4,
        jitter=True,
        ax=ax2
    )
    ax2.set_title('Time to 50% Adoption (Strong WOM Only)', fontweight='bold')
    ax2.set_xlabel('')
    ax2.set_ylabel('Steps (T50)')
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45, ha='right')
    
    out_path = FIGURES_DIR / 'fig2_final_metrics_boxplots.png'
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 图表已保存: {out_path}")

def main():
    if not PROCESSED_DATA_FILE.exists():
        print(f"找不到提取的指标文件 {PROCESSED_DATA_FILE}，请先运行 01_extract_metrics.py")
        return
        
    metrics_df = pd.read_csv(PROCESSED_DATA_FILE)
    timeline_df = load_timeline_data()
    
    if timeline_df.empty:
        print("未能加载到时序数据，请检查原始数据目录。")
        return
        
    plot_s_curves(timeline_df)
    plot_boxplots(metrics_df)
    
    print("\n所有图表绘制完成！请前往 analysis/figures/ 查看高清 PNG。")

if __name__ == "__main__":
    main()
