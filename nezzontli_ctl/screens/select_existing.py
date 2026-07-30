from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


class SelectExistingScreen(ModalScreen):
    """Lista genérica de (label, valor) para elegir uno. Devuelve el valor
    elegido (lo que sea — un Path, un string) o None si se cancela."""

    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, items, title="Elegí uno"):
        super().__init__()
        self._items = list(items)
        self._title = title

    def compose(self):
        with Vertical(classes="form-container"):
            yield Static(f" {self._title}")
            yield OptionList(
                *[Option(label, id=str(i)) for i, (label, _value) in enumerate(self._items)]
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = int(event.option.id)
        self.dismiss(self._items[index][1])

    def action_cancel(self) -> None:
        self.dismiss(None)
