from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, SelectionList, Static

from nezzontli_ctl import content, git_ops
from nezzontli_ctl.config import BLOG_DIR
from nezzontli_ctl.screens.confirm import ConfirmPushScreen
from nezzontli_ctl.screens.confirm_delete import ConfirmDeleteScreen
from nezzontli_ctl.screens.editor import EditorScreen
from nezzontli_ctl.screens.success import SuccessScreen


def _list_projects():
    if not BLOG_DIR.is_dir():
        return []
    return sorted(
        p.name for p in BLOG_DIR.iterdir() if p.is_dir() and (p / "index.md").is_file()
    )


def list_extra_pages():
    """(label, Path) de cada content/blog/<proyecto>/<slug>.md que NO es
    index.md — las páginas extra de un proyecto (ramas, capítulos, etc.),
    para el picker de edición."""
    if not BLOG_DIR.is_dir():
        return []
    items = []
    for project_dir in sorted(BLOG_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        for page_file in sorted(project_dir.glob("*.md")):
            if page_file.stem == "index":
                continue
            try:
                data, _ = content.parse_frontmatter(page_file.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            title = data.get("title", page_file.stem)
            items.append((f"{title}  ({project_dir.name}/{page_file.name})", page_file))
    return items


class NewPageScreen(Screen):
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
        projects = _list_projects()
        with Vertical(classes="form-container"):
            yield Label(
                "Editar página" if editing else "Nueva página en un proyecto existente",
                classes="form-label",
            )
            yield Static("", id="page-error")
            if editing:
                yield Label("Proyecto")
                yield Static(self._existing_file.parent.name, id="project-static")
            else:
                yield Label("Proyecto")
                yield Select(
                    [(p, p) for p in projects],
                    id="project-select",
                    allow_blank=True,
                    prompt="Elegí un proyecto",
                )
            yield Label("Título")
            yield Input(id="title-input")
            if not editing:
                yield Label("Slug (nombre de archivo)")
                yield Input(id="slug-input")
            yield Label("Descripción")
            yield Input(id="description-input")
            yield Label("Tags (separados por coma)")
            yield Input(id="tags-input")
            yield Label("Páginas relacionadas (opcional)", id="related-label")
            yield SelectionList(id="related-list")
            with Horizontal(classes="form-row"):
                yield Button(
                    "Guardar cambios →" if editing else "Continuar →",
                    id="continue-button",
                    variant="primary",
                )
                if editing:
                    yield Button("Eliminar", id="delete-button", variant="error")

    def on_mount(self) -> None:
        related_list = self.query_one("#related-list", SelectionList)
        if self._existing_file is None:
            self.query_one("#related-label").display = False
            related_list.display = False
            return

        data, body = content.parse_frontmatter(
            self._existing_file.read_text(encoding="utf-8")
        )
        self._existing_body = body
        self._existing_date = data.get("date")
        self.query_one("#title-input", Input).value = data.get("title", "")
        self.query_one("#description-input", Input).value = data.get("description", "")
        tags = data.get("taxonomies", {}).get("tags", [])
        self.query_one("#tags-input", Input).value = ", ".join(tags)
        self._slug_touched = True  # no aplica al editar, no hay campo de slug

        related_saved = data.get("extra", {}).get("related_pages", [])
        siblings = sorted(
            p.stem
            for p in self._existing_file.parent.glob("*.md")
            if p.stem not in ("index", self._existing_file.stem)
        )
        if siblings:
            for name in siblings:
                related_list.add_option((name, name))
            for name in related_saved:
                if name in siblings:
                    related_list.select(name)
            self.query_one("#related-label").display = True
            related_list.display = True
        else:
            self.query_one("#related-label").display = False
            related_list.display = False

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "project-select":
            return
        project = event.value
        related_list = self.query_one("#related-list", SelectionList)
        related_list.clear_options()
        if project and project is not Select.BLANK:
            project_dir = BLOG_DIR / project
            siblings = sorted(
                p.stem for p in project_dir.glob("*.md") if p.stem != "index"
            )
            if siblings:
                for name in siblings:
                    related_list.add_option((name, name))
                self.query_one("#related-label").display = True
                related_list.display = True
                return
        self.query_one("#related-label").display = False
        related_list.display = False

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "title-input" and not self._slug_touched:
            self._last_auto_slug = content.slugify(event.value)
            self.query_one("#slug-input", Input).value = self._last_auto_slug
        elif event.input.id == "slug-input" and event.value != self._last_auto_slug:
            self._slug_touched = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-button":
            self.run_worker(self._continue(), exclusive=True)
        elif event.button.id == "delete-button":
            self.run_worker(self._delete(), exclusive=True)

    async def _delete(self) -> None:
        project = self._existing_file.parent.name
        title = self.query_one("#title-input", Input).value.strip() or self._existing_file.stem
        confirmed = await self.app.push_screen_wait(
            ConfirmDeleteScreen(f'la página "{title}" ({project}/{self._existing_file.name})')
        )
        if not confirmed:
            return
        self._existing_file.unlink()
        git_ops.stage([self._existing_file])
        ok, output = git_ops.commit_and_push(f'{project}: elimina página "{title}"')
        if not ok:
            self.query_one("#page-error", Static).update(f"[red]Error al pushear:[/red]\n{output}")
            return
        await self.app.push_screen_wait(SuccessScreen("¡Eliminado!"))
        self.app.pop_screen()

    async def _continue(self) -> None:
        editing = self._existing_file is not None
        error = self.query_one("#page-error", Static)
        title = self.query_one("#title-input", Input).value.strip()
        description = self.query_one("#description-input", Input).value.strip()

        if editing:
            project = self._existing_file.parent.name
            target_file = self._existing_file
        else:
            project = self.query_one("#project-select", Select).value
            if not project or project is Select.BLANK:
                error.update("[red]Elegí un proyecto.[/red]")
                return
            slug = content.slugify(self.query_one("#slug-input", Input).value.strip() or title)
            target_file = BLOG_DIR / project / f"{slug}.md"
            if target_file.exists():
                error.update(f"[red]content/blog/{project}/{slug}.md ya existe.[/red]")
                return
        if not title or not description:
            error.update("[red]Título y descripción son obligatorios.[/red]")
            return
        error.update("")

        tags = [t.strip() for t in self.query_one("#tags-input", Input).value.split(",") if t.strip()]
        related_list = self.query_one("#related-list", SelectionList)
        related = list(related_list.selected) if related_list.display else []

        initial_body = self._existing_body if editing else f"# {title}\n\n"
        body = await self.app.push_screen_wait(
            EditorScreen(initial_text=initial_body, title=f"Cuerpo de \"{title}\"")
        )
        if body is None:
            return

        frontmatter = content.build_page_frontmatter(
            title, description, tags, ["B.E. Alejandro"],
            related=related, dt=self._existing_date,
        )
        target_file.write_text(frontmatter + "\n" + body, encoding="utf-8")

        message = f'{project}: actualiza "{title}"' if editing else f'{project}: nueva página "{title}"'
        pushed = await self.app.push_screen_wait(
            ConfirmPushScreen(
                [target_file],
                message,
                preview_markdown=f"# {title}\n\n{body}",
            )
        )
        if pushed:
            await self.app.push_screen_wait(
                SuccessScreen("¡Actualizado!" if editing else "¡Publicado!")
            )
            self.app.pop_screen()
