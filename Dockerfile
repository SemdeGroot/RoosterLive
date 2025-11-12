# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

# Laat pip cache juist AAN (dus GEEN PIP_NO_CACHE_DIR=1)
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# OS deps (blijft cachen zolang deze regels niet wijzigen)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# 1) Eerst requirements kopiëren → maakt pip-laag cachebaar op requirements-hash
COPY requirements.txt .

# 2) pip install. Dankzij layer caching en GHA cache slaat deze stap over
#    zolang requirements.txt niet verandert. --mount cache versnelt downloads
#    bij een ‘cold start’ (maar layer cache is de echte winst).
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 3) Daarna pas de rest van je code (zodat code-wijzigingen pip-laag niet breken)
COPY . .

# optioneel — laat niet falen in CI
RUN python manage.py collectstatic --noinput || true

CMD ["sh","-c","gunicorn rooster_site.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WORKERS:-3} --timeout ${TIMEOUT:-60}"]