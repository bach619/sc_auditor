FROM python:3.12-slim

LABEL service="scanner-manticore"
LABEL version="0.1.0"
LABEL description="Manticore symbolic execution — HIGH/CRIT severity bug confirmation"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Manticore (EVM + WASM symbolic execution engine)
RUN pip install --no-cache-dir manticore>=0.4.0

# Create service directory
WORKDIR /app

# Install app deps
COPY services/04e-scanner-manticore/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library
COPY services/shared/ ./shared/

# Copy service code
COPY services/04e-scanner-manticore/ .

EXPOSE 8018

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8018/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8018", "--log-level", "info"]
