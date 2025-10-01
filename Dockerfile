# Gebruik een stabiele base image (met security updates)
FROM python:3.11-slim-bookworm

# Om security errors te vermijden + voor PyMuPDF heb je deze system packages nodig
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libx11-6 libxcb1 libxext6 libxrender1 libfreetype6 \
    libfontconfig1 fonts-dejavu-core ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# Zorg dat Python voorspelbaar draait
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

# Dependencies installeren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy je app code + data folder
COPY app.py .
COPY data ./data

# Cache dir in container (schrijfbaar pad)
RUN mkdir -p /tmp/cache
ENV CACHE_DIR=/tmp/cache

EXPOSE 5000

# Start je Flask app
CMD ["python", "app.py"]
