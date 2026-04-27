# RedFlag Agents PH - Production Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy pyproject first for caching
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -r uv.lock

# Copy application code
COPY . .

# Create .env from variables (runtime)
RUN echo '# Runtime env vars' > .env

# Expose ports
EXPOSE 8000

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run migrations and start API server
CMD ["python", "api/main.py"]