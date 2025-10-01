# Dockerfile
FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=5000

# OS security updates + certs voor HTTPS
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies eerst (laag-caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip check

# App code en assets
COPY app.py ./
COPY data ./data

# (Optioneel) non-root draaien
RUN useradd -m appuser
USER appuser

# Vercel injecteert $PORT; Flask luistert daarop
EXPOSE 5000
CMD ["python", "app.py"]

