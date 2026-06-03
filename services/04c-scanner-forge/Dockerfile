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
COPY services/04c-scanner-forge/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip 'setuptools<60' wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install solc-select
RUN pip install --no-cache-dir solc-select

# Install Foundry (forge)
RUN curl -fsSL https://foundry.paradigm.xyz -o /tmp/foundryup.sh && \
    sh /tmp/foundryup.sh 2>/dev/null; \
    if [ -f /root/.foundry/bin/foundryup ]; then \
        /root/.foundry/bin/foundryup 2>/dev/null; \
    fi && \
    ln -sf /root/.foundry/bin/forge /usr/local/bin/forge && \
    ln -sf /root/.foundry/bin/cast /usr/local/bin/cast && \
    ln -sf /root/.foundry/bin/anvil /usr/local/bin/anvil && \
    echo "Foundry installed: $(forge --version 2>/dev/null || echo 'failed')"

# Copy shared library
COPY services/shared/ ./shared/

# Copy service code
COPY services/04c-scanner-forge/ .

# Create data dir
RUN mkdir -p /data/scanner-forge && chmod 777 /data/scanner-forge

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8016/health || exit 1

EXPOSE 8016
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8016", "--log-level", "info"]
