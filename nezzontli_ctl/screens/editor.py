import asyncio

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Markdown, Static, TextArea

from nezzontli_ctl import preview as preview_mod

try:
    from textual_image.widget import AutoImage
except ImportError:  # pragma: no cover — el preview cae a texto sin esto
    AutoImage = None

# Debounce del rebuild del preview: correr el tokenizer + renderizar
# LaTeX/imágenes en cada tecla sería carísimo, así que se espera una pausa
# corta en el tipeo antes de reconstruirlo.
_PREVIEW_DEBOUNCE = 0.5


class EditorScreen(ModalScreen[str]):
    """Editor de cuerpo Markdown con preview en vivo (Markdown + LaTeX
    renderizado + imágenes locales/remotas). Devuelve el texto final al
    llamador (ctrl+s / botón Listo) o None si se cancela (escape)."""

    BINDINGS = [
        ("ctrl+s", "submit", "Listo"),
        ("escape", "cancel", "Cancelar"),
    ]

    def __init__(self, initial_text: str = "", title: str = "Cuerpo"):
        super().__init__()
        self._initial_text = initial_text
        self._title = title
        self._debounce_timer = None

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
                yield VerticalScroll(id="editor-preview-scroll", classes="editor-pane")
        yield Footer()

    def on_mount(self) -> None:
        text_area = self.query_one("#editor-textarea", TextArea)
        text_area.focus()
        text_area.cursor_location = text_area.document.end
        self.watch(text_area, "scroll_y", self._sync_preview_scroll)
        self.run_worker(
            self._rebuild_preview(self._initial_text), exclusive=True, group="preview"
        )

    def _sync_preview_scroll(self, old_value: float, new_value: float) -> None:
        text_area = self.query_one("#editor-textarea", TextArea)
        preview_scroll = self.query_one("#editor-preview-scroll", VerticalScroll)
        max_ta = text_area.max_scroll_y
        if not max_ta:
            return
        ratio = max(0.0, min(1.0, new_value / max_ta))
        preview_scroll.scroll_y = ratio * preview_scroll.max_scroll_y

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        text = event.text_area.text
        self._debounce_timer = self.set_timer(
            _PREVIEW_DEBOUNCE, lambda: self._start_rebuild(text)
        )

    def _start_rebuild(self, text: str) -> None:
        self.run_worker(self._rebuild_preview(text), exclusive=True, group="preview")

    async def _rebuild_preview(self, text: str) -> None:
        """Tokeniza `text` y remonta el preview como una mezcla de widgets
        Markdown (texto normal) e Image (fórmulas LaTeX renderizadas a PNG,
        imágenes locales del repo o remotas por URL)."""
        segments = await asyncio.to_thread(preview_mod.tokenize, text)
        widgets = []
        for segment in segments:
            kind = segment[0]
            if kind == "text":
                if segment[1].strip():
                    widgets.append(Markdown(segment[1]))
            elif kind == "math":
                _, tex, is_display = segment
                png_path = await asyncio.to_thread(preview_mod.render_math, tex, is_display)
                if png_path is not None and AutoImage is not None:
                    widgets.append(AutoImage(str(png_path), classes="preview-math"))
                else:
                    widgets.append(Static(f"[$] {tex}", classes="preview-fallback"))
            elif kind == "image":
                _, ref, alt = segment
                img_path = await asyncio.to_thread(preview_mod.resolve_image, ref)
                if img_path is not None and AutoImage is not None:
                    widgets.append(AutoImage(str(img_path), classes="preview-image"))
                else:
                    widgets.append(Static(f"[img no encontrada: {ref}]", classes="preview-fallback"))
                if alt:
                    widgets.append(Static(alt, classes="preview-caption"))

        preview_scroll = self.query_one("#editor-preview-scroll", VerticalScroll)
        await preview_scroll.remove_children()
        await preview_scroll.mount_all(widgets or [Markdown("")])

    def action_submit(self) -> None:
        text = self.query_one("#editor-textarea", TextArea).text
        self.dismiss(text)

    def action_cancel(self) -> None:
        self.dismiss(None)
