FROM python:3.12-slim

# Install Node.js for Tailwind CSS build
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files and install Node dependencies (including devDependencies for build)
COPY package*.json ./
RUN npm ci

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Build Tailwind CSS
RUN npm run build:css

# Remove devDependencies to reduce image size
RUN npm prune --production

# Compile translations for production
RUN pybabel compile -d translations

RUN mkdir -p /app && touch /app/dev.db && chown nobody:nogroup /app/dev.db || true
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
