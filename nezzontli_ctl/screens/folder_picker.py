from pathlib import Path

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Static


class FolderPickerScreen(ModalScreen[Path]):
    """Navegador de carpetas. Enter sobre una carpeta la selecciona.
    Devuelve el Path elegido, o None si se cancela (escape)."""

    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, start_path: Path | None = None):
        super().__init__()
        self._start_path = start_path or Path.home()

    def compose(self):
        with Vertical(classes="form-container"):
            yield Static(" Elegí la carpeta con las fotos — Enter para confirmar, Esc para cancelar")
            yield DirectoryTree(str(self._start_path), id="folder-tree")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.dismiss(event.path)

    def action_cancel(self) -> None:
        self.dismiss(None)
