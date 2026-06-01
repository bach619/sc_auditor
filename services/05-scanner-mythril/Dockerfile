FROM python:3.11-slim

WORKDIR /app

# Install system deps: curl for healthcheck, build-essential for pyethash C extension
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY services/05-scanner-mythril/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 -r requirements.txt

COPY services/05-scanner-mythril/ .
COPY services/shared/ ./shared/

RUN mkdir -p /data/scanner-mythril && chmod 777 /data/scanner-mythril

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8013/health || exit 1

EXPOSE 8013
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8013", "--log-level", "info"]
