import asyncio
import logging
from contextlib import asynccontextmanager

from services import net_guard

# Antes de qualquer outra coisa: toda conexão de saída do processo passa
# a aceitar só endereços públicos (SSRF, ADR-071 do Mil1).
net_guard.install()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import API_PREFIX
from database.database import init_database

from api.media import router as media_router
from api.downloads import router as downloads_router
from api.files import router as files_router

from services.download_manager import (
    cleanup_loop,
    start_queue,
    stop_queue,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa o banco de dados
    init_database()

    # Recupera registros de downloads interrompidos
    from database.database import get_connection

    connection = get_connection()

    try:
        connection.execute(
            """
            UPDATE downloads
            SET
                status = ?,
                error = ?,
                speed = NULL,
                eta = NULL
            WHERE status IN (
                'queued',
                'starting',
                'downloading',
                'processing'
            )
            """,
            (
                "error",
                "Download interrompido porque o servidor foi reiniciado.",
            ),
        )

        connection.commit()

    finally:
        connection.close()

    # Inicia a fila de downloads
    await start_queue()

    # Remove arquivos e registros expirados periodicamente
    cleanup_task = asyncio.create_task(cleanup_loop())

    try:
        yield
    finally:
        cleanup_task.cancel()

        # Para a fila quando a aplicação for encerrada
        await stop_queue()


app = FastAPI(
    title="Mil1Utilidades Media API",
    description=(
        "API para download e gerenciamento "
        "de mídia."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "https://www.mil1utilidades.com.br",
        "https://mil1utilidades.com.br",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(
    media_router,
    prefix=API_PREFIX,
)

app.include_router(
    downloads_router,
    prefix=API_PREFIX,
)

app.include_router(
    files_router,
    prefix=API_PREFIX,
)


@app.get("/")
async def root():
    return {
        "name": "Mil1Utilidades Media API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
    }


@app.get(
    f"{API_PREFIX}/health",
)
async def health():
    return {
        "status": "ok",
        "service": "media-api",
        "version": "1.0.0",
    }