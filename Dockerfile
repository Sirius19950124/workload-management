# 微信云托管 Dockerfile
# 基于 Python 3.9 精简镜像

FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /tmp/uploads instance

# 设置环境变量
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# 暴露端口（云托管默认使用 80）
EXPOSE 80

# 启动命令
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:80", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
