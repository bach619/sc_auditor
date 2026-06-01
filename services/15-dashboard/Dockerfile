FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY services/15-dashboard/frontend/package*.json ./
RUN npm ci
COPY services/15-dashboard/frontend/ .
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/15-dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/15-dashboard/ .
COPY services/shared/ ./shared/
RUN rm -rf frontend templates

COPY --from=frontend-build /static ./static

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
