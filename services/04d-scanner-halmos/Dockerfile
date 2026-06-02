FROM python:3.12-slim

LABEL service="scanner-halmos"
LABEL version="0.1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Foundry
RUN curl -fsSL https://foundry.paradigm.xyz | bash
ENV PATH="/root/.foundry/bin:${PATH}"
RUN foundryup

# Install Halmos
RUN pip install --no-cache-dir halmos

# Create service directory
WORKDIR /app

# Install app deps
COPY services/04d-scanner-halmos/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library
COPY services/shared/ ./shared/

# Copy service code
COPY services/04d-scanner-halmos/ .

EXPOSE 8017

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8017/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8017"]
