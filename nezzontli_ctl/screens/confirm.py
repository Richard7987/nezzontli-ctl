from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown, Static

from nezzontli_ctl import git_ops


class ConfirmPushScreen(ModalScreen[bool]):
    """Hace git add de los paths, muestra el diff --stat + preview, y pide
    confirmación antes de commitear y pushear. Devuelve True si se pusheó,
    False si se canceló (los archivos quedan igual, staged, sin commitear)."""

    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, paths, commit_message: str, preview_markdown: str = ""):
        super().__init__()
        self._paths = paths
        self._commit_message = commit_message
        self._preview_markdown = preview_markdown

    def compose(self):
        with Vertical(classes="form-container"):
            yield Label("Confirmar", classes="form-label")
            yield Static("", id="confirm-diff")
            if self._preview_markdown:
                yield Markdown(self._preview_markdown, id="confirm-preview")
            yield Static("", id="confirm-error")
            with Horizontal():
                yield Button("Commitear y pushear", id="confirm-yes", variant="success")
                yield Button("Cancelar", id="confirm-no")

    def on_mount(self) -> None:
        git_ops.stage(self._paths)
        diff = git_ops.diff_stat_cached() or "(sin cambios detectados)"
        self.query_one("#confirm-diff", Static).update(diff)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            event.button.disabled = True
            self.query_one("#confirm-no", Button).disabled = True
            self.run_worker(self._do_push(), exclusive=True)
        else:
            self.action_cancel()

    async def _do_push(self) -> None:
        ok, output = git_ops.commit_and_push(self._commit_message)
        if ok:
            self.dismiss(True)
        else:
            self.query_one("#confirm-error", Static).update(f"[red]Error al pushear:[/red]\n{output}")

    def action_cancel(self) -> None:
        self.dismiss(False)
