#!/bin/bash

# CCF AIOps挑战赛 - 构建和运行脚本
set -e  # 如果任何命令失败，则退出

echo "🏆 CCF AIOps挑战赛 - 故障诊断智能体"
echo "=========================================="

# 检查必需的环境变量
if [ -z "$OPENAI_API_TOKEN" ]; then
    echo "❌ 错误: 环境变量 OPENAI_API_TOKEN 未设置"
    echo "请设置: export OPENAI_API_TOKEN='your-api-key'"
    exit 1
fi

if [ -z "$BASE_URL" ]; then
    echo "❌ 错误: 环境变量 BASE_URL 未设置"
    echo "请设置: export BASE_URL='your-base-url'"
    exit 1
fi

echo "🔧 检查Docker镜像..."
if docker images | grep -q ccf-aiops-challenge; then
    echo "✅ Docker镜像已存在，跳过构建"
else
    echo "🔧 构建Docker镜像..."
    docker build -t ccf-aiops-challenge .
    echo "✅ Docker镜像构建完成"
fi

echo "🚀 运行故障诊断智能体..."

# 运行Docker容器，传递环境变量并生成answer.json
docker run --rm \
    -e OPENAI_API_TOKEN="${OPENAI_API_TOKEN}" \
    -e BASE_URL="${BASE_URL}" \
    -v "$(pwd):/workspace" \
    -w /workspace \
    ccf-aiops-challenge python -c "
import sys
sys.path.append('/app')
from src.agent import AIOpsReactAgent
import json
import os

# 创建智能体实例
agent = AIOpsReactAgent(model_name='deepseek-v3:671b', max_iterations=12)

# 处理输入文件
print('📄 开始处理 input.json...')
result = agent.process_input_json('input.json', 'answer.json')

if result['status'] == 'completed':
    print(f'✅ 成功处理 {result[\"successful_cases\"]} 个案例')
    print(f'❌ 失败 {result[\"failed_cases\"]} 个案例') 
    print(f'📈 成功率: {result[\"success_rate\"]:.1f}%')
else:
    print(f'❌ 处理失败: {result.get(\"error\", \"未知错误\")}')
    sys.exit(1)
"

echo "✅ 故障诊断完成"

# 检查输出文件
if [ -f "answer.json" ]; then
    echo "📁 生成的答案文件: answer.json"
    echo "📊 文件大小: $(du -h answer.json | cut -f1)"
    
    # 验证JSON格式
    if python3 -c "import json; json.load(open('answer.json'))" 2>/dev/null; then
        echo "✅ JSON格式验证通过"
        echo "📈 结果数量: $(python3 -c "import json; print(len(json.load(open('answer.json'))))")"
    else
        echo "❌ JSON格式验证失败"
        exit 1
    fi
else
    echo "❌ 错误: 未生成answer.json文件"
    exit 1
fi

echo "🎉 任务完成! 提交文件: answer.json" 