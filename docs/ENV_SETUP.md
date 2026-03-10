# 🚀 环境配置指南

**最后更新**: 2026-03-10

---

## 📋 前置要求

| 工具 | 版本 | 用途 | 安装命令 |
|------|------|------|----------|
| Python | 3.11+ | ABM 仿真 | `brew install python@3.11` |
| Go | 1.23+ | LLM 智能体 | `brew install go@1.23` |
| uv | latest | Python 包管理 | `pip install -U uv` |
| Git | latest | 版本控制 | `brew install git` |

---

## 🔧 Python 环境配置

### 1. 创建虚拟环境

```bash
cd thesis-simulation/python

# 使用 uv (推荐)
uv venv
source .venv/bin/activate

# 或使用标准 venv
python -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
# 使用 uv (更快)
uv pip install -r requirements.txt

# 或使用 pip
pip install -r requirements.txt
```

### 3. 验证安装

```bash
python -c "
import mesa
import networkx as nx
import pandas as pd
import numpy as np

print('✅ Mesa:', mesa.__version__)
print('✅ NetworkX:', nx.__version__)
print('✅ pandas:', pd.__version__)
print('✅ numpy:', np.__version__)
print()
print('🎉 Python 环境配置完成！')
"
```

---

## 🦫 Go 环境配置

### 1. 安装 Go

```bash
# macOS
brew install go@1.23

# 验证安装
go version  # 应 >= go1.23
```

### 2. 配置环境变量

```bash
# 添加到 ~/.zshrc 或 ~/.bashrc
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin
export PATH=$PATH:/usr/local/go/bin

# 生效
source ~/.zshrc
```

### 3. 下载依赖

```bash
cd thesis-simulation/go

# 下载模块
go mod download
go mod tidy

# 验证
go list -m all | grep eino
```

### 4. 测试编译

```bash
go build -o bin/main cmd/main.go
ls -lh bin/
```

---

## 🔑 API Key 配置

### 1. 复制环境变量模板

```bash
cd thesis-simulation
cp .env.example .env
```

### 2. 编辑 .env 文件

```bash
vim .env
# 或
nano .env
```

### 3. 填入你的 API Key

```bash
# LLM 配置
LLM_PROVIDER=aliyun_bailian
LLM_API_KEY=your-actual-api-key-here
LLM_MODEL=qwen3.5-flash
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=700
LLM_SEED=42

# 实验配置
EXPERIMENT_GROUP=A
N_REPETITIONS=15
USE_LLM=true
```

### 4. 获取 API Key

1. 按最终确定的供应商创建 API Key
2. 将 API Key 写入 `.env` 的 `LLM_API_KEY`
3. 同步填写 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`
4. 在正式实验前执行一次最小调用验证

### 5. 参数建议与调优方向

- `LLM_TEMPERATURE=0.2`：偏稳定、低发散，适合学术化表达与复核。
- `LLM_MAX_TOKENS=700`：对“结论+机制+指标”结构化输出通常足够，控制成本与延迟。
- `LLM_SEED=42`：在模型支持时降低同条件波动，增强可复现性。
- 若输出经常被截断，可将 `LLM_MAX_TOKENS` 调高到 `900~1200`。

---

## ✅ 验证环境

### Python 测试

```bash
cd thesis-simulation

# 激活虚拟环境
source python/.venv/bin/activate

# 运行预实验
bash scripts/run_pilot.sh
```

**预期输出**:
```
🧪 开始预实验 (Pilot Experiment)
✅ Python 虚拟环境已激活
📊 运行组 A (小世界 + 强情感) - 单次仿真...
2026-03-02 12:00:00 | INFO | 使用配置：组 A (小世界 + 强情感)
2026-03-02 12:00:00 | INFO | 模型已创建：200 个智能体，800 条边
2026-03-02 12:00:05 | INFO | 步数 5: 采纳者 12/200 (6.0%)
2026-03-02 12:00:10 | INFO | 步数 10: 采纳者 35/200 (17.5%)
2026-03-02 12:00:15 | INFO | 步数 15: 采纳者 78/200 (39.0%)
2026-03-02 12:00:20 | INFO | 步数 20: 采纳者 125/200 (62.5%)

📊 预实验结果:
{
  "total_adopters": 125,
  "final_adoption_rate": 0.625,
  ...
}

✅ 预实验完成！
```

### Go 测试 (可选)

```bash
cd thesis-simulation/go

# 加载环境变量
set -a
source ../.env
set +a

# 运行测试
go run cmd/main.go
```

**预期输出**:
```
Provider: aliyun_bailian
Model: qwen3.5-flash
Temperature: 0.20
MaxTokens: 700
Assistant: ...
TokenUsage => model_calls=1 input_tokens=552 output_tokens=486 total_tokens=1038
TokenUsageAvgPerCall => input=552.00 output=486.00 total=1038.00
```

---

## 🐛 常见问题

### Q1: `uv: command not found`

**解决**:
```bash
pip install -U uv
# 或
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Q2: `go: command not found`

**解决**:
```bash
brew install go@1.23
# 添加到 PATH
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.zshrc
source ~/.zshrc
```

### Q3: Python 依赖安装失败

**解决**:
```bash
# 升级 pip
pip install --upgrade pip

# 清除缓存
pip cache purge

# 重新安装
pip install -r requirements.txt --no-cache-dir
```

### Q4: API Key 无效

**解决**:
1. 检查 `.env` 文件是否存在
2. 确认 API Key 格式正确（无多余空格）
3. 验证 API Key 是否已激活（登录控制台检查）
4. 检查网络连接

### Q5: `ModuleNotFoundError: No module named 'mesa'`

**解决**:
```bash
# 确认已激活虚拟环境
which python  # 应指向 .venv 目录

# 重新激活
source python/.venv/bin/activate

# 重新安装
pip install -r python/requirements.txt
```

---

## 📊 环境检查清单

- [ ] Python 3.11+ 已安装
- [ ] Go 1.23+ 已安装 (可选)
- [ ] uv 已安装
- [ ] Python 虚拟环境已创建
- [ ] 依赖已安装
- [ ] `.env` 文件已配置
- [ ] API Key 已填入
- [ ] 预实验运行成功

---

## 🎯 下一步

环境配置完成后：

1. **运行预实验**: `bash scripts/run_pilot.sh`
2. **检查结果**: 查看输出是否合理
3. **运行批量实验**: `bash scripts/run_batch.sh`
4. **分析结果**: `python scripts/analyze_results.py`

---

*如有问题，请查阅 README.md 或提交 Issue*
