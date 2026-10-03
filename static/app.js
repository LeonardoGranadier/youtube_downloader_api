const urlInput =
    document.getElementById("url");

const infoBtn =
    document.getElementById("infoBtn");

const downloadBtn =
    document.getElementById("downloadBtn");

const typeSelect =
    document.getElementById("type");

const qualityBox =
    document.getElementById("qualityBox");

const qualitySelect =
    document.getElementById("quality");

const preview =
    document.getElementById("preview");

const thumb =
    document.getElementById("thumb");

const title =
    document.getElementById("title");

const uploader =
    document.getElementById("uploader");

const duration =
    document.getElementById("duration");

const status =
    document.getElementById("status");

const statusText =
    document.getElementById("statusText");

const percent =
    document.getElementById("percent");

const bar =
    document.getElementById("bar");

const speed =
    document.getElementById("speed");

const eta =
    document.getElementById("eta");

const result =
    document.getElementById("result");

const filename =
    document.getElementById("filename");

const downloadLink =
    document.getElementById("downloadLink");

const errorBox =
    document.getElementById("error");

let currentDownloadId = null;

let progressTimer = null;


/* ============================================================
   UTILITÁRIOS
   ============================================================ */

function showError(message) {

    errorBox.textContent = message;

    errorBox.classList.remove(
        "hidden"
    );
}


function clearError() {

    errorBox.classList.add(
        "hidden"
    );

    errorBox.textContent = "";
}


function formatDuration(seconds) {

    if (!seconds) {
        return "";
    }

    seconds = Number(seconds);

    const hours =
        Math.floor(seconds / 3600);

    const minutes =
        Math.floor(
            (seconds % 3600) / 60
        );

    const secs =
        Math.floor(seconds % 60);

    if (hours > 0) {

        return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

    }

    return `${minutes}:${String(secs).padStart(2, "0")}`;
}


function formatBytes(bytes) {

    if (!bytes) {
        return "0 B";
    }

    const units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB"
    ];

    let value = Number(bytes);

    let index = 0;

    while (
        value >= 1024 &&
        index < units.length - 1
    ) {

        value /= 1024;

        index++;

    }

    return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}


