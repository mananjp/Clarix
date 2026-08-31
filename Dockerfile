# ---- Stage 1: Build frontend SPA ----
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python app ----
FROM python:3.12-slim AS runtime

# Non-root user
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# Install system deps for psycopg2-binary + PyMuPDF wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY app/ ./app/
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY scripts/ ./scripts/

# Copy built frontend assets into the static dir FastAPI serves
COPY --from=frontend-build /frontend/dist/ ./app/static/

# Create data dirs (uploads persisted via volume)
RUN mkdir -p /app/data/uploads && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
