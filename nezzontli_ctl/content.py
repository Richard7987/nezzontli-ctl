"""Lógica pura para armar TOML/Markdown de posts, páginas y álbumes.

Migrado tal cual del ctl.py anterior (probado ya en esa versión).
"""

import re
from datetime import date
from pathlib import Path

from nezzontli_ctl.config import IMAGE_EXTENSIONS


def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "sin-titulo"


def toml_str(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def toml_list(values):
    return "[" + ", ".join(toml_str(v) for v in values) + "]"


def build_post_frontmatter(title, description, tags, authors, katex=False, comments=None, dt=None):
    dt = dt or date.today()
    lines = [
        f"title = {toml_str(title)}",
        f"description = {toml_str(description)}",
        f"authors = {toml_list(authors)}",
        f"date = {dt.isoformat()}",
    ]
    if tags:
        lines.append("[taxonomies]")
        lines.append(f"tags = {toml_list(tags)}")
    if katex or comments:
        lines.append("[extra]")
        if katex:
            lines.append("katex = true")
        if comments:
            lines.append("")
            lines.append("[extra.comments]")
            lines.append(f"host = {toml_str(comments['host'])}")
            lines.append(f"user = {toml_str(comments['user'])}")
            lines.append(f"id = {toml_str(comments['id'])}")
    return "+++\n" + "\n".join(lines) + "\n+++\n"


def build_page_frontmatter(title, description, tags, authors, related=None, dt=None):
    dt = dt or date.today()
    lines = [
        'template = "article.html"',
        f"title = {toml_str(title)}",
        f"description = {toml_str(description)}",
        f"authors = {toml_list(authors)}",
        f"date = {dt.isoformat()}",
    ]
    if tags:
        lines.append("[taxonomies]")
        lines.append(f"tags = {toml_list(tags)}")
    if related:
        lines.append("[extra]")
        lines.append(f"related_pages = {toml_list(related)}")
    return "+++\n" + "\n".join(lines) + "\n+++\n"


def build_album_frontmatter(title, description, tags, cover_path, dt=None):
    dt = dt or date.today()
    lines = [
        f"title = {toml_str(title)}",
        f"date = {dt.isoformat()}",
        f"description = {toml_str(description)}",
    ]
    if tags:
        lines.append("[taxonomies]")
        lines.append(f"tags = {toml_list(tags)}")
    lines.append("[extra]")
    lines.append(f"cover_image = {toml_str(cover_path)}")
    return "+++\n" + "\n".join(lines) + "\n+++\n"


def gallery_shortcode(image_paths_with_alt):
    items = ", ".join(toml_str(p) for p in image_paths_with_alt)
    return f"{{{{ gallery(photos=[{items}]) }}}}\n"


def collect_images(source_dir):
    source = Path(source_dir).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"{source} no es un directorio.")
    files = sorted(
        p for p in source.iterdir() if p.suffix in IMAGE_EXTENSIONS and p.is_file()
    )
    if not files:
        raise ValueError(f"No se encontraron imágenes en {source}.")
    return files
