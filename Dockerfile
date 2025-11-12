FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# verzamel statics (werkt ook als je later S3 gebruikt)..
RUN python manage.py collectstatic --noinput || true

CMD ["sh","-c","gunicorn rooster_site.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WORKERS:-3} --timeout ${TIMEOUT:-60}"]
