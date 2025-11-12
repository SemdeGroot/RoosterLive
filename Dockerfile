# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# OS deps (laag blijft cachen zolang regels niet veranderen)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# 1) requirements eerst kopiëren → pip laag cached zolang requirements.txt niet wijzigt
COPY requirements.txt .

# 2) pip install met BuildKit cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 3) daarna pas de rest van de code
COPY . .

# statics verzamelen; laat niet falen als in dev
RUN python manage.py collectstatic --noinput || true

# gunicorn (PORT/WORKERS/TIMEOUT komen uit .env)
CMD ["sh","-c","gunicorn rooster_site.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WORKERS:-3} --timeout ${TIMEOUT:-60}"]
