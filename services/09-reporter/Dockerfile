FROM python:3.11-slim
ENV PIP_DEFAULT_TIMEOUT=200

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/09-reporter/requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY services/09-reporter/ .
COPY services/shared/ ./shared/

# Create data directories as root with world-writable permissions
# (will be mounted as volumes, so this is just a fallback)
RUN mkdir -p /data/reporter/reports && chmod 777 /data && chmod 777 /data/reporter && chmod 777 /data/reporter/reports

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:8007/health || exit 1

EXPOSE 8007
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8007", "--log-level", "info"]
