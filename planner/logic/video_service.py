"""Поиск, рекомендации и скачивание видео через yt-dlp."""

from pathlib import Path
import shutil
from typing import Any, Callable
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from planner.storage.database import VideoDatabase


class VideoService:
    """Объединяет локальные подписки с поиском и загрузкой видео."""

    def __init__(self, database: VideoDatabase, download_dir: Path) -> None:
        self.database = database
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_subscription(name: str, url: str) -> tuple[str, str]:
        """Проверяет название и ссылку на канал."""
        clean_name = name.strip()
        clean_url = url.strip()
        parsed = urlparse(clean_url)
        if not clean_url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Укажите ссылку канала, начинающуюся с http:// или https://.")
        if not clean_name:
            clean_name = parsed.netloc
        return clean_name, clean_url

    def add_subscription(self, name: str, url: str) -> None:
        """Проверяет и добавляет новую подписку."""
        clean_name, clean_url = self.validate_subscription(name, url)
        self.database.add_subscription(clean_name, clean_url)

    @staticmethod
    def _ydl_options(**options: Any) -> dict[str, Any]:
        """Общие настройки: yt-dlp не пишет служебный вывод в терминал."""
        return {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "skip_download": True,
            **options,
        }

    @staticmethod
    def _video_from_entry(entry: dict[str, Any]) -> dict[str, str] | None:
        """Оставляет поля, которые нужны спискам и загрузчику."""
        video_id = str(entry.get("id") or "")
        url = str(entry.get("webpage_url") or entry.get("original_url") or entry.get("url") or "")
        extractor = str(entry.get("ie_key") or entry.get("extractor_key") or "").lower()
        if url and not url.startswith(("http://", "https://")):
            if video_id and "youtube" in extractor:
                url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                return None
        if not url:
            return None
        return {
            "title": str(entry.get("title") or video_id or "Видео без названия"),
            "url": url,
            "channel": str(entry.get("channel") or entry.get("uploader") or ""),
            "duration": str(entry.get("duration_string") or ""),
        }

    def search(self, query: str, limit: int = 20) -> list[dict[str, str]]:
        """Ищет на YouTube по тексту или загружает сведения по прямой ссылке."""
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Введите запрос для поиска.")
        with YoutubeDL(self._ydl_options(extract_flat="in_playlist", playlistend=limit)) as ydl:
            if urlparse(clean_query).scheme in {"http", "https"}:
                result = ydl.extract_info(clean_query, download=False)
            else:
                result = ydl.extract_info(f"ytsearch{limit}:{clean_query}", download=False)
        if result and not result.get("entries"):
            video = self._video_from_entry(result)
            return [video] if video is not None else []
        entries = (result or {}).get("entries") or []
        return [
            video
            for entry in entries
            if entry and (video := self._video_from_entry(entry)) is not None
        ]

    def recommendations(self, limit_per_channel: int = 5) -> list[dict[str, str]]:
        """Собирает последние ролики из добавленных каналов."""
        videos: list[dict[str, str]] = []
        options = self._ydl_options(extract_flat="in_playlist", playlistend=limit_per_channel)
        with YoutubeDL(options) as ydl:
            for subscription in self.database.list_subscriptions():
                try:
                    result = ydl.extract_info(subscription["url"], download=False)
                except Exception:
                    # Один недоступный канал не должен скрывать видео остальных подписок.
                    continue
                entries = (result or {}).get("entries") or []
                for entry in entries:
                    if not entry:
                        continue
                    video = self._video_from_entry(entry)
                    if video is not None:
                        video["channel"] = video["channel"] or subscription["name"]
                        videos.append(video)
        return videos

    def download(
        self,
        url: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        """Скачивает видео в выбранную папку и возвращает путь к файлу."""
        self.download_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg_path = shutil.which("ffmpeg")
        options: dict[str, Any] = {
            # Без ffmpeg берём готовый видеофайл, который не нужно склеивать.
            "format": "bestvideo*+bestaudio/best" if ffmpeg_path else "best[ext=mp4]/best",
            "outtmpl": str(self.download_dir / "%(title).180B [%(id)s].%(ext)s"),
            "noplaylist": True,
            "overwrites": False,
            "quiet": True,
            "no_warnings": True,
        }
        if ffmpeg_path:
            options["ffmpeg_location"] = ffmpeg_path
            options["merge_output_format"] = "mp4"
        if progress_callback is not None:
            options["progress_hooks"] = [progress_callback]
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("Не удалось получить видео по этой ссылке.")
            filename = info.get("_filename") or ydl.prepare_filename(info)
        return str(Path(filename).resolve())
