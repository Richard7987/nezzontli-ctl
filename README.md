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

## Instalación (comando `ctl` global, sin `nix develop` a mano)

```bash
ln -s ~/projects/nezzontli-ctl/bin/ctl ~/.local/bin/ctl
ctl   # ya disponible en cualquier terminal
```

`bin/ctl` es un wrapper (`nix develop . --command ctl` parado en el
directorio del repo) — no un `pipx install`. La app necesita
`libstdc++.so.6` (lo pide numpy, dependencia de matplotlib para el
renderizado de LaTeX del preview), y en NixOS esa lib solo está en el
`LD_LIBRARY_PATH` que arma el `shellHook` del flake; un `pipx install`
plano no lo lleva y crashearía al primer `$...$` en el preview. El wrapper
sortea eso reusando siempre el flake real.

## Estado

Menú de dos niveles: **Crear nuevo…** (post / página en un proyecto /
álbum) y **Editar existente…** (post / página extra de un proyecto /
álbum / agregar fotos a un álbum), más Configuración. Cada flujo de
edición tiene botón "Eliminar" (confirmación simple, borra del disco y
pushea). Validado contra un clone local descartable (bare repo como
origin) para los tres borrados: se confirma qué se borra del disco, el
commit y el push al origin.

El preview del editor, además de Markdown, renderiza fórmulas en bloque
(`$$...$$`) como imagen (subset mathtext de matplotlib, fondo transparente)
y aproxima el LaTeX inline (`$...$`) a texto Unicode en el lugar (no rompe
el párrafo). Muestra imágenes referenciadas —locales del repo (`![]()`,
shortcodes `photo()`/`gallery()` de Zola) o remotas por URL (shortcode
`image()`)— usando el protocolo de gráficos de la terminal (Kitty, Sixel o
half-cell según detección; si no hay terminal real, cae a texto). El
scroll del editor y el preview están sincronizados por línea de origen.

Probado contra el repo real de nezzontli.xyz en uso diario. Queda a
decisión de Ale cuándo retirar `website/scripts/ctl.py` (el script viejo,
todavía intacto) y si integrar esta herramienta a su config de NixOS.
