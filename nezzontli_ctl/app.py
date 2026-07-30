from textual.app import App

from nezzontli_ctl.theme import GRUVBOX


class NezzontliApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "nezzontli-ctl"

    def on_mount(self) -> None:
        self.register_theme(GRUVBOX)
        self.theme = "gruvbox-nezzontli"
        from nezzontli_ctl.screens.menu import MenuScreen

        self.push_screen(MenuScreen())


def main():
    NezzontliApp().run()


if __name__ == "__main__":
    main()
