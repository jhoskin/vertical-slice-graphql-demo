# Dockerfile for the FastAPI application
FROM python:3.12-slim

WORKDIR /app

# Install uv for dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy application code
COPY app/ ./app/

# Expose ports
# 8000 for main GraphQL API
# 9080 for Restate service endpoint
EXPOSE 8000 9080

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
