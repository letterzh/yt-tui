"""TUI для поиска, подписок и загрузки видео."""

import asyncio
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    ProgressBar,
    Static,
    TabbedContent,
    TabPane,
)

from planner.logic.video_service import VideoService
from planner.storage.database import VideoDatabase


class VideoApp(App[None]):
    """Главное окно видеотеки."""

    TITLE = "yt-tui — поиск и загрузка видео"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("q", "quit", "Выход", show=True),
        Binding("1", "show_tab('recommendations')", "Рекомендации", show=True),
        Binding("2", "show_tab('subscriptions')", "Подписки", show=True),
        Binding("3", "show_tab('search')", "Поиск", show=True),
        Binding("4", "show_tab('downloads')", "Загрузки", show=True),
        Binding("r", "refresh_recommendations", "Обновить ленту", show=True),
        Binding("s", "focus_search", "Поиск", show=True),
        Binding("d", "download_selected", "Скачать видео", show=True),
        Binding("x", "delete_subscription", "Удалить подписку", show=True),
    ]

    def __init__(self, service: VideoService, database: VideoDatabase) -> None:
        super().__init__()
        self.service = service
        self.database = database
        self.video_items: dict[str, dict[str, str]] = {}

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Не перехватывает клавиши загрузки и удаления в полях ввода."""
        if action not in {"download_selected", "delete_subscription"} or not self.is_mounted:
            return True
        active = self.query_one(TabbedContent).active
        if action == "download_selected":
            selector = {
                "recommendations": "#recommendation-table",
                "search": "#search-table",
            }.get(active)
            return selector is not None and self.focused is self.query_one(selector, DataTable)
        return active == "subscriptions" and self.focused is self.query_one(
            "#subscription-table", DataTable
        )

    def compose(self) -> ComposeResult:
        """Создаёт четыре вкладки приложения."""
        yield Header()
        with Vertical(id="main"):
            with TabbedContent(initial="recommendations", id="tabs"):
                with TabPane("Рекомендации", id="recommendations"):
                    with Horizontal(classes="toolbar"):
                        yield Button("Обновить видео каналов", id="refresh-recommendations", variant="primary")
                        yield Static("Новые ролики из локальных подписок", id="recommendation-status")
                    yield DataTable(id="recommendation-table", cursor_type="row")
                with TabPane("Подписки", id="subscriptions"):
                    with Horizontal(classes="toolbar"):
                        yield Input(placeholder="Название канала", id="subscription-name")
                        yield Input(placeholder="Ссылка на канал или автора", id="subscription-url")
                        yield Button("Добавить", id="add-subscription", variant="primary")
                    yield Static("Подписки хранятся на этом компьютере.", id="subscription-status")
                    yield DataTable(id="subscription-table", cursor_type="row")
                with TabPane("Поиск", id="search"):
                    with Horizontal(classes="toolbar"):
                        yield Input(placeholder="Название видео или ссылка", id="search-query")
                        yield Button("Найти", id="search-button", variant="primary")
                    yield Static("Поиск по YouTube или метаданные по прямой ссылке.", id="search-status")
                    yield DataTable(id="search-table", cursor_type="row")
                with TabPane("Загрузки", id="downloads"):
                    yield Static("Файлы сохраняются в папку downloads/.", id="download-status")
                    yield DataTable(id="downloads-table", cursor_type="row")
            with Horizontal(id="activity-bar"):
                yield Static("Готово", id="activity-label")
                yield ProgressBar(total=100, id="activity-progress")
        yield Footer()

    def on_mount(self) -> None:
        """Настраивает столбцы и загружает локальные записи."""
        self.query_one("#recommendation-table", DataTable).add_columns(
            "Видео", "Канал", "Длительность", "Ссылка"
        )
        self.query_one("#search-table", DataTable).add_columns(
            "Видео", "Канал", "Длительность", "Ссылка"
        )
        self.query_one("#subscription-table", DataTable).add_columns("Канал", "Ссылка")
        self.query_one("#downloads-table", DataTable).add_columns(
            "Видео", "Статус", "Файл", "Добавлено"
        )
        self.refresh_subscriptions()
        self.refresh_downloads()
        self.query_one("#recommendation-table", DataTable).focus()
        if self.database.list_subscriptions():
            self.action_refresh_recommendations()

    def refresh_subscriptions(self) -> None:
        """Обновляет список подписок из SQLite."""
        table = self.query_one("#subscription-table", DataTable)
        table.clear()
        for subscription in self.database.list_subscriptions():
            table.add_row(
                subscription["name"],
                subscription["url"],
                key=str(subscription["id"]),
            )

    def refresh_downloads(self) -> None:
        """Обновляет историю загрузок из SQLite."""
        table = self.query_one("#downloads-table", DataTable)
        table.clear()
        for download in self.database.list_downloads():
            table.add_row(
                download["title"],
                download["status"],
                download["file_path"] or "—",
                download["created_at"],
                key=str(download["id"]),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Обрабатывает кнопки действий во вкладках."""
        if event.button.id == "add-subscription":
            self.add_subscription()
        elif event.button.id == "search-button":
            self.action_search_videos()
        elif event.button.id == "refresh-recommendations":
            self.action_refresh_recommendations()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Запускает поиск по Enter из строки ввода."""
        if event.input.id == "search-query":
            self.action_search_videos()
        elif event.input.id == "subscription-url":
            self.add_subscription()

    def add_subscription(self) -> None:
        """Проверяет поля и сохраняет канал в локальной базе."""
        name_input = self.query_one("#subscription-name", Input)
        url_input = self.query_one("#subscription-url", Input)
        try:
            self.service.add_subscription(name_input.value, url_input.value)
        except Exception as error:
            self.notify(str(error), title="Не удалось добавить подписку", severity="warning")
            return
        name_input.value = ""
        url_input.value = ""
        self.refresh_subscriptions()
        self.query_one("#subscription-table", DataTable).focus()
        self.notify("Канал добавлен в подписки.")

    def action_delete_subscription(self) -> None:
        """Удаляет выбранный канал из локальной базы."""
        table = self.query_one("#subscription-table", DataTable)
        if self.focused is not table or table.row_count == 0:
            self.notify("Список подписок пуст.", severity="warning")
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        self.database.delete_subscription(int(row_key.value))
        self.refresh_subscriptions()
        self.query_one("#recommendation-table", DataTable).clear()
        self.notify("Подписка удалена.")

    def action_show_tab(self, tab_id: str) -> None:
        """Переключает вкладку по её номеру."""
        self.query_one(TabbedContent).active = tab_id
        focus_target = {
            "recommendations": "#recommendation-table",
            "subscriptions": "#subscription-name",
            "search": "#search-query",
            "downloads": "#downloads-table",
        }[tab_id]
        self.query_one(focus_target).focus()

    def action_next_tab(self) -> None:
        """Переходит на следующую вкладку по кругу."""
        tabs = ("recommendations", "subscriptions", "search", "downloads")
        tabbed = self.query_one(TabbedContent)
        next_tab = tabs[(tabs.index(tabbed.active) + 1) % len(tabs)]
        self.action_show_tab(next_tab)

    def action_focus_search(self) -> None:
        """Открывает вкладку поиска и ставит курсор в поле ввода."""
        self.query_one(TabbedContent).active = "search"
        self.query_one("#search-query", Input).focus()

    def action_search_videos(self) -> None:
        """Запускает поиск в рабочем потоке."""
        query = self.query_one("#search-query", Input).value.strip()
        if not query:
            self.notify("Введите запрос или ссылку на видео.", severity="warning")
            return
        self.query_one("#search-status", Static).update("Ищу видео…")
        self.search_videos(query)

    @work(exclusive=True, group="video-search")
    async def search_videos(self, query: str) -> None:
        """Получает результаты поиска, не блокируя интерфейс."""
        try:
            videos = await asyncio.to_thread(self.service.search, query)
        except Exception as error:
            self._show_search_error(str(error))
            return
        self._show_search_results(videos)

    def _show_search_error(self, message: str) -> None:
        """Показывает ошибку поиска в интерфейсе."""
        self.query_one("#search-status", Static).update("Не удалось выполнить поиск.")
        self.notify(message, title="Ошибка поиска", severity="error")

    def _show_search_results(self, videos: list[dict[str, str]]) -> None:
        """Рисует найденные видео в таблице."""
        self._fill_video_table("#search-table", videos)
        self.query_one("#search-status", Static).update(f"Найдено видео: {len(videos)}")
        self.query_one("#search-table", DataTable).focus()

    def action_refresh_recommendations(self) -> None:
        """Загружает свежие ролики каналов из локальных подписок."""
        if not self.database.list_subscriptions():
            self.notify("Сначала добавьте каналы во вкладке «Подписки».", severity="warning")
            return
        self.query_one("#recommendation-status", Static).update("Загружаю свежие ролики…")
        self.query_one(TabbedContent).active = "recommendations"
        self.get_recommendations()

    @work(exclusive=True, group="video-recommendations")
    async def get_recommendations(self) -> None:
        """Получает последние видео из каждого канала подписок."""
        try:
            videos = await asyncio.to_thread(self.service.recommendations)
        except Exception as error:
            self._show_recommendation_error(str(error))
            return
        self._show_recommendations(videos)

    def _show_recommendation_error(self, message: str) -> None:
        """Показывает понятное состояние при ошибке ленты."""
        self.query_one("#recommendation-status", Static).update("Не удалось обновить рекомендации.")
        self.notify(message, title="Ошибка ленты", severity="warning")

    def _show_recommendations(self, videos: list[dict[str, str]]) -> None:
        """Рисует свежие видео подписок."""
        self._fill_video_table("#recommendation-table", videos)
        self.query_one("#recommendation-status", Static).update(
            f"Свежих видео: {len(videos)}"
        )
        self.query_one("#recommendation-table", DataTable).focus()

    def _fill_video_table(self, selector: str, videos: list[dict[str, str]]) -> None:
        """Заполняет таблицу видео и запоминает ссылки выбранных строк."""
        table = self.query_one(selector, DataTable)
        table.clear()
        for video in videos:
            url = video["url"]
            self.video_items[url] = video
            table.add_row(
                video["title"],
                video.get("channel", ""),
                video.get("duration", ""),
                url,
                key=url,
            )

    def _selected_video(self) -> dict[str, str] | None:
        """Возвращает видео из активной таблицы рекомендаций или поиска."""
        active_tab = self.query_one(TabbedContent).active
        selector = {
            "recommendations": "#recommendation-table",
            "search": "#search-table",
        }.get(active_tab)
        if selector is None:
            return None
        table = self.query_one(selector, DataTable)
        if self.focused is not table or table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return self.video_items.get(str(row_key.value))

    def action_download_selected(self) -> None:
        """Начинает загрузку выбранного ролика в фоновом потоке."""
        video = self._selected_video()
        if video is None:
            self.notify("Выберите видео в поиске или рекомендациях.", severity="warning")
            return
        download_id = self.database.create_download(video["title"], video["url"])
        self.refresh_downloads()
        self.query_one("#activity-progress", ProgressBar).update(progress=0)
        self.query_one("#activity-label", Static).update(f"Загружаю: {video['title']}")
        self.download_video(download_id, video)

    @work(group="video-download")
    async def download_video(self, download_id: int, video: dict[str, str]) -> None:
        """Скачивает ролик и обновляет локальную историю."""
        loop = asyncio.get_running_loop()

        def report_progress(data: dict[str, Any]) -> None:
            """Передаёт процент загрузки в UI из рабочего потока."""
            if data.get("status") == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                percent = min(100, int(downloaded * 100 / total)) if total else 0
                loop.call_soon_threadsafe(self._set_download_progress, percent)

        try:
            file_path = await asyncio.to_thread(
                self.service.download,
                video["url"],
                report_progress,
            )
        except Exception as error:
            self.database.finish_download(download_id, "Ошибка")
            self._finish_download_ui("Ошибка", str(error))
            return
        self.database.finish_download(download_id, "Готово", file_path)
        self._finish_download_ui("Готово", file_path)

    def _set_download_progress(self, percent: int) -> None:
        """Обновляет индикатор активной загрузки."""
        self.query_one("#activity-progress", ProgressBar).update(progress=percent)

    def _finish_download_ui(self, status: str, detail: str) -> None:
        """Обновляет историю и уведомляет о результате."""
        self.refresh_downloads()
        self.query_one("#activity-label", Static).update(
            "Загрузка завершена" if status == "Готово" else "Ошибка загрузки"
        )
        if status == "Готово":
            self.query_one("#activity-progress", ProgressBar).update(progress=100)
            self.notify(f"Видео сохранено: {detail}", title="Готово")
        else:
            self.notify(detail or "Не удалось скачать видео.", title="Ошибка загрузки", severity="error")

    def on_key(self, event) -> None:
        """Переключает вкладки, сохраняя Tab для перемещения в формах."""
        if event.key == "tab" and not isinstance(self.focused, (Input, Button)):
            event.stop()
            self.action_next_tab()

