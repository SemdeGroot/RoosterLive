# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Alleen wat nodig is voor nu + straks Postgres (psycopg2)
# (PyMuPDF heeft geen extra system deps nodig)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Dependencies eerst (laaggrootte/caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# (optioneel) niet-root gebruiker
RUN useradd -ms /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Static verzamelen (werkt met lokale static setup; later bij S3 kun je dit uit CI doen)
RUN python manage.py collectstatic --noinput || true

# Gunicorn default flags: 3 workers, nette timeout en logging naar stdout/stderr
ENV GUNICORN_CMD_ARGS="--bind 0.0.0.0:8000 --workers 3 --timeout 60 --access-logfile - --error-logfile -"

# Start
# Pas 'rooster_site.wsgi:application' aan als je projectmodule anders heet
CMD ["gunicorn", "rooster_site.wsgi:application"]