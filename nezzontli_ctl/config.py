"""Rutas del repo del sitio (nezzontli.xyz) y preferencias de usuario.

nezzontli-ctl es una herramienta aparte que opera sobre OTRO repo (el del
sitio, normalmente ~/projects/website) — no vive adentro de él, así que la
ruta no se puede derivar de la ubicación de este archivo. Se configura vía
NEZZONTLI_REPO_PATH o queda en ~/.config/nezzontli-ctl/config.json.
"""

import json
import os
from pathlib import Path

PREFS_DIR = Path.home() / ".config" / "nezzontli-ctl"
PREFS_FILE = PREFS_DIR / "config.json"

DEFAULT_PREFS = {
    "cowsay_char": "cow",
    "repo_path": str(Path.home() / "projects" / "website"),
}


def load_prefs():
    if not PREFS_FILE.is_file():
        return dict(DEFAULT_PREFS)
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_PREFS)
    prefs = dict(DEFAULT_PREFS)
    prefs.update(data)
    return prefs


def save_prefs(prefs):
    PREFS_DIR.mkdir(parents=True, exist_ok=True)
    PREFS_FILE.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


def get_repo_root():
    env_path = os.environ.get("NEZZONTLI_REPO_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path(load_prefs()["repo_path"]).expanduser().resolve()


REPO_ROOT = get_repo_root()
BLOG_DIR = REPO_ROOT / "content" / "blog"
PHOTOS_DIR = REPO_ROOT / "content" / "photos"
IMAGES_DIR = REPO_ROOT / "static" / "images"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG", ".gif", ".GIF"}
