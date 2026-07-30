from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static, Switch

from nezzontli_ctl import content
from nezzontli_ctl.config import BLOG_DIR
from nezzontli_ctl.screens.confirm import ConfirmPushScreen
from nezzontli_ctl.screens.editor import EditorScreen
from nezzontli_ctl.screens.success import SuccessScreen


def list_posts():
    """(label, Path) de cada content/blog/<slug>/index.md, para el picker de edición."""
    if not BLOG_DIR.is_dir():
        return []
    items = []
    for project_dir in sorted(BLOG_DIR.iterdir()):
        index_file = project_dir / "index.md"
        if not index_file.is_file():
            continue
        try:
            data, _ = content.parse_frontmatter(index_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        title = data.get("title", project_dir.name)
        items.append((f"{title}  ({project_dir.name})", index_file))
    return items


class NewPostScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Volver")]

    _slug_touched = False
    _last_auto_slug = None

    def __init__(self, existing_file=None):
        super().__init__()
        self._existing_file = existing_file
        self._existing_body = ""
        self._existing_date = None

    def compose(self):
        editing = self._existing_file is not None
        with Vertical(classes="form-container"):
            yield Label(
                "Editar post" if editing else "Nuevo post de blog", classes="form-label"
            )
            yield Static("", id="post-error")
            yield Label("Título")
            yield Input(id="title-input")
            if not editing:
                yield Label("Slug (carpeta)")
                yield Input(id="slug-input")
            yield Label("Descripción")
            yield Input(id="description-input")
            yield Label("Tags (separados por coma)")
            yield Input(id="tags-input")
            with Horizontal(classes="form-row"):
                yield Label("KaTeX  ")
                yield Switch(id="katex-switch")
            with Horizontal(classes="form-row"):
                yield Label("Comentarios de Mastodon  ")
                yield Switch(id="comments-switch")
            with Vertical(id="comments-fields"):
                yield Label("Instancia (host)")
                yield Input(value="masto.es", id="comments-host")
                yield Label("Usuario (sin @)")
                yield Input(id="comments-user")
                yield Label("ID del toot")
                yield Input(id="comments-id")
            yield Button(
                "Guardar cambios →" if editing else "Continuar →",
                id="continue-button",
                variant="primary",
            )

    def on_mount(self) -> None:
        self.query_one("#comments-fields").display = False
        if self._existing_file is not None:
            data, body = content.parse_frontmatter(
                self._existing_file.read_text(encoding="utf-8")
            )
            self._existing_body = body
            self._existing_date = data.get("date")
            self.query_one("#title-input", Input).value = data.get("title", "")
            self.query_one("#description-input", Input).value = data.get("description", "")
            tags = data.get("taxonomies", {}).get("tags", [])
            self.query_one("#tags-input", Input).value = ", ".join(tags)
            extra = data.get("extra", {})
            self.query_one("#katex-switch", Switch).value = bool(extra.get("katex", False))
            comments = extra.get("comments")
            if comments:
                self.query_one("#comments-switch", Switch).value = True
                self.query_one("#comments-fields").display = True
                self.query_one("#comments-host", Input).value = comments.get("host", "masto.es")
                self.query_one("#comments-user", Input).value = comments.get("user", "")
                self.query_one("#comments-id", Input).value = comments.get("id", "")
            self._slug_touched = True  # no aplica al editar, no hay campo de slug

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "title-input" and not self._slug_touched:
            self._last_auto_slug = content.slugify(event.value)
            self.query_one("#slug-input", Input).value = self._last_auto_slug
        elif event.input.id == "slug-input" and event.value != self._last_auto_slug:
            self._slug_touched = True

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "comments-switch":
            self.query_one("#comments-fields").display = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-button":
            self.run_worker(self._continue(), exclusive=True)

    async def _continue(self) -> None:
        editing = self._existing_file is not None
        title = self.query_one("#title-input", Input).value.strip()
        description = self.query_one("#description-input", Input).value.strip()
        error = self.query_one("#post-error", Static)

        if not title or not description:
            error.update("[red]Título y descripción son obligatorios.[/red]")
            return

        if editing:
            target_file = self._existing_file
        else:
            slug = content.slugify(self.query_one("#slug-input", Input).value.strip() or title)
            target_dir = BLOG_DIR / slug
            if target_dir.exists():
                error.update(f"[red]content/blog/{slug}/ ya existe.[/red]")
                return
            target_file = target_dir / "index.md"
        error.update("")

        tags = [t.strip() for t in self.query_one("#tags-input", Input).value.split(",") if t.strip()]
        katex = self.query_one("#katex-switch", Switch).value
        comments = None
        if self.query_one("#comments-switch", Switch).value:
            comments = {
                "host": self.query_one("#comments-host", Input).value.strip(),
                "user": self.query_one("#comments-user", Input).value.strip(),
                "id": self.query_one("#comments-id", Input).value.strip(),
            }

        initial_body = self._existing_body if editing else f"# {title}\n\n"
        body = await self.app.push_screen_wait(
            EditorScreen(initial_text=initial_body, title=f"Cuerpo de \"{title}\"")
        )
        if body is None:
            return

        frontmatter = content.build_post_frontmatter(
            title, description, tags, ["B.E. Alejandro"],
            katex=katex, comments=comments, dt=self._existing_date,
        )
        if not editing:
            target_file.parent.mkdir(parents=True)
        target_file.write_text(frontmatter + "\n" + body, encoding="utf-8")

        message = f'Actualiza: "{title}"' if editing else f"Nuevo post: {title}"
        pushed = await self.app.push_screen_wait(
            ConfirmPushScreen(
                [target_file if editing else target_file.parent],
                message,
                preview_markdown=f"# {title}\n\n{body}",
            )
        )
        if pushed:
            await self.app.push_screen_wait(
                SuccessScreen("¡Actualizado!" if editing else "¡Publicado!")
            )
            self.app.pop_screen()
