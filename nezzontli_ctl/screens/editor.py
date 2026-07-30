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
        # (línea de origen, widget) por cada widget montado en el preview,
        # en orden — permite anclar el scroll a la línea exacta que se está
        # editando en vez de una proporción de alturas (que se rompe apenas
        # hay imágenes/fórmulas con alturas fijas distintas a las del texto).
        self._preview_anchors: list[tuple[int, object]] = []

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
        """TextArea es un widget de líneas monoespaciadas: scroll_y ES el
        número de línea de origen que está arriba del viewport (no hace
        falta convertir a proporción). Con eso buscamos qué widget del
        preview corresponde a esa línea y lo llevamos al tope — anclado al
        contenido real, no a una altura proporcional que se desalinea en
        cuanto hay imágenes/fórmulas de altura fija."""
        if not self._preview_anchors:
            return
        top_line = round(new_value)
        target = self._preview_anchors[0][1]
        for line, widget in self._preview_anchors:
            if line <= top_line:
                target = widget
            else:
                break
        if not target.is_mounted:
            # El preview se está reconstruyendo (worker en curso) y este
            # anchor ya quedó viejo — el próximo rebuild trae anchors nuevos.
            return
        preview_scroll = self.query_one("#editor-preview-scroll", VerticalScroll)
        preview_scroll.scroll_to_widget(target, animate=False, top=True)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        text = event.text_area.text
        self._debounce_timer = self.set_timer(
            _PREVIEW_DEBOUNCE, lambda: self._start_rebuild(text)
        )

    def _start_rebuild(self, text: str) -> None:
        self.run_worker(self._rebuild_preview(text), exclusive=True, group="preview")

    async def _render_segment(self, segment) -> list:
        """Renderiza un segmento a 0+ widgets. Corre en paralelo para todos
        los segmentos vía asyncio.gather (cada render_math/resolve_image
        pesado va a un hilo aparte, así una fórmula lenta no bloquea a las
        demás ni a la UI)."""
        kind = segment[0]
        if kind == "text":
            _, chunk, _start = segment
            return [Markdown(chunk)] if chunk.strip() else []

        if kind == "math":
            _, tex, is_display, _start = segment
            png_path = await asyncio.to_thread(preview_mod.render_math, tex, is_display)
            if png_path is not None and AutoImage is not None:
                return [AutoImage(str(png_path), classes="preview-math")]
            return [Static(f"[$] {tex}", classes="preview-fallback")]

        if kind == "image":
            _, ref, alt, _start = segment
            img_path = await asyncio.to_thread(preview_mod.resolve_image, ref)
            if img_path is not None and AutoImage is not None:
                widgets = [AutoImage(str(img_path), classes="preview-image")]
            else:
                widgets = [Static(f"[img no encontrada: {ref}]", classes="preview-fallback")]
            if alt:
                widgets.append(Static(alt, classes="preview-caption"))
            return widgets

        return []

    async def _rebuild_preview(self, text: str) -> None:
        """Tokeniza `text` y remonta el preview como una mezcla de widgets
        Markdown (texto normal) e Image (fórmulas LaTeX renderizadas a PNG,
        imágenes locales del repo o remotas por URL)."""
        preview_scroll = self.query_one("#editor-preview-scroll", VerticalScroll)
        segments = await asyncio.to_thread(preview_mod.tokenize, text)

        if any(segment[0] in ("math", "image") for segment in segments):
            await preview_scroll.remove_children()
            await preview_scroll.mount(
                Static("⏳ Renderizando fórmulas e imágenes…", classes="preview-loading")
            )

        rendered_groups = await asyncio.gather(
            *(self._render_segment(segment) for segment in segments)
        )

        widgets = []
        anchors = []
        for segment, group in zip(segments, rendered_groups):
            line = text.count("\n", 0, segment[-1])
            for widget in group:
                widgets.append(widget)
                anchors.append((line, widget))

        await preview_scroll.remove_children()
        await preview_scroll.mount_all(widgets or [Markdown("")])
        self._preview_anchors = anchors

    def action_submit(self) -> None:
        text = self.query_one("#editor-textarea", TextArea).text
        self.dismiss(text)

    def action_cancel(self) -> None:
        self.dismiss(None)
