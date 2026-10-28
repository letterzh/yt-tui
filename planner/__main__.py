"""Загрузка настроек и запуск видеотеки."""

import os
from pathlib import Path
import sys


PACKAGE_NAMES = {
    "dotenv": "python-dotenv",
    "textual": "textual",
    "yt_dlp": "yt-dlp",
}


def main() -> None:
    """Загружает конфигурацию и запускает терминальное приложение."""
    # Импортируем пакеты здесь, чтобы показать понятную подсказку при пропуске установки.
    try:
        from dotenv import load_dotenv

        from planner.logic.video_service import VideoService
        from planner.storage.database import VideoDatabase
        from planner.ui.app import VideoApp
    except ModuleNotFoundError as error:
        package_name = PACKAGE_NAMES.get(error.name or "")
        if package_name is None:
            raise
        project_root = Path(__file__).resolve().parents[1]
        virtualenv_python = project_root / ".venv" / "bin" / "python"
        windows_venv_python = project_root / ".venv" / "Scripts" / "python.exe"
        if sys.prefix != sys.base_prefix:
            install_command = (
                ".venv/bin/python -m pip install -r requirements.txt"
                if virtualenv_python.exists()
                else "python -m pip install -r requirements.txt"
            )
            message = (
                f"Не найдена зависимость {package_name} в активном окружении. "
                f"Установите зависимости командой {install_command}."
            )
        elif virtualenv_python.exists():
            message = (
                f"Зависимость {package_name} не найдена в текущем Python, но рядом есть .venv. "
                "Запустите приложение командой .venv/bin/python -m planner "
                "или сначала выполните source .venv/bin/activate."
            )
        elif windows_venv_python.exists():
            message = (
                f"Зависимость {package_name} не найдена в текущем Python, но рядом есть .venv. "
                "Запустите приложение командой .venv\\Scripts\\python.exe -m planner "
                "или сначала выполните .venv\\Scripts\\activate."
            )
        else:
            message = (
                f"Не найдена зависимость {package_name}. Установите зависимости командой "
                "python -m pip install -r requirements.txt."
            )
        print(message, file=sys.stderr)
        raise SystemExit(1) from None

    load_dotenv()
    project_root = Path(__file__).resolve().parents[1]
    download_dir = Path(os.getenv("VIDEO_DOWNLOAD_DIR", "downloads")).expanduser()
    if not download_dir.is_absolute():
        download_dir = project_root / download_dir
    database = VideoDatabase()
    service = VideoService(database, download_dir)
    VideoApp(service, database).run()


if __name__ == "__main__":
    main()
