import cowsay
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, OptionList
from textual.widgets.option_list import Option

from nezzontli_ctl.config import load_prefs, save_prefs


class SettingsScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Volver")]

    def compose(self):
        prefs = load_prefs()
        with Vertical(classes="form-container"):
            yield Label("Configuración", classes="form-label")
            yield Label("Animal de cowsay para el mensaje de éxito:")
            option_list = OptionList(
                *[Option(name, id=name) for name in cowsay.char_names],
                id="cowsay-picker",
            )
            yield option_list
            yield Label("Carpeta del repo del sitio:")
            yield Input(value=prefs["repo_path"], id="repo-path-input")
        yield Footer()

    def on_mount(self) -> None:
        prefs = load_prefs()
        option_list = self.query_one("#cowsay-picker", OptionList)
        try:
            index = cowsay.char_names.index(prefs["cowsay_char"])
            option_list.highlighted = index
        except ValueError:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        prefs = load_prefs()
        prefs["cowsay_char"] = event.option.id
        save_prefs(prefs)
        self.notify(f"Animal elegido: {event.option.id}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "repo-path-input":
            prefs = load_prefs()
            prefs["repo_path"] = event.value
            save_prefs(prefs)
            self.notify("Ruta del repo guardada (efectiva en el próximo inicio).")
