from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Diálogo centrado que pide confirmar la eliminación una vez. True si
    se confirma, False si se cancela."""

    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, what: str):
        super().__init__()
        self._what = what

    def compose(self):
        with Vertical(id="delete-dialog"):
            yield Label("Eliminar", classes="form-label")
            yield Static(f"Se va a eliminar: {self._what}", id="delete-target")
            yield Static("¿Seguro? Esta acción no se puede deshacer.", id="delete-message")
            with Horizontal(id="delete-buttons"):
                yield Button("Sí, eliminar", id="delete-yes", variant="error")
                yield Button("Cancelar", id="delete-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "delete-yes")

    def action_cancel(self) -> None:
        self.dismiss(False)
