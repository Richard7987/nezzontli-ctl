from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Markdown, Static, TextArea


class EditorScreen(ModalScreen[str]):
    """Editor de cuerpo Markdown con preview en vivo. Devuelve el texto final
    al llamador (ctrl+s / botón Listo) o None si se cancela (escape)."""

    BINDINGS = [
        ("ctrl+s", "submit", "Listo"),
        ("escape", "cancel", "Cancelar"),
    ]

    def __init__(self, initial_text: str = "", title: str = "Cuerpo"):
        super().__init__()
        self._initial_text = initial_text
        self._title = title

    def compose(self):
        with Vertical():
            yield Static(f" {self._title}", id="editor-title")
            with Horizontal(classes="editor-split"):
                yield TextArea(
                    self._initial_text,
                    language="markdown",
                    show_line_numbers=True,
                    id="editor-textarea",
                    classes="editor-pane",
                )
                with VerticalScroll(id="editor-preview-scroll", classes="editor-pane"):
                    yield Markdown(self._initial_text, id="editor-preview")
        yield Footer()

    def on_mount(self) -> None:
        text_area = self.query_one("#editor-textarea", TextArea)
        text_area.focus()
        text_area.cursor_location = text_area.document.end
        self.watch(text_area, "scroll_y", self._sync_preview_scroll)

    def _sync_preview_scroll(self, old_value: float, new_value: float) -> None:
        text_area = self.query_one("#editor-textarea", TextArea)
        preview_scroll = self.query_one("#editor-preview-scroll", VerticalScroll)
        max_ta = text_area.max_scroll_y
        if not max_ta:
            return
        ratio = max(0.0, min(1.0, new_value / max_ta))
        preview_scroll.scroll_y = ratio * preview_scroll.max_scroll_y

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        preview = self.query_one("#editor-preview", Markdown)
        preview.update(event.text_area.text)

    def action_submit(self) -> None:
        text = self.query_one("#editor-textarea", TextArea).text
        self.dismiss(text)

    def action_cancel(self) -> None:
        self.dismiss(None)
