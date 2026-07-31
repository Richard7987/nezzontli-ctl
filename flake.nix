{
  description = "nezzontli-ctl — TUI (Textual) para gestionar contenido de nezzontli.xyz sin CMS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      # cowsay (el paquete de Python, no el cowsay clásico de C) no está en
      # nixpkgs — el resto de las deps sí (confirmado: textual, pyfiglet,
      # matplotlib, textual-image, flatlatex), así que solo hace falta
      # empaquetar esta. Wheel puro, sin deps propias.
      cowsay-py = pkgs.python313Packages.buildPythonPackage rec {
        pname = "cowsay";
        version = "6.1";
        format = "wheel";
        src = pkgs.fetchPypi {
          inherit pname version format;
          python = "py3";
          dist = "py3";
          sha256 = "02mk8hi8ipzvz5d4a2vh192pmc2cr45bjgikfqwxarmrq5piwjr7";
        };
        doCheck = false;
      };

      nezzontli-ctl = pkgs.python313Packages.buildPythonApplication {
        pname = "nezzontli-ctl";
        version = "0.1.0";
        pyproject = true;
        src = ./.;
        build-system = [ pkgs.python313Packages.hatchling ];
        dependencies = with pkgs.python313Packages; [
          textual
          pyfiglet
          cowsay-py
          textual-image
          matplotlib
          flatlatex
        ];
        # Empaquetado así (deps de nixpkgs, no pip), numpy/matplotlib ya
        # vienen enlazados correctamente por nixpkgs — a diferencia del
        # devShell (venv + pip), acá no hace falta el fix de
        # LD_LIBRARY_PATH para libstdc++.so.6.
        doCheck = false;
        pythonImportsCheck = [ "nezzontli_ctl" ];
      };
    in
    {
      packages.${system} = {
        default = nezzontli-ctl;
        inherit nezzontli-ctl;
      };

      devShells.${system}.default = pkgs.mkShell {
        # Deps del proyecto (textual/pyfiglet/cowsay/matplotlib/textual-image)
        # van por pip/pyproject.toml, no por nixpkgs: cowsay no está
        # empaquetado ahí, y mezclar deps de nix con deps de pip para el mismo
        # proyecto es frágil. Nix solo fija la versión de Python + las libs de
        # sistema que los wheels compilados (numpy, vía matplotlib) esperan
        # encontrar en rutas estándar que en NixOS no existen.
        packages = [
          pkgs.python313
          pkgs.stdenv.cc.cc.lib  # libstdc++.so.6 — lo pide numpy al importar
          pkgs.zlib
        ];

        shellHook = ''
          if [ ! -d .venv ]; then
            echo "Creando .venv..."
            python3 -m venv .venv
          fi
          source .venv/bin/activate
          export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib pkgs.zlib ]}:$LD_LIBRARY_PATH"
          pip install -q -e . --disable-pip-version-check
          echo "nezzontli-ctl listo. Corré 'ctl' o 'python3 -m nezzontli_ctl'."
          echo "Apunta a: ''${NEZZONTLI_REPO_PATH:-$HOME/projects/website}"
        '';
      };
    };
}
