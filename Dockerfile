# Multi-stage Dockerfile for VirtualSRE MCP Server
# Supports hybrid authentication: in-cluster + kubeconfig for multi-cluster access

# ============================================================================
# Stage 1: Builder - Install dependencies with uv
# ============================================================================
FROM python:3.13-slim as builder

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv pip install --system --no-cache -r pyproject.toml

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.13-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash mcpuser

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY mcp_server.py .
COPY config.py .

# Create .kube directory for optional kubeconfig mount
RUN mkdir -p /home/mcpuser/.kube && \
    chown -R mcpuser:mcpuser /home/mcpuser/.kube

# Change to non-root user
USER mcpuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/mcpuser

# Expose MCP server port
EXPOSE 5555

# Health check (basic connectivity test)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('127.0.0.1', 5555)); s.close()" || exit 1

# Run MCP server with HTTP transport
CMD ["python", "mcp_server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "5555"]


