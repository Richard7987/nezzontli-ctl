import shutil

from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from nezzontli_ctl import content, git_ops
from nezzontli_ctl.config import IMAGES_DIR, PHOTOS_DIR
from nezzontli_ctl.screens.confirm import ConfirmPushScreen
from nezzontli_ctl.screens.confirm_delete import ConfirmDeleteScreen
from nezzontli_ctl.screens.editor import EditorScreen
from nezzontli_ctl.screens.success import SuccessScreen


def list_albums():
    """(label, Path) de cada content/photos/<slug>/index.md."""
    if not PHOTOS_DIR.is_dir():
        return []
    items = []
    for album_dir in sorted(PHOTOS_DIR.iterdir()):
        index_file = album_dir / "index.md"
        if not index_file.is_file():
            continue
        try:
            data, _ = content.parse_frontmatter(index_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        title = data.get("title", album_dir.name)
        items.append((f"{title}  ({album_dir.name})", index_file))
    return items


class EditAlbumScreen(Screen):
    """Edita título/descripción/tags/cuerpo de un álbum existente. Para
    agregar fotos nuevas, usar 'Agregar fotos a un álbum existente'."""

    BINDINGS = [("escape", "app.pop_screen", "Volver")]

    def __init__(self, existing_file):
        super().__init__()
        self._existing_file = existing_file
        self._existing_body = ""
        self._cover_image = None
        self._existing_date = None

    def compose(self):
        with Vertical(classes="form-container"):
            yield Label("Editar álbum", classes="form-label")
            yield Static("", id="album-error")
            yield Label("Título")
            yield Input(id="title-input")
            yield Label("Descripción")
            yield Input(id="description-input")
            yield Label("Tags (separados por coma)")
            yield Input(id="tags-input")
            yield Static(
                "Para agregar fotos, usá \"Agregar fotos a un álbum existente\" en el menú.",
                classes="form-row",
            )
            with Horizontal(classes="form-row"):
                yield Button("Guardar cambios →", id="continue-button", variant="primary")
                yield Button("Eliminar", id="delete-button", variant="error")

    def on_mount(self) -> None:
        data, body = content.parse_frontmatter(self._existing_file.read_text(encoding="utf-8"))
        self._existing_body = body
        self._cover_image = data.get("extra", {}).get("cover_image")
        self._existing_date = data.get("date")
        self.query_one("#title-input", Input).value = data.get("title", "")
        self.query_one("#description-input", Input).value = data.get("description", "")
        tags = data.get("taxonomies", {}).get("tags", [])
        self.query_one("#tags-input", Input).value = ", ".join(tags)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-button":
            self.run_worker(self._continue(), exclusive=True)
        elif event.button.id == "delete-button":
            self.run_worker(self._delete(), exclusive=True)

    async def _delete(self) -> None:
        album_dir = self._existing_file.parent
        slug = album_dir.name
        title = self.query_one("#title-input", Input).value.strip() or slug
        images_dir = IMAGES_DIR / slug
        confirmed = await self.app.push_screen_wait(
            ConfirmDeleteScreen(
                f'el álbum "{title}" (content/photos/{slug}/ y static/images/{slug}/, fotos incluidas)'
            )
        )
        if not confirmed:
            return
        shutil.rmtree(album_dir)
        paths = [album_dir]
        if images_dir.is_dir():
            shutil.rmtree(images_dir)
            paths.append(images_dir)
        git_ops.stage(paths)
        ok, output = git_ops.commit_and_push(f'Elimina álbum: "{title}"')
        if not ok:
            self.query_one("#album-error", Static).update(f"[red]Error al pushear:[/red]\n{output}")
            return
        await self.app.push_screen_wait(SuccessScreen("¡Eliminado!"))
        self.app.pop_screen()

    async def _continue(self) -> None:
        error = self.query_one("#album-error", Static)
        title = self.query_one("#title-input", Input).value.strip()
        description = self.query_one("#description-input", Input).value.strip()
        if not title or not description:
            error.update("[red]Título y descripción son obligatorios.[/red]")
            return
        error.update("")

        tags = [t.strip() for t in self.query_one("#tags-input", Input).value.split(",") if t.strip()]

        body = await self.app.push_screen_wait(
            EditorScreen(initial_text=self._existing_body, title=f'Cuerpo de "{title}"')
        )
        if body is None:
            return

        frontmatter = content.build_album_frontmatter(
            title, description, tags, self._cover_image or "", dt=self._existing_date
        )
        self._existing_file.write_text(frontmatter + "\n" + body, encoding="utf-8")

        pushed = await self.app.push_screen_wait(
            ConfirmPushScreen(
                [self._existing_file],
                f'Actualiza álbum: "{title}"',
                preview_markdown=f"# {title}\n\n{body}",
            )
        )
        if pushed:
            await self.app.push_screen_wait(SuccessScreen("¡Actualizado!"))
            self.app.pop_screen()
