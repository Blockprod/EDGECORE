<<<<<<< HEAD
﻿# Both stages use debian:bookworm-slim — zero additional CVE surface vs python:3.11-slim.
# Python 3.11 is installed from Debian's patched repos (same CVE baseline as bookworm-slim).
FROM debian:bookworm-slim AS builder
=======
# Use official Python runtime as base image (must match pyproject.toml)
FROM python:3.11.9-slim AS builder
>>>>>>> origin/main

# Set working directory
WORKDIR /app

<<<<<<< HEAD
# Apply OS patches + build tools + Python 3.11 from Debian repos
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies into a venv
COPY requirements.txt .

RUN python3.11 -m venv /opt/venv
=======
# Install build dependencies (including C++ compiler and CMake)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gcc \
    g++ \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .

RUN python -m venv /opt/venv
>>>>>>> origin/main
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

<<<<<<< HEAD
# Production stage — same base as builder: debian:bookworm-slim
FROM debian:bookworm-slim
=======
# Production stage (must match pyproject.toml)
FROM python:3.11.9-slim
>>>>>>> origin/main

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
<<<<<<< HEAD
    EDGECORE_ENV=prod

# Apply OS patches + Python 3.11 runtime + minimal system deps
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-minimal \
=======
    EDGECORE_ENV=production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
>>>>>>> origin/main
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment (all packages) from builder — no /usr/local copy needed
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Create logs directory
RUN mkdir -p logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose ports
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]