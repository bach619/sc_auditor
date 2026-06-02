FROM python:3.11-slim

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
COPY services/04b-scanner-echidna/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip 'setuptools<60' wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install solc-select
RUN pip install --no-cache-dir solc-select

# Install Echidna fuzzer
RUN ECHIDNA_VER=$(curl -fsSL https://api.github.com/repos/crytic/echidna/releases/latest | \
    python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'].lstrip('v'))" 2>/dev/null || echo "2.3.2") && \
    ARCH=$(uname -m) && \
    case "$ARCH" in \
        x86_64)  ECHIDNA_ARCH="x86_64-linux" ;; \
        aarch64|arm64) ECHIDNA_ARCH="aarch64-linux" ;; \
        *)       echo "Unsupported architecture: $ARCH"; exit 1 ;; \
    esac && \
    echo "Downloading Echidna ${ECHIDNA_VER} for ${ECHIDNA_ARCH}" && \
    curl -fsSL "https://github.com/crytic/echidna/releases/download/v${ECHIDNA_VER}/echidna-${ECHIDNA_VER}-${ECHIDNA_ARCH}.tar.gz" -o /tmp/echidna.tar.gz && \
    tar -xzf /tmp/echidna.tar.gz -C /tmp/ && \
    install -m 755 /tmp/echidna /usr/local/bin/echidna && \
    echo "Echidna installed ($ARCH): $(echidna --version 2>/dev/null || echo 'failed')"

# Copy shared library
COPY services/shared/ ./shared/

# Copy service code
COPY services/04b-scanner-echidna/ .

# Create data dir
RUN mkdir -p /data/scanner-echidna && chmod 777 /data/scanner-echidna

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8015/health || exit 1

EXPOSE 8015
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8015", "--log-level", "info"]
