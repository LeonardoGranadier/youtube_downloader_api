# YouTube Downloader Local

Aplicação local em Python para baixar vídeos/áudios usando FastAPI + yt-dlp + FFmpeg.

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

Abra:

http://127.0.0.1:8000

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
