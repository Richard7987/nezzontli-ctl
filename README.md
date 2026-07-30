# nezzontli-ctl

TUI (Textual) para crear/editar contenido de [nezzontli.xyz](https://nezzontli.xyz)
sin depender de un CMS externo — ninguno soporta git-lfs, que es como se
versionan las fotos de los álbumes. Esta herramienta usa git real (el mismo
`git lfs install` de siempre), así que no tiene ese problema.

Es un proyecto separado del repo del sitio: opera *sobre* `~/projects/website`
(u otra ruta, ver `NEZZONTLI_REPO_PATH` abajo), no vive adentro de él.

## Desarrollo

```bash
nix develop   # crea/activa .venv y hace pip install -e . automáticamente
ctl           # o: python3 -m nezzontli_ctl
```

`NEZZONTLI_REPO_PATH` (variable de entorno, opcional) apunta al clone del
sitio sobre el que trabaja. Default: `~/projects/website`. También se puede
fijar de forma persistente en `~/.config/nezzontli-ctl/config.json`
(`repo_path`) o cambiarla desde la pantalla de Configuración.

## Instalación (una vez validada)

```bash
cd nezzontli-ctl
pipx install -e .
ctl   # ya disponible en cualquier terminal, sin activar nada
```

## Estado

Validada de punta a punta contra un clone local descartable (no el repo
real): las 4 pantallas (post, page, album, add-photos), edición con preview
de Markdown en vivo, commit+push real, y confirmado que las fotos quedan
como punteros git-lfs reales (no blobs crudos). Pantalla de configuración
(animal de cowsay, ruta del repo) también probada. Editar entradas/álbumes
existentes también probado.

El preview del editor, además de Markdown, renderiza fórmulas LaTeX (subset
mathtext de matplotlib) como imagen y muestra las imágenes referenciadas
—locales del repo (`![]()`, shortcodes `photo()`/`gallery()` de Zola) o
remotas por URL (shortcode `image()`)— usando el protocolo de gráficos de
la terminal (requiere Kitty, iTerm2 o soporte Sixel; si no, cae a texto).

Todavía no reemplaza a `website/scripts/ctl.py` en el uso diario — eso
queda a decisión de Ale, una vez que la pruebe él mismo contra el repo real.
