FROM python:3.11-slim
ENV PIP_DEFAULT_TIMEOUT=200

LABEL service="scanner-manticore"
LABEL version="0.1.0"
LABEL description="Manticore symbolic execution — HIGH/CRIT severity bug confirmation"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# pysha3 (manticore dep) is unmaintained and won't build on modern Python.
# Install safe-pysha3 (pre-built wheel) + dummy pysha3 to satisfy manticore.
RUN pip install --no-cache-dir safe-pysha3==1.0.5 && \
    mkdir -p /tmp/pysha3-fake && cd /tmp/pysha3-fake && \
    printf 'from setuptools import setup\nsetup(name="pysha3", version="1.0.2", py_modules=[], install_requires=["safe-pysha3>=1.0.0"])\n' > setup.py && \
    pip install --no-cache-dir --no-build-isolation . && \
    cd / && rm -rf /tmp/pysha3-fake

# Install Manticore (EVM + WASM symbolic execution engine)
RUN pip install --no-cache-dir manticore==0.3.7

# Create service directory
WORKDIR /app

# Install app deps
COPY services/04e-scanner-manticore/requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy shared library
COPY services/shared/ ./shared/

# Copy service code
COPY services/04e-scanner-manticore/ .

ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

EXPOSE 8018

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8018/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8018", "--log-level", "info"]
