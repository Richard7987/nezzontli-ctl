import asyncio

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Offset
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
        text_area.cursor_location = (0, 0)
        self.watch(text_area, "scroll_y", self._sync_preview_scroll)
        self.run_worker(
            self._rebuild_preview(self._initial_text), exclusive=True, group="preview"
        )

    def _sync_preview_scroll(self, old_value: float, new_value: float) -> None:
        """scroll_y de TextArea está en FILAS VISUALES, no en líneas lógicas
        del documento — con soft_wrap (el default) una sola línea larga de
        un párrafo ocupa varias filas visuales. Usar scroll_y directo como
        "línea" (como se hacía antes) se desalinea cada vez más a medida
        que el documento tiene párrafos largos arriba. wrapped_document
        traduce la fila visual de vuelta a la línea lógica real, que es la
        misma unidad en la que se calcularon los anchors."""
        if not self._preview_anchors:
            return
        text_area = self.query_one("#editor-textarea", TextArea)
        top_row = round(new_value)
        top_line, _column = text_area.wrapped_document.offset_to_location(
            Offset(0, top_row)
        )
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

    async def _render_segment(self, segment, display_text: str) -> list:
        """Renderiza un segmento a [(widget, línea_o_None), ...]. `None`
        para widgets que no deben ser su propio punto de anclaje del sync
        (ej. la caption debajo de una imagen). Corre en paralelo para todos
        los segmentos vía asyncio.gather (cada render_math/resolve_image
        pesado va a un hilo aparte, así una fórmula lenta no bloquea a las
        demás ni a la UI)."""
        kind = segment[0]

        if kind == "text":
            _, chunk, start = segment
            entries = []
            for para, offset_in_chunk in preview_mod.split_paragraphs_with_offsets(chunk):
                line = display_text.count("\n", 0, start + offset_in_chunk)
                entries.append((Markdown(para), line))
            return entries

        if kind == "math":
            _, tex, is_display, start = segment
            line = display_text.count("\n", 0, start)
            png_path = await asyncio.to_thread(preview_mod.render_math, tex, is_display)
            if png_path is not None and AutoImage is not None:
                return [(AutoImage(str(png_path), classes="preview-math"), line)]
            return [(Static(f"$$ {tex} $$", classes="preview-fallback"), line)]

        if kind == "image":
            _, ref, alt, start = segment
            line = display_text.count("\n", 0, start)
            img_path = await asyncio.to_thread(preview_mod.resolve_image, ref)
            if img_path is not None and AutoImage is not None:
                entries = [(AutoImage(str(img_path), classes="preview-image"), line)]
            else:
                entries = [(Static(f"[img no encontrada: {ref}]", classes="preview-fallback"), line)]
            if alt:
                entries.append((Static(alt, classes="preview-caption"), None))
            return entries

        return []

    async def _rebuild_preview(self, text: str) -> None:
        """Tokeniza `text` y remonta el preview como una mezcla de widgets
        Markdown (texto normal, con el LaTeX inline ya aproximado a Unicode
        en el lugar, un widget por párrafo) e Image (fórmulas en bloque
        $$...$$ renderizadas a PNG, imágenes locales del repo o remotas por
        URL)."""
        preview_scroll = self.query_one("#editor-preview-scroll", VerticalScroll)
        display_text, segments = await asyncio.to_thread(preview_mod.tokenize, text)

        if any(segment[0] in ("math", "image") for segment in segments):
            await preview_scroll.remove_children()
            await preview_scroll.mount(
                Static("⏳ Renderizando fórmulas e imágenes…", classes="preview-loading")
            )

        rendered_groups = await asyncio.gather(
            *(self._render_segment(segment, display_text) for segment in segments)
        )

        widgets = []
        anchors = []
        last_anchored_line = None
        for group in rendered_groups:
            for widget, line in group:
                widgets.append(widget)
                # Un anchor por línea de origen distinta, apuntando al
                # PRIMER widget que aparece ahí (ej. la imagen, no su
                # caption debajo; o la primera foto de una gallery con 20
                # fotos en la misma línea) — anclar cada widget hacía que
                # el scroll saltara al ÚLTIMO en vez de al primero.
                if line is not None and line != last_anchored_line:
                    anchors.append((line, widget))
                    last_anchored_line = line

        await preview_scroll.remove_children()
        await preview_scroll.mount_all(widgets or [Markdown("")])
        self._preview_anchors = anchors

    def action_submit(self) -> None:
        text = self.query_one("#editor-textarea", TextArea).text
        self.dismiss(text)

    def action_cancel(self) -> None:
        self.dismiss(None)
