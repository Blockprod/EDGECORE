# Use official Python runtime as base image
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies (including C++ compiler and CMake)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gcc \
    g++ \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and source
COPY requirements.txt .
COPY CMakeLists.txt .
COPY cpp/ cpp/

# Create virtual environment and install Python dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Try to compile C++ extensions (optional - won't fail if not successful)
RUN mkdir -p build && \
    cd build && \
    cmake .. || echo "CMake configuration failed, continuing with Python-only build" && \
    make -j$(nproc) || echo "C++ compilation failed, continuing with Python fallback" && \
    cd .. || true

# Production stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Copy compiled C++ extensions if they exist (from builder)
COPY --from=builder /app/edgecore/ edgecore/

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
