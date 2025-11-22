FROM python:3.13-slim

# Add labels for better metadata management
LABEL maintainer="FastAPI Alpine Starter" \
      version="1.0" \
      description="FastAPI + Alpine.js application with PostgreSQL and i18n"

# Install Node.js and curl for Tailwind CSS build and health checks
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1001 -U app

WORKDIR /app

# Change ownership of app directory to allow the app user to write
RUN chown -R app:app /app

# Switch to app user
USER app

# Copy package files and install Node dependencies (including devDependencies for build)
COPY --chown=app:app package*.json ./
RUN npm ci

# Copy Python requirements and install
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy source code
COPY --chown=app:app . .

# Build Tailwind CSS
RUN npm run build:css

# Remove devDependencies to reduce image size
RUN npm prune --production

# Compile translations for production
RUN pybabel compile -d translations

# Health check using FastAPI's built-in /docs endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/docs || exit 1

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
