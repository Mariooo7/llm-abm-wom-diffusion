import pandas as pd
import numpy as np
from pathlib import Path
import json

# 设定目标数据目录（使用最新的一次正式运行结果）
RESULTS_DIR = Path("data/results/formal_20260319_174207")
OUTPUT_FILE = Path("data/processed/analysis_dataset.csv")

def calculate_time_to_threshold(timeline_df: pd.DataFrame, threshold: float) -> int:
    """计算达到特定采纳率阈值所需的时间步数（如果没有达到，返回最大步数）"""
    passed = timeline_df[timeline_df['adoption_rate'] >= threshold]
    if len(passed) > 0:
        return int(passed.iloc[0]['step'])
    return int(timeline_df['step'].max())

def process_single_run(run_id: str, group: str, timeline_file: Path, metrics_file: Path) -> dict:
    """处理单个 Run 的数据并提取核心统计指标"""
    # 1. 读取基础配置
    with open(metrics_file, 'r') as f:
        metrics = json.load(f)
    
    config = metrics['config']
    network_type = config['network_type']
    wom_strength = config['wom_strength']
    
    # 2. 读取时序曲线
    timeline_df = pd.read_csv(timeline_file)
    
    # 3. 提取扩散指标
    t_10 = calculate_time_to_threshold(timeline_df, 0.10)
    t_50 = calculate_time_to_threshold(timeline_df, 0.50)
    t_90 = calculate_time_to_threshold(timeline_df, 0.90)
    
    # 4. 计算最大扩散速度 (单步新增采纳者的最大值)
    timeline_df['new_adopters'] = timeline_df['total_adopters'].diff().fillna(0)
    max_adoption_speed = float(timeline_df['new_adopters'].max())
    
    return {
        'run_id': run_id,
        'group': group,
        'network_type': network_type,
        'wom_strength': wom_strength,
        'final_adoption_rate': float(metrics['result']['final_adoption_rate']),
        't_10': t_10,
        't_50': t_50,
        't_90': t_90,
        'max_adoption_speed': max_adoption_speed
    }

def main():
    print(f"开始处理目录: {RESULTS_DIR}")
    
    # 读取批次汇总文件
    summary_df = pd.read_csv(RESULTS_DIR / "batch_summary.csv")
    
    # 只要出现在 summary_df 里的通常都是跑完的
    records = []
    for _, row in summary_df.iterrows():
        run_id = f"{row['group']}_r{row['rep']}_s{row['seed']}"
        group = row['group']
        timeline_file = Path(row['adoption_timeline_file'])
        metrics_file = Path(row['metrics_file'])
        
        if timeline_file.exists() and metrics_file.exists():
            record = process_single_run(run_id, group, timeline_file, metrics_file)
            records.append(record)
        else:
            print(f"警告: 找不到 Run {run_id} 的原始文件，跳过。")
            
    # 转换为 DataFrame 并导出
    output_df = pd.DataFrame(records)
    
    # 确保输出目录存在
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(OUTPUT_FILE, index=False)
    
    print(f"\n数据清洗与提取完成！共处理 {len(output_df)} 条成功记录。")
    print(f"统计宽表已保存至: {OUTPUT_FILE}")
    print("\n数据前 5 行预览:")
    print(output_df.head().to_string())

if __name__ == "__main__":
    main()
