FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code & .env & data
COPY app.py ./
COPY .env ./.env
COPY data ./data

EXPOSE 5000

CMD ["python", "app.py"]
