"""Preview enriquecido para EditorScreen: parte el Markdown/Zola en
segmentos (texto, fórmulas LaTeX, imágenes locales o remotas) para poder
mezclar widgets Markdown + Image en la pantalla de edición.

Nada de esto lo usa el build real del sitio (Zola) — es solo para que la
TUI muestre una aproximación visual de lo que va a salir.
"""

import hashlib
import re
import urllib.request
from pathlib import Path

from nezzontli_ctl.config import REPO_ROOT

CACHE_DIR = Path.home() / ".cache" / "nezzontli-ctl" / "preview"

_DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_GALLERY_RE = re.compile(r"\{\{\s*gallery\(photos\s*=\s*\[(.*?)\]\s*\)\s*\}\}", re.DOTALL)
_PHOTO_RE = re.compile(r"\{\{\s*photo\(([^)]*)\)\s*\}\}")
_IMAGE_SHORTCODE_RE = re.compile(r"\{\{\s*image\(([^)]*)\)\s*\}\}")
_QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_KV_RE = re.compile(r'(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"')


def _parse_kv_args(raw):
    return {m.group(1): m.group(2) for m in _KV_RE.finditer(raw)}


def _resolve_local_image(path_str):
    """'/images/x/y.jpg' o 'images/x/y.jpg' -> Path bajo REPO_ROOT/static,
    o None si el archivo no existe."""
    candidate = REPO_ROOT / "static" / path_str.lstrip("/")
    return candidate if candidate.is_file() else None


def _cache_path_for_url(url, prefix="remote"):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    suffix = Path(url.split("?")[0]).suffix or ".img"
    return CACHE_DIR / f"{prefix}-{digest}{suffix}"


def _fetch_remote_image(url, timeout=5):
    cached = _cache_path_for_url(url)
    if cached.is_file():
        return cached
    # Sin User-Agent, varios hosts (ej. Wikimedia) devuelven 403.
    req = urllib.request.Request(url, headers={"User-Agent": "nezzontli-ctl-preview/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = resp.read()
    except Exception:
        return None
    cached.write_bytes(data)
    return cached


def resolve_image(path_or_url):
    """Devuelve un Path local a la imagen (descargándola a caché si es
    remota) o None si no se pudo resolver."""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return _fetch_remote_image(path_or_url)
    return _resolve_local_image(path_or_url)


def render_math(tex, display=False):
    """Renderiza una fórmula LaTeX-ish (sintaxis mathtext de matplotlib,
    subconjunto de LaTeX) a PNG con fondo transparente, cacheado por
    contenido. Devuelve el Path del PNG o None si no se pudo parsear.

    No se usa matplotlib.mathtext.math_to_image() porque no expone
    transparent=True — sin eso, savefig() pinta un fondo blanco sólido que
    se ve como un cartel pegado en medio del preview oscuro. Se reimplementa
    su mismo procedimiento (parser + Figure.text + savefig) nada más que
    con el fondo transparente.
    """
    from matplotlib.figure import Figure
    from matplotlib.mathtext import MathTextParser

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # "v2" invalida el caché de renders viejos con fondo blanco.
    key = f"v2:{'display' if display else 'inline'}:{tex}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    cached = CACHE_DIR / f"math-{digest}.png"
    if cached.is_file():
        return cached

    dpi = 200 if display else 150
    formula = f"${tex}$"
    try:
        parser = MathTextParser("path")
        width, height, depth, _, _ = parser.parse(formula, dpi=72)
        fig = Figure(figsize=(width / 72.0, height / 72.0))
        fig.text(0, depth / height, formula, color="#ebdbb2")
        fig.savefig(str(cached), dpi=dpi, format="png", transparent=True)
    except Exception:
        return None
    return cached


def tokenize(text):
    """Parte `text` en segmentos ordenados:
    ("text", markdown), ("math", tex, es_display), ("image", ruta_o_url, alt)
    """
    matches = []
    for m in _GALLERY_RE.finditer(text):
        matches.append((m.start(), m.end(), "gallery", m))
    for m in _PHOTO_RE.finditer(text):
        matches.append((m.start(), m.end(), "photo", m))
    for m in _IMAGE_SHORTCODE_RE.finditer(text):
        matches.append((m.start(), m.end(), "image_shortcode", m))
    for m in _MD_IMAGE_RE.finditer(text):
        matches.append((m.start(), m.end(), "md_image", m))
    for m in _DISPLAY_MATH_RE.finditer(text):
        matches.append((m.start(), m.end(), "display_math", m))

    display_spans = [(s, e) for s, e, k, _ in matches if k == "display_math"]
    for m in _INLINE_MATH_RE.finditer(text):
        if any(s <= m.start() < e for s, e in display_spans):
            continue
        matches.append((m.start(), m.end(), "inline_math", m))

    matches.sort(key=lambda t: t[0])

    # El 4to campo (o 3ro para "text") es el offset de carácter donde
    # arranca el segmento en `text` — lo usa EditorScreen para anclar el
    # scroll del preview a la línea del cursor en el editor.
    segments = []
    cursor = 0
    for start, end, kind, m in matches:
        if start < cursor:
            continue
        if start > cursor:
            segments.append(("text", text[cursor:start], cursor))

        if kind == "gallery":
            for qm in _QUOTED_RE.finditer(m.group(1)):
                path, _, alt = qm.group(1).partition("::")
                segments.append(("image", path, alt, start))
        elif kind == "photo":
            kv = _parse_kv_args(m.group(1))
            if "path" in kv:
                segments.append(("image", kv["path"], kv.get("alt", ""), start))
        elif kind == "image_shortcode":
            kv = _parse_kv_args(m.group(1))
            if "url" in kv:
                segments.append(("image", kv["url"], kv.get("alt", ""), start))
        elif kind == "md_image":
            segments.append(("image", m.group(2), m.group(1), start))
        elif kind == "display_math":
            segments.append(("math", m.group(1).strip(), True, start))
        elif kind == "inline_math":
            segments.append(("math", m.group(1).strip(), False, start))

        cursor = end

    if cursor < len(text):
        segments.append(("text", text[cursor:], cursor))
    return segments