function escapeHtml(value) {

    if (!value) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


/* ============================================================
   NAVEGAÇÃO
   ============================================================ */

const navItems =
    document.querySelectorAll(
        ".nav-item"
    );

const pages = {

    dashboard:
        document.getElementById(
            "page-dashboard"
        ),

    history:
        document.getElementById(
            "page-history"
        ),

    library:
        document.getElementById(
            "page-library"
        ),

};


function openPage(pageName) {

    Object.values(pages)
        .forEach(page => {
            page.classList.remove(
                "active-page"
            );
        });

    pages[pageName]
        .classList.add(
            "active-page"
        );

    navItems.forEach(button => {

        button.classList.toggle(
            "active",
            button.dataset.page === pageName
        );

    });

    const titles = {

        dashboard: [
            "Dashboard",
            "Baixe e organize seus arquivos de mídia."
        ],

        history: [
            "Histórico",
            "Todos os downloads realizados."
        ],

        library: [
            "Biblioteca",
            "Arquivos armazenados localmente."
        ],

    };

    document.getElementById(
        "pageTitle"
    ).textContent =
        titles[pageName][0];

    document.getElementById(
        "pageDescription"
    ).textContent =
        titles[pageName][1];


    if (pageName === "history") {
        loadHistory();
    }

    if (pageName === "library") {
        loadLibrary();
    }

}


navItems.forEach(button => {

    button.addEventListener(
        "click",
        () => {

            openPage(
                button.dataset.page
            );

        }
    );

});


document.getElementById(
    "openHistory"
).addEventListener(
    "click",
    () => openPage("history")
);


/* ============================================================
   TIPO DE MÍDIA
   ============================================================ */

typeSelect.addEventListener(
    "change",
    () => {

        qualityBox.style.display =
            typeSelect.value === "audio"
                ? "none"
                : "block";

    }
);


/* ============================================================
   ANALISAR URL
   ============================================================ */

infoBtn.addEventListener(
    "click",
    analyzeVideo
);


urlInput.addEventListener(
    "keydown",
    event => {

        if (event.key === "Enter") {
            analyzeVideo();
        }

    }
);


async function analyzeVideo() {

    clearError();

    const url =
        urlInput.value.trim();

    if (!url) {

        showError(
            "Cole uma URL primeiro."
        );

        return;
    }

    infoBtn.disabled = true;

    infoBtn.textContent =
        "Analisando...";

    try {

        const body =
            new FormData();

        body.append(
            "url",
            url
        );

        const response =
            await fetch(
                "/api/info",
                {
                    method: "POST",
                    body
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Não foi possível analisar o vídeo."
            );

        }

        title.textContent =
            data.title ||
            "Sem título";

        uploader.textContent =
            data.uploader
                ? `Canal: ${data.uploader}`
                : "";

        duration.textContent =
            data.duration
                ? `Duração: ${formatDuration(data.duration)}`
                : "";

        if (data.thumbnail) {

            thumb.src =
                data.thumbnail;

        }

        preview.classList.remove(
            "hidden"
        );


        /*
         * Seleciona automaticamente
         * uma qualidade disponível.
         */

        if (
            Array.isArray(
                data.available_heights
            )
        ) {

            const heights =
                data.available_heights;

            const preferred = [
                "2160",
                "1440",
                "1080",
                "720",
                "480",
                "360"
            ];

            let selected =
                "best";

            for (
                const value of preferred
            ) {

                if (
                    heights.includes(
                        Number(value)
                    )
                ) {

                    selected = value;

                    break;
                }

            }

            const option =
                [...qualitySelect.options]
                    .find(
                        item =>
                            item.value === selected
                    );

            if (option) {
                qualitySelect.value =
                    selected;
            }

        }

    } catch (error) {

        showError(
            error.message
        );

    } finally {

        infoBtn.disabled = false;

        infoBtn.textContent =
            "Analisar";

    }
}


/* ============================================================
   INICIAR DOWNLOAD
   ============================================================ */

downloadBtn.addEventListener(
    "click",
    startDownload
);


async function startDownload() {

    clearError();

    result.classList.add(
        "hidden"
    );

    const url =
        urlInput.value.trim();

    if (!url) {

        showError(
            "Cole uma URL primeiro."
        );

        return;
    }

    const body =
        new FormData();

    body.append(
        "url",
        url
    );

    body.append(
        "quality",
        qualitySelect.value
    );

    body.append(
        "media_type",
        typeSelect.value
    );

    downloadBtn.disabled = true;

    downloadBtn.textContent =
        "Iniciando...";

    status.classList.remove(
        "hidden"
    );

    statusText.textContent =
        "Colocado na fila...";

    percent.textContent =
        "0%";

    bar.style.width =
        "0%";

    speed.textContent =
        "-";

    eta.textContent =
        "-";

    try {

        const response =
            await fetch(
                "/api/download",
                {
                    method: "POST",
                    body
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Não foi possível iniciar o download."
            );

        }

        currentDownloadId =
            data.download_id;

        monitorDownload(
            currentDownloadId
        );

    } catch (error) {

        showError(
            error.message
        );

        resetDownloadButton();

    }

}


/* ============================================================
   MONITORAR DOWNLOAD
   ============================================================ */

function monitorDownload(
    downloadId
) {

    if (progressTimer) {

        clearInterval(
            progressTimer
        );

    }

    checkProgress(
        downloadId
    );

    progressTimer =
        setInterval(
            () => checkProgress(
                downloadId
            ),
            800
        );

}


async function checkProgress(
    downloadId
) {

    try {

        const response =
            await fetch(
                `/api/progress/${downloadId}`
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Erro ao consultar download."
            );

        }

        const progress =
            Number(
                data.progress || 0
            );

        bar.style.width =
            `${progress}%`;

        percent.textContent =
            `${progress}%`;

        speed.textContent =
            data.speed ||
            "-";

        eta.textContent =
            data.eta
                ? `ETA: ${data.eta}`
                : "-";


        if (
            data.status ===
            "queued"
        ) {

            statusText.textContent =
                "Na fila...";

        }

        else if (
            data.status ===
            "starting"
        ) {

            statusText.textContent =
                "Preparando download...";

        }

        else if (
            data.status ===
            "downloading"
        ) {

            statusText.textContent =
                "Baixando...";

        }

        else if (
            data.status ===
            "processing"
        ) {

            statusText.textContent =
                "Processando com FFmpeg...";

        }

        else if (
            data.status ===
            "completed"
        ) {

            clearInterval(
                progressTimer
            );

            progressTimer = null;

            statusText.textContent =
                "Concluído!";

            bar.style.width =
                "100%";

            percent.textContent =
                "100%";

            filename.textContent =
                data.filename ||
                "Arquivo";

            downloadLink.href =
                `/api/file/${encodeURIComponent(data.filename)}`;

            result.classList.remove(
                "hidden"
            );

            resetDownloadButton();

            loadStats();

            loadRecent();

        }

        else if (
            data.status ===
            "error"
        ) {

            clearInterval(
                progressTimer
            );

            progressTimer = null;

            throw new Error(
                data.error ||
                "Erro durante o download."
            );

        }

    } catch (error) {

        if (progressTimer) {

            clearInterval(
                progressTimer
            );

            progressTimer = null;

        }

        showError(
            error.message
        );

        resetDownloadButton();

    }

}


