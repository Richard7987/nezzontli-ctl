import threading

from textual.app import App

from nezzontli_ctl.theme import GRUVBOX

# textual_image detecta el protocolo de imágenes del terminal (Kitty TGP /
# Sixel / half-cell) mandando escape sequences y esperando la respuesta —
# eso solo funciona ANTES de que Textual ponga la terminal en raw mode +
# alt screen. Si se importa recién al abrir el editor (como pasaba antes,
# import lazy adentro de screens/editor.py), la detección ya no puede leer
# la respuesta, falla, y cae al renderer de half-cell (pixelado y lento por
# los timeouts de esas queries fallidas).
try:
    import textual_image.widget  # noqa: F401
except ImportError:
    pass


def _warm_up_matplotlib() -> None:
    """El import de matplotlib.mathtext tarda ~1-2s la primera vez — lo
    calentamos en un hilo aparte apenas arranca la app para que el primer
    $...$ que se escriba en el editor no se sienta lento."""
    try:
        import matplotlib.mathtext  # noqa: F401
    except ImportError:
        pass


threading.Thread(target=_warm_up_matplotlib, daemon=True).start()


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
