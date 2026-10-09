# Mil1Utilidades Media API

API em Python (FastAPI + yt-dlp + FFmpeg) para baixar vídeos/áudios de sites com conteúdo de licença livre, usada pelo Mil1 Utilidades.

## Sites permitidos

Somente domínios da lista `ALLOWED_SITES` em `config.py` (hoje: `archive.org` e `wikimedia.org`). O extrator genérico do yt-dlp nunca é liberado, o que impede o servidor de acessar URLs arbitrárias (SSRF).

- **YouTube**: fora da lista. Bloqueia IPs de datacenter (testado no Railway em 2026-10-09: "Sign in to confirm you're not a bot").
- **Vimeo**: fora da lista. O yt-dlp passou a exigir conta logada.

## Endpoints (todos exigem o cabeçalho `X-API-Key`)

- `GET /api/v1/media/sites`: domínios aceitos
- `POST /api/v1/media/info` `{ "url" }`: título, duração e resoluções
- `POST /api/v1/media/download` `{ "url", "media_type": "video"|"audio", "quality": "360"|"480"|"720"|"1080"|"best" }`: `202` com `{ "id" }`
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