/* ============================================================
   RESET
   ============================================================ */

function resetDownloadButton() {

    downloadBtn.disabled =
        false;

    downloadBtn.textContent =
        "↓ Iniciar download";

}


/* ============================================================
   ESTATÍSTICAS
   ============================================================ */

async function loadStats() {

    try {

        const response =
            await fetch(
                "/api/stats"
            );

        const data =
            await response.json();

        document.getElementById(
            "statTotal"
        ).textContent =
            data.total;

        document.getElementById(
            "statCompleted"
        ).textContent =
            data.completed;

        document.getElementById(
            "statFiles"
        ).textContent =
            data.files;

        document.getElementById(
            "statStorage"
        ).textContent =
            formatBytes(
                data.storage_bytes
            );

    } catch (error) {

        console.error(
            error
        );

    }

}


/* ============================================================
   RECENTES
   ============================================================ */

async function loadRecent() {

    const container =
        document.getElementById(
            "recentList"
        );

    try {

        const response =
            await fetch(
                "/api/history"
            );

        const data =
            await response.json();

        const downloads =
            data.downloads.slice(
                0,
                5
            );

        if (!downloads.length) {

            container.innerHTML =
                `<div class="empty">
                    Nenhum download realizado ainda.
                </div>`;

            return;
        }

        container.innerHTML =
            downloads
                .map(renderDownload)
                .join("");

    } catch (error) {

        container.innerHTML =
            `<div class="empty">
                Não foi possível carregar o histórico.
            </div>`;

    }

}


/* ============================================================
   HISTÓRICO
   ============================================================ */

async function loadHistory() {

    const container =
        document.getElementById(
            "historyList"
        );

    container.innerHTML =
        `<div class="empty">
            Carregando...
        </div>`;

    try {

        const response =
            await fetch(
                "/api/history"
            );

        const data =
            await response.json();

        if (!data.downloads.length) {

            container.innerHTML =
                `<div class="empty">
                    Nenhum download realizado ainda.
                </div>`;

            return;
        }

        container.innerHTML =
            data.downloads
                .map(renderDownload)
                .join("");

    } catch (error) {

        container.innerHTML =
            `<div class="empty">
                Erro ao carregar histórico.
            </div>`;

    }

}


