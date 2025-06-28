# CCF AIOps挑战赛 - React模式故障诊断智能体

这是一个专门为**2025年CCF国际AIOps挑战赛**设计的智能体，基于React模式（Reasoning + Acting）进行微服务系统的故障诊断。

## 🏆 比赛适配特性

- ✅ **完全符合比赛要求**: 支持input.json到answer.json的完整工作流
- ✅ **评分标准优化**: 针对LA、TA、效率和可解释性四个维度优化
- ✅ **输出稳定性**: temperature=0确保结果可复现
- ✅ **容器化部署**: Docker支持，符合比赛提交要求
- ✅ **批量处理**: 自动处理846个故障案例

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

## 🔧 复现过程说明

### 环境依赖
- Python 3.9+
- Docker（用于容器化运行）
- 网络访问（需要调用大模型API）

### 运行流程
1. **环境变量设置**: 必须设置`OPENAI_API_TOKEN`和`BASE_URL`
2. **Docker构建**: `docker build -t ccf-aiops-challenge .`
3. **容器运行**: 在容器内直接调用`src/agent.py`模块
4. **结果输出**: 生成`answer.json`文件

### 可能遇到的问题及解决方案

#### 1. 环境变量未设置
**问题**: `❌ 错误: 环境变量 OPENAI_API_TOKEN 未设置`
**解决方案**: 
```bash
export OPENAI_API_TOKEN="your-actual-api-key"
export BASE_URL="https://uni-api.cstcloud.cn/v1"
```

#### 2. 网络连接问题
**问题**: API调用失败或超时
**解决方案**: 
- 确保网络能访问`uni-api.cstcloud.cn`
- 检查API key是否有效
- 查看domain.conf确认所需外网域名

#### 3. 内存不足
**问题**: Docker运行时内存不足
**解决方案**: 
- 为Docker分配至少4GB内存
- 使用`docker run --memory=4g`限制内存使用

#### 4. 数据加载失败
**问题**: parquet文件读取错误
**解决方案**: 
- 确保data目录完整
- 检查parquet文件是否损坏
- 使用tools.py中的预览功能检查数据

#### 5. JSON格式错误
**问题**: answer.json格式不正确
**解决方案**: 
```bash
# 手动验证JSON格式
python -c "import json; data=json.load(open('answer.json')); print(f'格式正确，包含{len(data)}个结果')"
```

#### 6. Docker构建失败
**问题**: 依赖安装失败
**解决方案**: 
- 检查requirements.txt
- 使用国内镜像源：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple`
- 确保网络能访问PyPI

## 📊 输出格式说明

生成的`answer.json`严格按照比赛要求格式：
```json
[
  {
    "uuid": "345fbe93-80",
    "component": "checkoutservice",
    "reason": "disk IO overload",
    "time": "2025-06-05 16:18:00",
    "reasoning_trace": [
      {
        "step": 1,
        "action": "LoadMetrics(checkoutservice)",
        "observation": "disk_read_latency spike to 500ms at 16:18"
      }
    ]
  }
]
```

## 🎯 比赛评分适配

- **组件准确率 (LA)**: 输出具体微服务组件名称
- **原因准确率 (TA)**: 输出具体故障原因，避免generic描述
- **推理效率**: 目标5-8步推理路径
- **推理可解释性**: 覆盖metrics、logs、traces三类证据

## 🔍 验证与测试

```bash
# 使用run.sh进行完整测试
./run.sh

# 或者直接调用Python模块
python -c "
from src.agent import AIOpsReactAgent
agent = AIOpsReactAgent(model_name='deepseek-v3:671b', max_iterations=1)
demo_case = {'uuid': 'test-001', 'Anomaly Description': 'Test case'}
result = agent.diagnose_single_case(demo_case, debug=True)
print('测试完成:', result['status'])
"
```

## 📞 技术支持

如果在复现过程中遇到问题，请检查：
1. 环境变量是否正确设置
2. 网络连接是否正常
3. Docker是否有足够资源
4. 数据文件是否完整

所有推理过程由大语言模型驱动完成，符合比赛要求。
