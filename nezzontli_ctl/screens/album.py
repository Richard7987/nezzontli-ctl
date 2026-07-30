import shutil

from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from nezzontli_ctl import content
from nezzontli_ctl.config import IMAGES_DIR, PHOTOS_DIR
from nezzontli_ctl.screens.confirm import ConfirmPushScreen
from nezzontli_ctl.screens.folder_picker import FolderPickerScreen
from nezzontli_ctl.screens.success import SuccessScreen

_slug_touched = False


class NewAlbumScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Volver")]

    _slug_touched = False
    _source_files = None

    def compose(self):
        with Vertical(classes="form-container"):
            yield Label("Nuevo álbum de fotos", classes="form-label")
            yield Static("", id="album-error")
            yield Label("Título del álbum")
            yield Input(id="title-input")
            yield Label("Slug (carpeta)")
            yield Input(id="slug-input")
            yield Label("Descripción")
            yield Input(id="description-input")
            yield Label("Tags (separados por coma)")
            yield Input(id="tags-input")
            with Horizontal(classes="form-row"):
                yield Button("Elegir carpeta de fotos", id="pick-folder-button")
                yield Static("(ninguna carpeta elegida)", id="folder-summary")
            yield Button("Continuar →", id="continue-button", variant="primary", disabled=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "title-input" and not self._slug_touched:
            self.query_one("#slug-input", Input).value = content.slugify(event.value)
        elif event.input.id == "slug-input":
            self._slug_touched = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pick-folder-button":
            self.run_worker(self._pick_folder(), exclusive=True)
        elif event.button.id == "continue-button":
            self.run_worker(self._continue(), exclusive=True)

    async def _pick_folder(self) -> None:
        path = await self.app.push_screen_wait(FolderPickerScreen())
        if path is None:
            return
        error = self.query_one("#album-error", Static)
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
        error = self.query_one("#album-error", Static)
        title = self.query_one("#title-input", Input).value.strip()
        description = self.query_one("#description-input", Input).value.strip()
        slug = content.slugify(self.query_one("#slug-input", Input).value.strip() or title)

        if not title or not description:
            error.update("[red]Título y descripción son obligatorios.[/red]")
            return
        if not self._source_files:
            error.update("[red]Elegí una carpeta con fotos.[/red]")
            return
        if (IMAGES_DIR / slug).exists() or (PHOTOS_DIR / slug).exists():
            error.update(f"[red]El álbum '{slug}' ya existe.[/red]")
            return
        error.update("")

        tags = [t.strip() for t in self.query_one("#tags-input", Input).value.split(",") if t.strip()]

        dest_dir = IMAGES_DIR / slug
        dest_dir.mkdir(parents=True)
        for f in self._source_files:
            shutil.copy2(f, dest_dir / f.name)

        items = [f"/images/{slug}/{f.name}::{slug}" for f in self._source_files]
        body = content.gallery_shortcode(items)
        frontmatter = content.build_album_frontmatter(
            title, description, tags, f"/images/{slug}/{self._source_files[0].name}"
        )
        content_dir = PHOTOS_DIR / slug
        content_dir.mkdir(parents=True)
        (content_dir / "index.md").write_text(
            frontmatter + f"\n# {title}\n\n" + body, encoding="utf-8"
        )

        pushed = await self.app.push_screen_wait(
            ConfirmPushScreen(
                [dest_dir, content_dir],
                f"Álbum nuevo: {title}",
                preview_markdown=f"# {title}\n\n{len(self._source_files)} fotos: {body}",
            )
        )
        if pushed:
            await self.app.push_screen_wait(SuccessScreen("¡Álbum publicado!"))
            self.app.pop_screen()