function renderDownload(
    item
) {

    const image =
        item.thumbnail
            ? `<img
                class="item-thumb"
                src="${escapeHtml(item.thumbnail)}"
                alt=""
              >`
            : `<div class="item-thumb"></div>`;

    let status =
        item.status;

    if (status === "completed") {
        status = "Concluído";
    }

    else if (status === "error") {
        status = "Erro";
    }

    else if (status === "downloading") {
        status = `${item.progress || 0}%`;
    }

    else if (status === "processing") {
        status = "Processando";
    }

    else if (status === "queued") {
        status = "Na fila";
    }

    const action =
        item.filename
            ? `<a
                class="item-action"
                href="/api/file/${encodeURIComponent(item.filename)}"
              >
                Abrir
              </a>`
            : "";

    return `
        <div class="list-item">

            ${image}

            <div class="item-main">

                <strong>
                    ${escapeHtml(
                        item.title ||
                        item.filename ||
                        item.url
                    )}
                </strong>

                <span>
                    ${escapeHtml(
                        item.media_type === "audio"
                            ? "MP3"
                            : `${item.quality || "Melhor"}`
                    )}
                    ·
                    ${escapeHtml(
                        item.created_at || ""
                    )}
                </span>

            </div>

            <span class="item-status">
                ${escapeHtml(status)}
            </span>

            ${action}

        </div>
    `;
}


/* ============================================================
   BIBLIOTECA
   ============================================================ */

async function loadLibrary() {

    const container =
        document.getElementById(
            "libraryList"
        );

    container.innerHTML =
        `<div class="empty">
            Carregando arquivos...
        </div>`;

    try {

        const response =
            await fetch(
                "/api/library"
            );

        const data =
            await response.json();

        if (!data.files.length) {

            container.innerHTML =
                `<div class="empty">
                    Sua biblioteca está vazia.
                </div>`;

            return;
        }

        container.innerHTML =
            data.files
                .map(renderLibraryFile)
                .join("");

    } catch (error) {

        container.innerHTML =
            `<div class="empty">
                Erro ao carregar biblioteca.
            </div>`;

    }

}


function renderLibraryFile(
    file
) {

    const url =
        `/api/file/${encodeURIComponent(file.name)}`;

    return `
        <div class="list-item">

            <div class="item-thumb">
            </div>

            <div class="item-main">

                <strong>
                    ${escapeHtml(file.name)}
                </strong>

                <span>
                    ${escapeHtml(
                        file.extension
                    )}
                    ·
                    ${formatBytes(
                        file.size
                    )}
                    ·
                    ${escapeHtml(
                        file.modified
                    )}
                </span>

            </div>

            <a
                class="item-action"
                href="${url}"
            >
                Baixar
            </a>

            <button
                class="item-action"
                onclick="deleteLibraryFile(${JSON.stringify(file.name)})"
            >
                Excluir
            </button>

        </div>
    `;

}


async function deleteLibraryFile(
    name
) {

    const confirmed =
        confirm(
            `Excluir "${name}"?`
        );

    if (!confirmed) {
        return;
    }

    try {

        const response =
            await fetch(
                `/api/file/${encodeURIComponent(name)}`,
                {
                    method: "DELETE"
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Não foi possível excluir."
            );

        }

        loadLibrary();
        loadStats();

    } catch (error) {

        showError(
            error.message
        );

    }

}


/* ============================================================
   LIMPAR HISTÓRICO
   ============================================================ */

document.getElementById(
    "clearHistory"
).addEventListener(
    "click",
    async () => {

        const confirmed =
            confirm(
                "Deseja realmente limpar todo o histórico?"
            );

        if (!confirmed) {
            return;
        }

        try {

            const response =
                await fetch(
                    "/api/history",
                    {
                        method: "DELETE"
                    }
                );

            if (!response.ok) {

                throw new Error(
                    "Não foi possível limpar o histórico."
                );

            }

            loadHistory();
            loadRecent();
            loadStats();

        } catch (error) {

            showError(
                error.message
            );

        }

    }
);


/* ============================================================
   INICIALIZAÇÃO
   ============================================================ */

loadStats();

loadRecent();