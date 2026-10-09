# Imagem base pelo espelho público da AWS (mesma imagem oficial do Docker
# Hub): o builder do Railway levou 429 do Docker Hub em 2026-10-09.
FROM public.ecr.aws/docker/library/python:3.13-slim

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

# Host vazio: escuta em IPv4 e IPv6 (a rede privada do Railway pode
# usar IPv6). "::" sozinho no uvicorn escuta só IPv6 — testado.
# O Railway define PORT; 8000 é o padrão local
CMD ["sh", "-c", "uvicorn app:app --host \"\" --port ${PORT:-8000}"]
