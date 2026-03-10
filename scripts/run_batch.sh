#!/bin/bash

# 批量实验运行脚本
# 用途：运行 4 组 × 15 次 = 60 次正式实验

set -euo pipefail

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

if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

if [ -z "${LLM_API_KEY:-}" ]; then
    echo "❌ 缺少 LLM_API_KEY，请在 .env 或环境变量中设置"
    exit 1
fi

if ! command -v go >/dev/null 2>&1; then
    echo "❌ 未检测到 go 命令，无法自动拉起决策网关"
    exit 1
fi

# 实验参数
GROUPS=("A" "B" "C" "D")
REPETITIONS=15
OUTPUT_DIR="data/results"
RAW_DIR="data/raw"
LOG_INTERVAL=5
SUMMARY_FILE="$OUTPUT_DIR/batch_summary.csv"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"
mkdir -p "$RAW_DIR"

RUN_LOG="$OUTPUT_DIR/run_batch_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$RUN_LOG") 2>&1

echo ""
echo "📋 实验参数:"
echo "  实验组：${GROUPS[*]}"
echo "  重复次数：$REPETITIONS"
echo "  总实验数：$((${#GROUPS[@]} * $REPETITIONS))"
echo "  输出目录：$OUTPUT_DIR"
echo "  运行日志：$RUN_LOG"
echo "  日志间隔：每 ${LOG_INTERVAL} 步"
echo "  汇总文件：$SUMMARY_FILE"
echo ""

python -c "
import sys
import os
import time
sys.path.insert(0, 'python')
from config.settings import get_config
for g in ['A', 'B', 'C', 'D']:
    get_config(g)
print('✅ 配置预检查通过: A/B/C/D')
"

# 运行实验
for GROUP in "${GROUPS[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔬 运行组 $GROUP (${GROUPS[*]})"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    for REP in $(seq 1 $REPETITIONS); do
        echo "[$GROUP-$REP/$REPETITIONS] 启动..."
        
        python -c "
import sys
sys.path.insert(0, 'python')

from models import DiffusionModel
from config.settings import get_config
import pandas as pd
from pathlib import Path
import json

# 加载配置
config = get_config('$GROUP')
config.seed = $REP  # 不同 repetition 用不同种子

# 创建模型
model = DiffusionModel(config)
log_interval = max(1, int(os.getenv('LOG_INTERVAL', '$LOG_INTERVAL')))
started_at = time.perf_counter()
print(f'  ▶ 组{config.group}-第$REP次: n_agents={config.n_agents}, n_steps={config.n_steps}, seed={config.seed}', flush=True)

# 运行仿真
while model.running:
    model.step()
    if model.current_step % log_interval == 0 or not model.running:
        adopters = sum(1 for a in model.population.values() if a.memory.has_adopted)
        rate = adopters / config.n_agents
        elapsed = time.perf_counter() - started_at
        print(
            f'    · step {model.current_step}/{config.n_steps} adopters={adopters}/{config.n_agents} ({rate:.1%}) elapsed={elapsed:.1f}s',
            flush=True,
        )

# 保存数据
agent_data = model.datacollector.get_agent_vars_dataframe()
raw_file = Path('${RAW_DIR}/simulation_${GROUP}_${REP}.csv')
agent_data.to_csv(raw_file)

# 输出进度
metrics = model.get_metrics()
metrics_file = Path('${OUTPUT_DIR}/metrics_${GROUP}_${REP}.json')
metrics_file.write_text(
    json.dumps(metrics, ensure_ascii=False, indent=2),
    encoding='utf-8'
)
total_elapsed = time.perf_counter() - started_at
rep_index = int('$REP')
summary_path = Path('${SUMMARY_FILE}')
if not summary_path.exists():
    summary_path.write_text(
        'group,rep,seed,n_agents,n_steps,final_adoption_rate,total_adopters,model_calls,prompt_tokens,completion_tokens,total_tokens,elapsed_seconds\n',
        encoding='utf-8'
    )
summary_line = (
    f\"{config.group},{rep_index},{config.seed},{config.n_agents},{config.n_steps},\"
    f\"{metrics['final_adoption_rate']:.6f},{metrics['total_adopters']},\"
    f\"{metrics['llm_usage']['model_calls']},{metrics['llm_usage']['prompt_tokens']},\"
    f\"{metrics['llm_usage']['completion_tokens']},{metrics['llm_usage']['total_tokens']},\"
    f\"{total_elapsed:.2f}\n\"
)
with summary_path.open('a', encoding='utf-8') as summary_handle:
    summary_handle.write(summary_line)
print(f'  ✅ 完成率：{metrics[\"final_adoption_rate\"]:.1%} | raw={raw_file} | metrics={metrics_file} | elapsed={total_elapsed:.1f}s', flush=True)
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
echo "  指标数据：data/results/metrics_*.json"
echo ""
