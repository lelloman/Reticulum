FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Docker CLI for test-runner
# iproute2 provides tc/netem for network chaos testing
# procps provides pgrep/pkill for daemon control
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    iproute2 \
    procps \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy and install RNS
COPY . /app/
RUN pip install --no-cache-dir -e .

# Install pytest for test-runner
RUN pip install --no-cache-dir pytest

# Create directories
RUN mkdir -p /root/.reticulum /app/scripts

# Copy control scripts
COPY tests/e2e/scripts/ /app/scripts/

# Default: run rnsd daemon
CMD ["rnsd", "-v"]
