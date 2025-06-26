# Dockerfile (修正版 v2)

FROM python:3.10-slim

WORKDIR /app

# 【核心修正】在安装Python包之前，先安装系统级的编译工具
# apt-get update 更新包列表
# apt-get install -y --no-install-recommends gcc build-essential 安装编译工具链
# apt-get clean && rm -rf /var/lib/apt/lists/* 清理缓存，保持镜像体积小
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 使用国内镜像源安装Python依赖
RUN pip install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY ./app /app/app

EXPOSE 8000

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "app.main:app"]
