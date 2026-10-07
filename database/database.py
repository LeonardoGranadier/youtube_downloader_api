import sqlite3

from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database() -> None:
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT,
            uploader TEXT,
            thumbnail TEXT,
            media_type TEXT NOT NULL,
            quality TEXT,
            status TEXT NOT NULL,
            progress REAL DEFAULT 0,
            speed TEXT,
            eta TEXT,
            filename TEXT,
            filepath TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
        """
    )

    connection.commit()
    connection.close()

def create_download(download_id: str, **fields) -> None:
    allowed_fields = {
        "url",
        "title",
        "uploader",
        "thumbnail",
        "media_type",
        "quality",
        "status",
        "progress",
        "speed",
        "eta",
        "filename",
        "filepath",
        "error",
        "created_at",
        "completed_at",
    }

    fields = {
        key: value
        for key, value in fields.items()
        if key in allowed_fields
    }

    fields["id"] = download_id

    columns = ", ".join(fields.keys())
    placeholders = ", ".join(
        "?"
        for _ in fields
    )

    values = list(fields.values())

    connection = get_connection()

    connection.execute(
        f"""
        INSERT INTO downloads (
            {columns}
        )
        VALUES (
            {placeholders}
        )
        """,
        values,
    )

    connection.commit()
    connection.close()

def update_download(download_id: str, **fields) -> None:
    if not fields:
        return

    allowed_fields = {
        "url",
        "title",
        "uploader",
        "thumbnail",
        "media_type",
        "quality",
        "status",
        "progress",
        "speed",
        "eta",
        "filename",
        "filepath",
        "error",
        "created_at",
        "completed_at",
    }

    fields = {
        key: value
        for key, value in fields.items()
        if key in allowed_fields
    }

    if not fields:
        return

    assignments = ", ".join(
        f"{key} = ?"
        for key in fields
    )

    values = list(fields.values())
    values.append(download_id)

    connection = get_connection()

    connection.execute(
        f"""
        UPDATE downloads
        SET {assignments}
        WHERE id = ?
        """,
        values,
    )

    connection.commit()
    connection.close()


def get_download(download_id: str):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM downloads
        WHERE id = ?
        """,
        (download_id,),
    ).fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


def get_downloads():
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM downloads
        ORDER BY created_at DESC
        """
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def delete_download(download_id: str) -> bool:
    connection = get_connection()

    cursor = connection.execute(
        """
        DELETE FROM downloads
        WHERE id = ?
        """,
        (download_id,),
    )

    connection.commit()
    connection.close()

    return cursor.rowcount > 0