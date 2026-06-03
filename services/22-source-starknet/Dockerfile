FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*
COPY services/22-source-starknet/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/22-source-starknet/ .
COPY services/shared/ shared/
COPY vyper_lib/ vyper_lib/
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
