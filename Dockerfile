# Dockerfile

# 1. 使用官方Python镜像作为基础
FROM python:3.10-slim

# 2. 设置工作目录
WORKDIR /app

# 3. 安装Poetry (可选，但推荐用于依赖管理) 或直接用requirements.txt
# RUN pip install poetry
# COPY poetry.lock pyproject.toml /app/
# RUN poetry config virtualenvs.create false && poetry install --no-root --no-dev

# 或者，使用 requirements.txt (更简单)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制应用代码到工作目录
COPY ./app /app/app

# 5. 暴露端口 (Gunicorn/Uvicorn将监听这个端口)
EXPOSE 8000

# 6. 运行应用的命令
# 使用Gunicorn作为进程管理器，Uvicorn作为ASGI worker
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "app.main:app"]
# -k: 指定worker类型
# -w: worker数量, 通常是 (2 * CPU核心数) + 1
# -b: 绑定地址和端口, 0.0.0.0 允许从容器外部访问
