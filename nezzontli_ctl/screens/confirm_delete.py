from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Pide confirmar la eliminación DOS VECES (dos preguntas seguidas en el
    mismo modal) antes de devolver True. False si se cancela en cualquiera
    de las dos."""

    BINDINGS = [("escape", "cancel", "Cancelar")]

    _MESSAGES = [
        "¿Seguro que querés eliminar esto?",
        "¿Estás completamente seguro? Esta acción no se puede deshacer.",
    ]

    def __init__(self, what: str):
        super().__init__()
        self._what = what
        self._step = 0

    def compose(self):
        with Vertical(classes="form-container"):
            yield Label("Eliminar", classes="form-label")
            yield Static(f"Se va a eliminar: {self._what}", id="delete-target")
            yield Static(self._MESSAGES[0], id="delete-message")
            with Horizontal():
                yield Button("Sí, eliminar", id="delete-yes", variant="error")
                yield Button("Cancelar", id="delete-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "delete-yes":
            self.dismiss(False)
            return
        if self._step == 0:
            self._step = 1
            self.query_one("#delete-message", Static).update(self._MESSAGES[1])
            self.query_one("#delete-yes", Button).label = "Sí, eliminar definitivamente"
            return
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
