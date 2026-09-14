FROM python:3.11-slim

# 官方 SDK 依赖:libcurl, libssl 等(以官方 README 为准,可能还需 libgcc_s)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcurl4 \
        libssl3 \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码
COPY *.py rules.yaml ./

# SDK 库 + 密钥挂载卷,不打进镜像(通过 docker-compose 挂载)
VOLUME ["/app/lib", "/app/keys", "/app/data"]

CMD ["python", "scheduler.py"]
