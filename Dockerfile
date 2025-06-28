# 使用官方Python运行时作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制需求文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码和数据
COPY src/ ./src/
COPY data/ ./data/
COPY input.json .

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 确保工作目录权限
RUN chmod -R 755 /app

# 默认命令（由run.sh调用时会被覆盖）
CMD ["python", "-c", "print('请通过 run.sh 运行此容器')"] 