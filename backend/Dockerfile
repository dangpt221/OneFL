# ==============================================================================
# OneFL Backend Production Dockerfile (Powered by uv for ultra-fast builds)
# ==============================================================================

# --- Stage 1: Build Dependencies via uv ---
FROM python:3.11-slim AS builder

WORKDIR /build

# Copy pre-built uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml & requirements
COPY pyproject.toml ./

# Create virtual environment and install all dependencies with uv
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --no-cache -r pyproject.toml

# --- Stage 2: Minimal Runtime Image ---
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime media tools: FFmpeg, libass, international fonts for ASS rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libass-dev \
    fonts-noto-cjk \
    fonts-dejavu-core \
    fontconfig \
    curl \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/outputs /app/tmp/scratch

# Copy backend application code
COPY app /app/app

EXPOSE 8000

# Healthcheck probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
