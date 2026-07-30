import cowsay
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from nezzontli_ctl.config import load_prefs


class SuccessScreen(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Volver al menú"), ("enter", "close", "Volver al menú")]

    def __init__(self, message: str = "¡Publicado!"):
        super().__init__()
        self._message = message

    def compose(self):
        char = load_prefs()["cowsay_char"]
        art = cowsay.get_output_string(char, self._message)
        with Vertical(id="success-container"):
            yield Static(art, id="cowsay-output")
            yield Static("(Enter / Esc para volver al menú)")

    def action_close(self) -> None:
        self.dismiss(None)
