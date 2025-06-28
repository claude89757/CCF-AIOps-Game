#!/bin/bash

# 设置脚本在遇到错误时退出
set -e

echo "===== CCF AIOps 竞赛 - 根因定位系统 ====="
echo "开始构建Docker镜像..."

# 构建Docker镜像
docker build -t ccf-aiops-game .

echo "Docker镜像构建完成！"
echo "开始运行推理流程..."

# 运行Docker容器
# 挂载当前目录到容器中，确保输出文件可以保存到宿主机
docker run --rm \
    -v "$(pwd)/output:/app/output" \
    -v "$(pwd)/data:/app/data" \
    --name ccf-aiops-container \
    ccf-aiops-game

echo "推理流程执行完成！"
echo "检查输出文件..."

# 检查answer.json是否生成
if [ -f "output/answer.json" ]; then
    echo "✓ answer.json 文件已生成"
    echo "文件大小: $(du -h output/answer.json | cut -f1)"
    echo "生成时间: $(stat -c %y output/answer.json)"
else
    echo "✗ 错误：未找到 answer.json 文件"
    exit 1
fi

echo "===== 运行完成 =====" 