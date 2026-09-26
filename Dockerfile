FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY bot.py .

RUN mkdir -p \
    /app/data \
    /app/downloads \
    /app/logs \
    /app/backups \
    /app/updates \
    /app/data/tg-api

CMD ["python", "bot.py"]
