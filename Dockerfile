# Use official Kali Linux image
FROM kalilinux/kali-rolling:latest

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    SHELL=/bin/bash \
    GOPATH=/root/go \
    PATH="/opt/venv/bin:/root/go/bin:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"

# Set working directory
WORKDIR /app

# Install all system packages in one layer
RUN apt-get update && \
    apt-get install -y \
    # Python tools
    python3 \
    python3-pip \
    python3-venv \
    # Go compiler
    golang-go \
    # Essential utilities
    bash \
    curl \
    wget \
    git \
    vim \
    nano \
    procps \
    # Network tools
    net-tools \
    iputils-ping \
    dnsutils \
    whois \
    netcat-traditional \
    # Security/pentest tools
    nmap \
    ffuf \
    dirb \
    tcpdump \
    exiftool \
    whatweb \
    swaks \
    seclists \
    # JSON processor
    jq \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Go-based tools
RUN go install -v github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy application code and configuration
COPY src/ /app/
COPY config.toml /app/config.toml

# Run the server
CMD ["python", "/app/kali_server.py"]