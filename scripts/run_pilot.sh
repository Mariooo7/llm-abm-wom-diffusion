#!/bin/bash

# 预实验运行脚本
# 用途：验证仿真流程，调试代码

set -e

echo "🧪 开始预实验 (Pilot Experiment)"
echo "================================"

# 切换到项目目录
cd "$(dirname "$0")/.."

# 激活 Python 虚拟环境
if [ -d "python/.venv" ]; then
    source python/.venv/bin/activate
    echo "✅ Python 虚拟环境已激活"
else
    echo "❌ Python 虚拟环境不存在，请先创建："
    echo "   cd python && uv venv && source .venv/bin/activate"
    exit 1
fi

# 运行预实验 (组 A, 单次)
echo ""
echo "📊 运行组 A (小世界 + 强情感) - 单次仿真..."
python -c "
import sys
sys.path.insert(0, 'python')

from models import DiffusionModel
from config.settings import get_config
from loguru import logger
import json

# 加载配置
config = get_config('A')
logger.info(f'使用配置：组 A (小世界 + 强情感)')

# 创建模型
model = DiffusionModel(config)
logger.info(f'模型已创建：{config.n_agents} 个智能体，{model.network.number_of_edges()} 条边')

# 运行仿真
step = 0
while model.running and step < 20:  # 预实验只跑 20 步
    model.step()
    step += 1
    
    if step % 5 == 0:
        adopters = sum(1 for a in model.population.values() if a.memory.has_adopted)
        rate = adopters / config.n_agents
        logger.info(f'步数 {step}: 采纳者 {adopters}/{config.n_agents} ({rate:.1%})')

# 输出指标
metrics = model.get_metrics()
print()
print('📊 预实验结果:')
print(json.dumps(metrics, indent=2, ensure_ascii=False))
"

echo ""
echo "✅ 预实验完成！"
echo ""
echo "下一步:"
echo "1. 检查结果是否合理"
echo "2. 如有问题，修复代码"
echo "3. 运行正式实验：bash scripts/run_batch.sh"
