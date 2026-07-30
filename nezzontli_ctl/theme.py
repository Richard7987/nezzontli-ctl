"""Tema Gruvbox dark — misma paleta que usa nezzontli.xyz
(sass/_variables.scss del sitio: acento #98971a / #b8bb26 en modo dark)."""

from textual.theme import Theme

GRUVBOX = Theme(
    name="gruvbox-nezzontli",
    primary="#83a598",
    secondary="#d3869b",
    accent="#b8bb26",
    warning="#fabd2f",
    error="#fb4934",
    success="#b8bb26",
    foreground="#ebdbb2",
    background="#282828",
    surface="#3c3836",
    panel="#504945",
    dark=True,
)
