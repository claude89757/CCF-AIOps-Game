# 使用官方Python运行时作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY . /app/

# 创建requirements.txt文件
RUN echo "pandas>=1.5.0" > requirements.txt && \
    echo "pyarrow>=10.0.0" >> requirements.txt && \
    echo "numpy>=1.21.0" >> requirements.txt && \
    echo "scikit-learn>=1.1.0" >> requirements.txt && \
    echo "openai>=1.0.0" >> requirements.txt && \
    echo "requests>=2.28.0" >> requirements.txt && \
    echo "python-dotenv>=0.19.0" >> requirements.txt && \
    echo "tqdm>=4.64.0" >> requirements.txt

# 配置pip使用清华镜像源加速安装
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建输出目录
RUN mkdir -p /app/output

# 设置默认命令
CMD ["python", "src/main.py"] 