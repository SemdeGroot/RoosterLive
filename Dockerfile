# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# 1) requirements eerst, voor layer caching
COPY requirements.txt .

# 2) pip install met BuildKit cache mount (snel in CI, geen image-bloat)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 3) daarna de rest van de code
COPY . .

# optional — niet laten falen in CI
RUN python manage.py collectstatic --noinput || true

# Healthcheck endpoint (/health/) in je Django
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
  CMD curl -f http://localhost:${PORT:-8000}/health/ || exit 1

CMD ["sh","-c","gunicorn rooster_site.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WORKERS:-3} --timeout ${TIMEOUT:-60}"]
