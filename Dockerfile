# Chess Coach AI - Multi-stage Dockerfile
# This builds both frontend and backend into a single container

# ============================================
# Stage 1: Build Frontend
# ============================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for better caching
COPY frontend/package.json frontend/package-lock.json* frontend/yarn.lock* ./

# Install dependencies (yarn handles peer deps gracefully unlike npm ci)
RUN yarn install

# Copy frontend source
COPY frontend/ ./

# Build the React app
RUN yarn build

# ============================================
# Stage 2: Production Runtime
# ============================================
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    supervisor \
    stockfish \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python requirements and install
COPY backend/requirements.txt backend/requirements-human-policy.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir -r backend/requirements-human-policy.txt

# Copy backend source code
COPY backend/ ./backend/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Bake the commit that produced this image into /api/health, so
# verify_deployment.py's commit-match check can confirm a deploy
# actually reached prod (2026-08-07). .dockerignore excludes .git, so
# this has to be passed in at build time -- `git rev-parse HEAD`
# doesn't work inside the container itself.
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=$GIT_COMMIT

# Copy configuration files
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create necessary directories
RUN mkdir -p /var/log/supervisor /var/log/nginx

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/api/health || exit 1

# Start supervisor (manages nginx + uvicorn)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
