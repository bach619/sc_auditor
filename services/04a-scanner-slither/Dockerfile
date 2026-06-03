FROM python:3.11-slim
ENV PIP_DEFAULT_TIMEOUT=200

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first
COPY vyper_lib/ /app/vyper_lib/

# Install app deps
COPY services/04a-scanner-slither/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip 'setuptools<60' wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install solc-select + slither
RUN pip install --no-cache-dir solc-select && \
    pip install --no-cache-dir slither-analyzer

# Copy shared library
COPY services/shared/ ./shared/

# Copy service code
COPY services/04a-scanner-slither/ .

# Create data dir
RUN mkdir -p /data/scanner-slither && chmod 777 /data/scanner-slither

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8014/health || exit 1

EXPOSE 8014
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8014", "--log-level", "info"]
