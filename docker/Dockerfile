# ECS Fargate processor image for Scenario 2
# Multi-stage build for smaller image size

FROM python:3.12-slim AS builder

# Install poetry
RUN pip install --no-cache-dir poetry poetry-plugin-export

# Copy poetry files
WORKDIR /app
COPY pyproject.toml poetry.lock* ./

# Export dependencies to requirements.txt (main + docker groups)
RUN poetry export --without-hashes -f requirements.txt --with docker -o requirements.txt

# Production stage
FROM python:3.12-slim AS runtime

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
# TODO
COPY service/ ./service/

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables (defaults, overridden by ECS task definition)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

# Run the container processor
CMD ["python", "-m", "service.container.processor"]
