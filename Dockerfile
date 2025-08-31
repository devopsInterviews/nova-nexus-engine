# Multi-stage Dockerfile for MCP Client
# Combines both frontend and backend into a single image

# Stage 1: Build React Frontend
FROM node:18-alpine AS frontend-build
WORKDIR /app

# Copy frontend package files
COPY ui/package*.json ./
RUN npm ci

# Copy frontend source and build
COPY ui/ ./
RUN npm run build

# Stage 2: Setup Python Backend with built frontend
FROM python:3.11-slim AS production

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY app/ ./app/
COPY *.py ./
COPY logging_config.json ./

# Copy built frontend from previous stage
COPY --from=frontend-build /app/dist ./static/

# Create directories and set permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start the application
CMD ["python", "-m", "uvicorn", "client:app", "--host", "0.0.0.0", "--port", "8000"]
