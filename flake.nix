{
  description = "nezzontli-ctl — TUI (Textual) para gestionar contenido de nezzontli.xyz sin CMS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        # Deps del proyecto (textual/pyfiglet/cowsay) van por pip/pyproject.toml,
        # no por nixpkgs: cowsay no está empaquetado ahí, y mezclar deps de nix
        # con deps de pip para el mismo proyecto es frágil. Nix solo fija la
        # versión de Python.
        packages = [ pkgs.python313 ];

        shellHook = ''
          if [ ! -d .venv ]; then
            echo "Creando .venv..."
            python3 -m venv .venv
          fi
          source .venv/bin/activate
          pip install -q -e . --disable-pip-version-check
          echo "nezzontli-ctl listo. Corré 'ctl' o 'python3 -m nezzontli_ctl'."
          echo "Apunta a: ''${NEZZONTLI_REPO_PATH:-$HOME/projects/website}"
        '';
      };
    };
}
