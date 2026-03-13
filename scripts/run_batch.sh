#!/bin/bash

# 批量实验运行脚本
# 用途：运行 4 组 × 15 次 = 60 次正式实验

set -euo pipefail

echo "🚀 开始批量实验 (Batch Experiment)"
echo "==================================="

# 切换到项目目录
cd "$(dirname "$0")/.."

# 激活 Python 虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Python 虚拟环境已激活 (.venv)"
elif [ -d "python/.venv" ]; then
    source python/.venv/bin/activate
    echo "✅ Python 虚拟环境已激活 (python/.venv)"
else
    echo "❌ Python 虚拟环境不存在"
    exit 1
fi

if [ -f ".env" ]; then
    while IFS='=' read -r key value; do
        key="$(echo "$key" | xargs)"
        value="$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed 's/^"//;s/"$//')"
        if [ -z "$key" ]; then
            continue
        fi
        case "$key" in
            \#*)
                continue
                ;;
        esac
        if [ -z "${!key+x}" ]; then
            export "$key=$value"
        fi
    done < .env
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
EXP_GROUPS=("A" "B" "C" "D")
REPETITIONS="${REPETITIONS:-15}"
SEED_START="${SEED_START:-12001}"
N_AGENTS="${N_AGENTS:-100}"
N_STEPS="${N_STEPS:-60}"
LOG_INTERVAL="${LOG_INTERVAL:-10}"
REPETITION_WORKERS="${REPETITION_WORKERS:-3}"
RUN_RETRIES="${RUN_RETRIES:-2}"
RETRY_BACKOFF_SECONDS="${RETRY_BACKOFF_SECONDS:-3}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-210}"
LLM_MAX_INFLIGHT="${LLM_MAX_INFLIGHT:-3}"
LLM_RETRY_MAX_ATTEMPTS="${LLM_RETRY_MAX_ATTEMPTS:-8}"
LLM_RETRY_BASE_MS="${LLM_RETRY_BASE_MS:-600}"
LLM_RETRY_JITTER_MS="${LLM_RETRY_JITTER_MS:-300}"
RUN_TAG="${RUN_TAG:-formal_$(date +%Y%m%d_%H%M%S)}"
OUTPUT_DIR="${OUTPUT_DIR:-data/results/$RUN_TAG}"
RAW_DIR="${RAW_DIR:-data/raw/$RUN_TAG}"
SUMMARY_FILE="${SUMMARY_FILE:-$OUTPUT_DIR/batch_summary.csv}"
if [ "$REPETITION_WORKERS" -gt "$LLM_MAX_INFLIGHT" ]; then
    echo "⚠️ REPETITION_WORKERS=${REPETITION_WORKERS} 高于 LLM_MAX_INFLIGHT=${LLM_MAX_INFLIGHT}，已自动下调为 ${LLM_MAX_INFLIGHT}"
    REPETITION_WORKERS="${LLM_MAX_INFLIGHT}"
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"
mkdir -p "$RAW_DIR"

RUN_LOG="$OUTPUT_DIR/run_batch_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$RUN_LOG") 2>&1

echo ""
echo "📋 实验参数:"
echo "  实验组：${EXP_GROUPS[*]}"
echo "  重复次数：$REPETITIONS"
echo "  Agent 数：$N_AGENTS"
echo "  步数：$N_STEPS"
echo "  总实验数：$((${#EXP_GROUPS[@]} * $REPETITIONS))"
echo "  输出目录：$OUTPUT_DIR"
echo "  运行日志：$RUN_LOG"
echo "  日志间隔：每 ${LOG_INTERVAL} 步"
echo "  汇总文件：$SUMMARY_FILE"
echo "  并行 workers：$REPETITION_WORKERS"
echo "  单次失败重试：$RUN_RETRIES"
echo "  重试退避起始秒数：$RETRY_BACKOFF_SECONDS"
echo "  LLM 超时秒数：$TIMEOUT_SECONDS"
echo "  LLM 最大并发请求：$LLM_MAX_INFLIGHT"
echo ""

export LLM_MAX_INFLIGHT
export LLM_RETRY_MAX_ATTEMPTS
export LLM_RETRY_BASE_MS
export LLM_RETRY_JITTER_MS
export LLM_REQUEST_TIMEOUT_SECONDS="$TIMEOUT_SECONDS"

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

python python/run_preflight.py \
    --mode formal_batch \
    --groups "${EXP_GROUPS[@]}" \
    --repetitions "$REPETITIONS" \
    --seed-start "$SEED_START" \
    --n-agents "$N_AGENTS" \
    --n-steps "$N_STEPS" \
    --repetition-workers "$REPETITION_WORKERS" \
    --run-retries "$RUN_RETRIES" \
    --retry-backoff-seconds "$RETRY_BACKOFF_SECONDS" \
    --timeout-seconds "$TIMEOUT_SECONDS" \
    --log-interval "$LOG_INTERVAL" \
    --output-dir "$OUTPUT_DIR" \
    --raw-dir "$RAW_DIR" \
    --summary-file "$SUMMARY_FILE"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 所有实验完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 结果位置:"
echo "  原始数据：data/raw/simulation_*.csv"
echo "  指标数据：data/results/metrics_*.json"
echo ""
