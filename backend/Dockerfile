FROM python:3.11-slim

# 不跑 apt-get：受构建网络限制，健康检查改用 Python 标准库（容器内本来就有 python）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 60 -r /app/requirements.txt

COPY . /app
COPY scripts/worker_healthcheck.sh /app/worker_healthcheck.sh
RUN chmod +x /app/worker_healthcheck.sh

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
