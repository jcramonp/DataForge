# DataForge Control Plane API image.
# The same image runs locally (docker compose --profile api) and on AWS compute;
# behavior differs only through environment variables (see docs/operations/configuration.md).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATAFORGE_LOG_FORMAT=json

WORKDIR /app

RUN useradd --create-home --uid 10001 dataforge

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src
COPY config ./config
COPY database ./database

USER dataforge

EXPOSE 8000

# Liveness only. Orchestrators/load balancers should gate traffic on /api/ready.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
