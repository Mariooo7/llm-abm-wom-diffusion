#!/bin/bash

# 批量实验运行脚本
# 用途：运行 4 组 × 20 次 = 80 次正式实验

set -e

echo "🚀 开始批量实验 (Batch Experiment)"
echo "==================================="

# 切换到项目目录
cd "$(dirname "$0")/.."

# 激活 Python 虚拟环境
if [ -d "python/.venv" ]; then
    source python/.venv/bin/activate
    echo "✅ Python 虚拟环境已激活"
else
    echo "❌ Python 虚拟环境不存在"
    exit 1
fi

# 实验参数
GROUPS=("A" "B" "C" "D")
REPETITIONS=20
OUTPUT_DIR="data/results"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

echo ""
echo "📋 实验参数:"
echo "  实验组：${GROUPS[*]}"
echo "  重复次数：$REPETITIONS"
echo "  总实验数：$((${#GROUPS[@]} * $REPETITIONS))"
echo "  输出目录：$OUTPUT_DIR"
echo ""

# 运行实验
for GROUP in "${GROUPS[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔬 运行组 $GROUP (${GROUPS[*]})"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    for REP in $(seq 1 $REPETITIONS); do
        echo "[$GROUP-$REP/$REPETITIONS] 运行中..."
        
        python -c "
import sys
sys.path.insert(0, 'python')

from models import DiffusionModel
from config.settings import get_config
import pandas as pd
from pathlib import Path

# 加载配置
config = get_config('$GROUP')
config.seed = $REP  # 不同 repetition 用不同种子

# 创建模型
model = DiffusionModel(config)

# 运行仿真
while model.running:
    model.step()

# 保存数据
agent_data = model.datacollector.get_agent_vars_dataframe()
agent_data.to_csv('data/raw/simulation_${GROUP}_${REP}.csv')

# 输出进度
metrics = model.get_metrics()
print(f'  ✅ 完成率：{metrics[\"final_adoption_rate\"]:.1%}')
"
    done
    
    echo "✅ 组 $GROUP 完成!"
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 所有实验完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 结果位置:"
echo "  原始数据：data/raw/simulation_*.csv"
echo "  分析脚本：python scripts/analyze_results.py"
echo ""
echo "下一步:"
echo "  bash scripts/analyze_results.sh"
