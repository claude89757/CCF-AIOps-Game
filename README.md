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
# 直接调用智能体
python -c "
from src.agent import AIOpsReactAgent
agent = AIOpsReactAgent(model_name='deepseek-v3:671b', max_iterations=12)
result = agent.process_input_json('input.json', 'answer.json')
print(f'成功率: {result[\"success_rate\"]:.1f}%')
"
```

## 📁 项目结构

```
CCF-AIOps-Game/
├── README.md           # 项目说明文档（本文件）
├── domain.conf         # 外网域名配置文件
├── src/                # 核心代码目录
│   ├── agent.py        # AIOpsReactAgent核心类
│   ├── model.py        # 模型客户端
│   ├── prompt.py       # 比赛优化的系统提示词
│   └── tools.py        # 数据分析工具
├── data/              # 监控数据目录
│   ├── 2025-06-06/    # 按日期组织的数据
│   ├── 2025-06-07/
│   └── ...
├── input.json         # 比赛输入文件（846个案例）
├── answer.json        # 比赛输出文件（运行后生成）

├── Dockerfile         # Docker构建文件
├── run.sh            # 一键运行脚本
└── requirements.txt   # Python依赖
```
