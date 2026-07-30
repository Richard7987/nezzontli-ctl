import shutil

from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from nezzontli_ctl import content
from nezzontli_ctl.config import IMAGES_DIR, PHOTOS_DIR
from nezzontli_ctl.screens.confirm import ConfirmPushScreen
from nezzontli_ctl.screens.folder_picker import FolderPickerScreen
from nezzontli_ctl.screens.success import SuccessScreen


def _list_albums():
    if not PHOTOS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in PHOTOS_DIR.iterdir() if p.is_dir() and (p / "index.md").is_file()
    )


class AddPhotosScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Volver")]

    _source_files = None

    def compose(self):
        albums = _list_albums()
        with Vertical(classes="form-container"):
            yield Label("Agregar fotos a un álbum existente", classes="form-label")
            yield Static("", id="add-error")
            yield Label("Álbum")
            yield Select([(a, a) for a in albums], id="album-select", prompt="Elegí un álbum")
            yield Label("Alt/caption para estas fotos")
            yield Input(id="alt-input")
            with Horizontal(classes="form-row"):
                yield Button("Elegir carpeta de fotos", id="pick-folder-button")
                yield Static("(ninguna carpeta elegida)", id="folder-summary")
            yield Button("Continuar →", id="continue-button", variant="primary", disabled=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pick-folder-button":
            self.run_worker(self._pick_folder(), exclusive=True)
        elif event.button.id == "continue-button":
            self.run_worker(self._continue(), exclusive=True)

    async def _pick_folder(self) -> None:
        path = await self.app.push_screen_wait(FolderPickerScreen())
        if path is None:
            return
        error = self.query_one("#add-error", Static)
        try:
            files = content.collect_images(path)
        except ValueError as e:
            error.update(f"[red]{e}[/red]")
            return
        error.update("")
        self._source_files = files
        names = ", ".join(f.name for f in files[:6])
        more = f" (+{len(files) - 6})" if len(files) > 6 else ""
        self.query_one("#folder-summary", Static).update(f"{len(files)} fotos: {names}{more}")
        self.query_one("#continue-button", Button).disabled = False

    async def _continue(self) -> None:
        error = self.query_one("#add-error", Static)
        album = self.query_one("#album-select", Select).value
        alt = self.query_one("#alt-input", Input).value.strip()

        if not album or album is Select.BLANK:
            error.update("[red]Elegí un álbum.[/red]")
            return
        if not self._source_files:
            error.update("[red]Elegí una carpeta con fotos.[/red]")
            return
        dest_dir = IMAGES_DIR / album
        content_file = PHOTOS_DIR / album / "index.md"
        existing_names = {f.name for f in dest_dir.iterdir()} if dest_dir.is_dir() else set()
        collision = [f.name for f in self._source_files if f.name in existing_names]
        if collision:
            error.update(f"[red]Ya existen con ese nombre: {', '.join(collision)}[/red]")
            return
        error.update("")

        for f in self._source_files:
            shutil.copy2(f, dest_dir / f.name)

        alt_final = alt or album
        items = [f"/images/{album}/{f.name}::{alt_final}" for f in self._source_files]
        new_gallery = "\n" + content.gallery_shortcode(items)
        original = content_file.read_text(encoding="utf-8")
        content_file.write_text(original.rstrip("\n") + "\n" + new_gallery, encoding="utf-8")

        pushed = await self.app.push_screen_wait(
            ConfirmPushScreen(
                [dest_dir, content_file],
                f"{album}: agrega {len(self._source_files)} fotos",
                preview_markdown=new_gallery,
            )
        )
        if pushed:
            await self.app.push_screen_wait(SuccessScreen("¡Fotos agregadas!"))
            self.app.pop_screen()
