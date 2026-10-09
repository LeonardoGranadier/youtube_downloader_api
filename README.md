# Mil1Utilidades Media API

API em Python (FastAPI + yt-dlp + FFmpeg) para baixar vídeos/áudios a partir de um link, usada pelo Mil1 Utilidades.

## Sites aceitos

Qualquer site que o yt-dlp consiga baixar, e links diretos de arquivo (`.mp4`, `.webm`...), via http/https. Nada é contornado: sem cookies, contas ou proxies; se o site bloquear (ex.: YouTube bloqueia IPs de datacenter, testado no Railway em 2026-10-09), o download falha. Respeitar os termos de cada plataforma e a licença de cada obra é responsabilidade de quem baixa (decisão registrada no ADR-071 do Mil1).

**Proteção contra SSRF** (`services/net_guard.py`): toda resolução de nome do processo só devolve endereços públicos. Isso cobre redirecionamentos, fragmentos HLS/DASH e DNS rebinding, não só a URL inicial. Só protocolos baixados em Python (sem RTMP/RTSP via FFmpeg).

## Endpoints (todos exigem o cabeçalho `X-API-Key`)

- `POST /api/v1/media/info` `{ "url" }`: título, duração, miniatura, resoluções (`available_heights`) e `has_video` (link direto sem resolução conhecida vem com `[]` e `true`, e baixa o original)
- `POST /api/v1/media/download` `{ "url", "media_type": "video"|"audio", "quality": "best" | altura exata, ex.: "360" }`: `202` com `{ "id" }`. A altura precisa estar em `available_heights` do `/media/info` (até 1080p). O vídeo sempre sai com som: se a versão escolhida for muda (conferido com `ffprobe` no arquivo real), o áudio de outra versão é juntado com FFmpeg, sem recodificar o vídeo.
- `GET /api/v1/downloads/{id}/progress`: status e progresso
- `GET /api/v1/downloads/{id}/file`: arquivo final (quando `completed`)

Limites configuráveis por variável de ambiente (ver `.env.example`): duração máxima, tamanho máximo, teto de 1080p, e arquivos apagados automaticamente após `FILE_TTL_MINUTES`.

## Docker / Railway

```bash
docker build -t media-api .
docker run -e MEDIA_API_KEY=troque -p 8000:8000 media-api
```

No Railway, o `railway.json` usa o `Dockerfile` e o health check `/api/v1/health`. A variável `PORT` é definida pelo próprio Railway.

## Testes

```bash
pip install -r requirements-dev.txt
MEDIA_API_KEY=test-key python -m pytest -q
```

## Requisitos

- Ubuntu
- Python 3.10+
- FFmpeg

## Instalação

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg
```

Entre na pasta do projeto:

```bash
cd youtube_downloader
```

Crie o ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Executar

```bash
source .venv/bin/activate
uvicorn app:app --reload
```

Abra a documentação interativa:

http://127.0.0.1:8000/docs

Os arquivos serão salvos na pasta:

```text
downloads/
```

## Atualizar yt-dlp

```bash
source .venv/bin/activate
pip install -U yt-dlp
```

## Observações

A qualidade "Melhor disponível" tenta obter a melhor combinação de vídeo e áudio disponível. Para resoluções altas, o yt-dlp pode baixar vídeo e áudio separadamente e o FFmpeg fará a combinação.

Use a ferramenta somente para conteúdos que você tenha autorização para baixar e de acordo com as regras aplicáveis da plataforma.
