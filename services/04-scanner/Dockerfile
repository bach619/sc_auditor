FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY services/04-scanner/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip 'setuptools<60' wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install Foundry (forge, cast, anvil, chisel) for Solidity compilation & fuzzing
RUN curl -fsSL https://foundry.paradigm.xyz -o /tmp/foundryup.sh && \
    sh /tmp/foundryup.sh 2>/dev/null; \
    if [ -f /root/.foundry/bin/foundryup ]; then \
        /root/.foundry/bin/foundryup 2>/dev/null; \
    fi && \
    ln -sf /root/.foundry/bin/forge /usr/local/bin/forge && \
    ln -sf /root/.foundry/bin/cast /usr/local/bin/cast && \
    ln -sf /root/.foundry/bin/anvil /usr/local/bin/anvil && \
    ln -sf /root/.foundry/bin/chisel /usr/local/bin/chisel && \
    echo "Foundry installed: $(forge --version 2>/dev/null || echo 'failed')"

# Install Echidna fuzzer from GitHub releases (persistent, no runtime download)
RUN ECHIDNA_VER=$(curl -fsSL https://api.github.com/repos/crytic/echidna/releases/latest | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'].lstrip('v'))" 2>/dev/null || echo "2.3.2") && \
    curl -fsSL "https://github.com/crytic/echidna/releases/download/v${ECHIDNA_VER}/echidna-${ECHIDNA_VER}-x86_64-linux.tar.gz" -o /tmp/echidna.tar.gz && \
    tar -xzf /tmp/echidna.tar.gz -C /tmp/ && \
    install -m 755 /tmp/echidna /usr/local/bin/echidna && \
    echo "Echidna installed: $(echidna --version 2>/dev/null || echo 'failed')"

COPY services/04-scanner/ .
COPY services/shared/ ./shared/

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
