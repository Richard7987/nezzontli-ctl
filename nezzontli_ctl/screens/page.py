from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, SelectionList, Static

from nezzontli_ctl import content
from nezzontli_ctl.config import BLOG_DIR
from nezzontli_ctl.screens.confirm import ConfirmPushScreen
from nezzontli_ctl.screens.editor import EditorScreen
from nezzontli_ctl.screens.success import SuccessScreen


def _list_projects():
    if not BLOG_DIR.is_dir():
        return []
    return sorted(
        p.name for p in BLOG_DIR.iterdir() if p.is_dir() and (p / "index.md").is_file()
    )


class NewPageScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Volver")]

    _slug_touched = False

    def compose(self):
        projects = _list_projects()
        with Vertical(classes="form-container"):
            yield Label("Nueva página en un proyecto existente", classes="form-label")
            yield Static("", id="page-error")
            yield Label("Proyecto")
            yield Select(
                [(p, p) for p in projects], id="project-select", allow_blank=True, prompt="Elegí un proyecto"
            )
            yield Label("Título")
            yield Input(id="title-input")
            yield Label("Slug (nombre de archivo)")
            yield Input(id="slug-input")
            yield Label("Descripción")
            yield Input(id="description-input")
            yield Label("Tags (separados por coma)")
            yield Input(id="tags-input")
            yield Label("Páginas relacionadas (opcional)", id="related-label")
            yield SelectionList(id="related-list")
            yield Button("Continuar →", id="continue-button", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#related-label").display = False
        self.query_one("#related-list").display = False

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
            self.query_one("#slug-input", Input).value = content.slugify(event.value)
        elif event.input.id == "slug-input":
            self._slug_touched = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-button":
            self.run_worker(self._continue(), exclusive=True)

    async def _continue(self) -> None:
        error = self.query_one("#page-error", Static)
        project = self.query_one("#project-select", Select).value
        title = self.query_one("#title-input", Input).value.strip()
        description = self.query_one("#description-input", Input).value.strip()
        slug = content.slugify(self.query_one("#slug-input", Input).value.strip() or title)

        if not project or project is Select.BLANK:
            error.update("[red]Elegí un proyecto.[/red]")
            return
        if not title or not description:
            error.update("[red]Título y descripción son obligatorios.[/red]")
            return
        target_file = BLOG_DIR / project / f"{slug}.md"
        if target_file.exists():
            error.update(f"[red]content/blog/{project}/{slug}.md ya existe.[/red]")
            return
        error.update("")

        tags = [t.strip() for t in self.query_one("#tags-input", Input).value.split(",") if t.strip()]
        related_list = self.query_one("#related-list", SelectionList)
        related = list(related_list.selected) if related_list.display else []

        body = await self.app.push_screen_wait(
            EditorScreen(initial_text=f"# {title}\n\n", title=f"Cuerpo de \"{title}\"")
        )
        if body is None:
            return

        frontmatter = content.build_page_frontmatter(
            title, description, tags, ["B.E. Alejandro"], related=related
        )
        target_file.write_text(frontmatter + "\n" + body, encoding="utf-8")

        pushed = await self.app.push_screen_wait(
            ConfirmPushScreen(
                [target_file],
                f'{project}: nueva página "{title}"',
                preview_markdown=f"# {title}\n\n{body}",
            )
        )
        if pushed:
            await self.app.push_screen_wait(SuccessScreen("¡Publicado!"))
            self.app.pop_screen()
