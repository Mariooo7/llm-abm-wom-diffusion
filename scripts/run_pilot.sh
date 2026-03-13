#!/bin/bash

# 预实验运行脚本
# 用途：预实验入口（内部统一复用 python/run_preflight.py --mode smoke）

set -euo pipefail

echo "🧪 开始预实验 (Pilot Experiment)"
echo "================================"

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
    echo "❌ Python 虚拟环境不存在，请先创建："
    echo "   uv venv .venv && source .venv/bin/activate"
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

GROUP="${GROUP:-A}"
SEED="${SEED:-101}"
N_AGENTS="${N_AGENTS:-50}"
N_STEPS="${N_STEPS:-20}"
LOG_INTERVAL="${LOG_INTERVAL:-5}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"

echo ""
echo "📊 运行预实验（统一走 run_preflight.py）"
python python/run_preflight.py \
    --mode smoke \
    --group "$GROUP" \
    --seed "$SEED" \
    --n-agents "$N_AGENTS" \
    --n-steps "$N_STEPS" \
    --timeout-seconds "$TIMEOUT_SECONDS" \
    --log-interval "$LOG_INTERVAL"

echo ""
echo "✅ 预实验完成！"
echo ""
echo "下一步：如结果合理，运行正式实验：bash scripts/run_batch.sh"
