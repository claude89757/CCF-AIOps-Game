# CCF AIOps挑战赛 - React模式故障诊断智能体

这是一个专门为**2025年CCF国际AIOps挑战赛**设计的智能体，基于React模式（Reasoning + Acting）进行微服务系统的故障诊断。

## 🏆 比赛适配特性

- ✅ **完全符合比赛要求**: 支持input.json到answer.json的完整工作流
- ✅ **评分标准优化**: 针对LA、TA、效率和可解释性四个维度优化
- ✅ **输出稳定性**: temperature=0确保结果可复现
- ✅ **容器化部署**: Docker支持，符合比赛提交要求
- ✅ **批量处理**: 自动处理N个故障案例

## 🚀 快速使用

### 环境准备
```bash
# 设置必需的环境变量
export OPENAI_API_TOKEN="your-api-key"
export BASE_URL="https://uni-api.cstcloud.cn/v1"
```

### 一键运行（推荐）
```bash
# 构建Docker并生成answer.json
./run.sh
```

### 直接运行
```bash

# 使用命令行参数
python src/agent_run.py --model deepseek-v3:671b --concurrency 15 --input input.json --output answer.json

# 串行处理（设置并发为1）
python src/agent_run.py --concurrency 1 --input input.json --output answer.json

# 调试模式下的并行处理
python src/agent_run.py --debug --concurrency 5 --input input.json --output answer.json
```

### 命令行参数说明

```bash
python src/agent_run.py [options]

必选参数:
  无（使用默认值）

可选参数:
  -h, --help            显示帮助信息
  -m, --model {deepseek-v3:671b,qwen3:235b,deepseek-r1:671b-0528}
                        指定使用的模型 (默认: deepseek-v3:671b)
  -i, --iterations INT  最大迭代次数 (默认: 30)
  -r, --retries INT     模型调用最大重试次数 (默认: 5)
  -c, --concurrency INT 并发处理数量 (默认: 10, 设置为1表示串行处理)
  --input FILE          输入文件路径 (默认: input.json)
  --output FILE         输出文件路径 (默认: answer.jsonl)
                        支持 .jsonl 和 .json 格式，根据文件扩展名自动检测
  --debug               开启调试模式
  --context-length INT  手动指定最大上下文长度
  --temperature FLOAT   手动指定模型温度
```