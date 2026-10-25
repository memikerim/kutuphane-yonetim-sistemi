FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hem yerel (8000) hem de Hugging Face Spaces (7860) portlarını bildir
EXPOSE 7860 8000

# Veritabanı şemasını güncelle (Alembic), başlangıç verilerini yükle (Seed) ve FastAPI'yi başlat
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed_cloud && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
