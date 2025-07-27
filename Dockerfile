# TestAgent Dockerfile - 多阶段多架构构建
# 支持 linux/amd64, linux/arm64, linux/arm/v7

# 构建阶段
FROM --platform=$BUILDPLATFORM python:3.11-slim as builder

# 构建参数
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETOS
ARG TARGETARCH

# 设置工作目录
WORKDIR /app

# 根据目标架构安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    pkg-config \
    && if [ "$TARGETARCH" = "arm64" ] || [ "$TARGETARCH" = "arm" ]; then \
        apt-get install -y gcc-aarch64-linux-gnu || apt-get install -y gcc-arm-linux-gnueabihf; \
    fi \
    && rm -rf /var/lib/apt/lists/*

# 设置交叉编译环境变量
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        export CC=aarch64-linux-gnu-gcc; \
    elif [ "$TARGETARCH" = "arm" ]; then \
        export CC=arm-linux-gnueabihf-gcc; \
    fi

# 复制依赖文件
COPY requirements.txt .
COPY requirements-dev.txt .

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 升级pip并安装依赖
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 生产阶段
FROM --platform=$TARGETPLATFORM python:3.11-slim as production

# 构建参数
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/opt/venv/bin:$PATH"

# 创建非root用户
RUN groupadd -r testagent && useradd -r -g testagent testagent

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 添加平台信息标签
LABEL platform=$TARGETPLATFORM
LABEL architecture=$TARGETARCH
LABEL os=$TARGETOS

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置工作目录
WORKDIR /app

# 复制应用代码
COPY --chown=testagent:testagent . .

# 创建必要的目录
RUN mkdir -p /app/data/vectordb \
    /app/data/documents \
    /app/data/cache \
    /app/logs \
    /app/config \
    /app/backups \
    && chown -R testagent:testagent /app

# 切换到非root用户
USER testagent

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "uvicorn", "src.server.main:app", "--host", "0.0.0.0", "--port", "8000"]