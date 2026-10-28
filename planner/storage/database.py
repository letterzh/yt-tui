"""Локальная SQLite-база подписок и истории загрузок."""

import sqlite3
from pathlib import Path
from typing import Any


class VideoDatabase:
    """Хранит подписки пользователя и результаты загрузки видео."""

    def __init__(self, database_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.database_path = database_path or project_root / "videos.sqlite3"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        """Открывает соединение, возвращающее строки в виде словарей."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_tables(self) -> None:
        """Создаёт таблицы при первом запуске."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    file_path TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def list_subscriptions(self) -> list[dict[str, Any]]:
        """Возвращает подписки в порядке добавления."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, url FROM subscriptions ORDER BY id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_subscription(self, name: str, url: str) -> None:
        """Сохраняет канал или страницу автора."""
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO subscriptions (name, url) VALUES (?, ?)",
                    (name, url),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Этот канал уже есть в подписках.") from error

    def delete_subscription(self, subscription_id: int) -> None:
        """Удаляет подписку по её идентификатору."""
        with self._connect() as connection:
            connection.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))

    def create_download(self, title: str, url: str) -> int:
        """Добавляет запись о начале загрузки."""
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO downloads (title, url, status) VALUES (?, ?, 'Загружается')",
                (title, url),
            )
            return int(cursor.lastrowid)

    def finish_download(self, download_id: int, status: str, file_path: str = "") -> None:
        """Обновляет статус и путь завершённой загрузки."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE downloads SET status = ?, file_path = ? WHERE id = ?",
                (status, file_path, download_id),
            )

    def list_downloads(self, limit: int = 100) -> list[dict[str, Any]]:
        """Показывает последние загрузки."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, url, file_path, status, created_at
                FROM downloads ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
