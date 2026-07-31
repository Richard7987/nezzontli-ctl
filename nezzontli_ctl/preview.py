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

# flatlatex no reconoce estos nombres de función/operador (los deja con la
# barra literal), así que se pasan a texto plano antes de convertir.
_FUNC_NAMES = [
    "varlimsup", "varliminf", "limsup", "liminf", "sinh", "cosh", "tanh",
    "coth", "arcsin", "arccos", "arctan", "sin", "cos", "tan", "cot", "sec",
    "csc", "log", "ln", "exp", "lim", "max", "min", "det", "gcd", "sup",
    "inf", "arg", "mod", "deg", "dim", "hom", "ker",
]
_WRAPPER_MACROS = ("text", "mathrm", "textrm", "operatorname")


def _parse_kv_args(raw):
    return {m.group(1): m.group(2) for m in _KV_RE.finditer(raw)}


_CODE_FENCE_RE = re.compile(r"```[^\n]*\n.*?\n```", re.DOTALL)


def _split_plain_paragraphs(text, base_offset):
    """[(párrafo, offset_absoluto), ...] separados por 1+ líneas en blanco,
    salteando los que quedan vacíos."""
    parts = []
    cursor = 0
    for m in re.finditer(r"\n{2,}", text):
        para = text[cursor:m.start()]
        if para.strip():
            parts.append((para, base_offset + cursor))
        cursor = m.end()
    tail = text[cursor:]
    if tail.strip():
        parts.append((tail, base_offset + cursor))
    return parts


def split_paragraphs_with_offsets(chunk):
    """[(párrafo, offset_en_chunk), ...] separados por 1+ líneas en blanco,
    salteando los que quedan vacíos. Un tramo largo de texto plano (sin
    imágenes/fórmulas en el medio) se anclaba como un solo widget gigante
    para el sync del scroll — recién al llegar a la SIGUIENTE fórmula/
    imagen (si la había) se volvía a mover el preview. Sin más fórmulas
    después, se quedaba pegado ahí el resto del documento. Con un anchor
    por párrafo, el sync tiene puntos de referencia repartidos parejo en
    todo el texto, no solo donde hay imágenes/fórmulas.

    Los bloques ```código``` son un párrafo atómico, nunca se parten por
    las líneas en blanco que tengan adentro (código con espaciado entre
    funciones/comentarios, típico) — si se parten, cada pedazo reabre su
    propio widget Markdown con su propio margen y el bloque se ve hecho
    pedazos con huecos enormes en vez de un solo bloque de código."""
    parts = []
    cursor = 0
    for m in _CODE_FENCE_RE.finditer(chunk):
        parts.extend(_split_plain_paragraphs(chunk[cursor:m.start()], cursor))
        parts.append((m.group(0), m.start()))
        cursor = m.end()
    parts.extend(_split_plain_paragraphs(chunk[cursor:], cursor))
    return parts


def _strip_wrapper_macro(tex, name):
    pattern = re.compile(r"\\" + name + r"\{([^{}]*)\}")
    while pattern.search(tex):
        tex = pattern.sub(r"\1", tex)
    return tex


def _preprocess_for_flatlatex(tex):
    """flatlatex traduce símbolos/griego/sub-superíndices bastante bien,
    pero no conoce nombres de función (\\sin, \\log, ...), \\text{}/\\mathrm{}
    (los deja con la barra literal pegada), ni \\left/\\right ni \\to."""
    for name in _WRAPPER_MACROS:
        tex = _strip_wrapper_macro(tex, name)
    for name in _FUNC_NAMES:
        tex = re.sub(r"\\" + name + r"(?![a-zA-Z])", name + " ", tex)
    tex = tex.replace(r"\left", "").replace(r"\right", "")
    tex = tex.replace(r"\to", "→").replace(r"\gets", "←")
    tex = tex.replace(r"\{", "{").replace(r"\}", "}")
    return tex


_flatlatex_converter = None


def latex_to_unicode(tex):
    """Aproxima una fórmula LaTeX-ish a texto Unicode plano (griego,
    sub/superíndices, operadores) para que se pueda mostrar flotando en
    medio de una oración sin partirla en un bloque de imagen separado.
    Si no se puede convertir, devuelve la fórmula tal cual (con los \\ )."""
    global _flatlatex_converter
    if _flatlatex_converter is None:
        import flatlatex

        _flatlatex_converter = flatlatex.converter()
    try:
        return _flatlatex_converter.convert(_preprocess_for_flatlatex(tex))
    except Exception:
        return tex


def _substitute_inline_math(text):
    """Reemplaza cada $...$ inline (fuera de bloques $$...$$, que sí se
    renderizan como imagen más abajo) por su aproximación Unicode, en el
    mismo lugar del texto — así la oración sigue siendo un solo párrafo de
    Markdown en el preview en vez de partirse en texto/imagen/texto/imagen."""
    display_spans = [(m.start(), m.end()) for m in _DISPLAY_MATH_RE.finditer(text)]

    def replace(m):
        if any(s <= m.start() < e for s, e in display_spans):
            return m.group(0)
        return latex_to_unicode(m.group(1).strip())

    return _INLINE_MATH_RE.sub(replace, text)


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
    ("text", markdown, offset), ("math", tex, es_display, offset),
    ("image", ruta_o_url, alt, offset)

    Devuelve (texto_mostrado, segmentos) — el texto inline $...$ ya viene
    reemplazado por su aproximación Unicode (ver _substitute_inline_math),
    así que los offsets son relativos a ESE texto, no al original. Solo
    $$...$$ (bloque) sigue generando un segmento "math" con imagen — el
    inline nunca rompe el párrafo en pedazos.
    """
    text = _substitute_inline_math(text)

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

    matches.sort(key=lambda t: t[0])

    # El 4to campo (o 3ro para "text") es el offset de carácter donde
    # arranca el segmento en el texto devuelto — lo usa EditorScreen para
    # anclar el scroll del preview a la línea del cursor en el editor.
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

        cursor = end

    if cursor < len(text):
        segments.append(("text", text[cursor:], cursor))
    return text, segments
