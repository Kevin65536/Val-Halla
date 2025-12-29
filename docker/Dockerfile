FROM python:3.11-slim

LABEL maintainer="Val-Halla Team"
LABEL description="QQ群成员自动备份与一键重建工具"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY src/ ./src/
COPY config/ ./config/

# 创建数据目录
RUN mkdir -p data/backups data/logs data/database

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 暴露端口 (如果启用 Web API)
EXPOSE 8000

# 运行程序
CMD ["python", "src/main.py"]
