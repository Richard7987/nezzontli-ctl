import pyfiglet
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

BANNER = pyfiglet.Figlet(font="small").renderText("nezzontli")

MENU_ITEMS = [
    ("post", "Nuevo post de blog"),
    ("page", "Nueva página en un proyecto existente"),
    ("album", "Nuevo álbum de fotos"),
    ("add-photos", "Agregar fotos a un álbum existente"),
    ("settings", "Configuración"),
    ("quit", "Salir"),
]


class MenuScreen(Screen):
    def compose(self):
        with Vertical(id="menu-container"):
            yield Static(BANNER, id="banner")
            yield Static("gestor de contenido — sin CMS", id="subtitle")
            yield OptionList(
                *[Option(label, id=key) for key, label in MENU_ITEMS],
                id="menu-options",
            )
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        key = event.option.id
        if key == "quit":
            self.app.exit()
            return
        if key == "settings":
            from nezzontli_ctl.screens.settings import SettingsScreen

            self.app.push_screen(SettingsScreen())
            return
        if key == "post":
            from nezzontli_ctl.screens.post import NewPostScreen

            self.app.push_screen(NewPostScreen())
            return
        if key == "page":
            from nezzontli_ctl.screens.page import NewPageScreen

            self.app.push_screen(NewPageScreen())
            return
        if key == "album":
            from nezzontli_ctl.screens.album import NewAlbumScreen

            self.app.push_screen(NewAlbumScreen())
            return
        if key == "add-photos":
            from nezzontli_ctl.screens.add_photos import AddPhotosScreen

            self.app.push_screen(AddPhotosScreen())
            return
