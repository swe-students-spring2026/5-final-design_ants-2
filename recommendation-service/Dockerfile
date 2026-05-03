FROM python:3.11-slim AS base

WORKDIR /app

# Install dependencies in a separate layer so source changes don't bust the cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source.
COPY app ./app
COPY wsgi.py .
COPY scripts ./scripts

ENV PORT=8000
EXPOSE ${PORT}

# Healthcheck talks to our /healthz endpoint. ${PORT} is expanded by /bin/sh
# at runtime, so changing PORT (via compose env) is picked up without rebuild.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys;\
sys.exit(0) if urllib.request.urlopen('http://localhost:${PORT}/healthz', timeout=3).status==200 else sys.exit(1)" || exit 1

# `sh -c "exec ..."` so ${PORT} expands at runtime AND gunicorn becomes PID 1
# (so SIGTERM still reaches it for graceful shutdown).
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --access-logfile - wsgi:application"]
