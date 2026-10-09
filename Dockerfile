FROM python:3.13-slim

# FFmpeg: junta vídeo + áudio e converte para MP3
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Não roda como root
RUN useradd --create-home appuser \
    && mkdir -p downloads data \
    && chown -R appuser:appuser /app
USER appuser

# O Railway define PORT; 8000 é o padrão local
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
