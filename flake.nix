{
  description = "nix-enter — hardened per-project podman containers for AI coding agents";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }: let
    systems = [ "x86_64-linux" "aarch64-linux" ];
    forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f {
      pkgs = import nixpkgs { inherit system; };
    });
  in {
    packages = forAllSystems ({ pkgs }: {
      default = pkgs.python3Packages.buildPythonApplication {
        pname = "nix-enter";
        version = "0.2.0";
        pyproject = true;
        src = ./.;
        build-system = [ pkgs.python3Packages.setuptools ];
        nativeBuildInputs = [ pkgs.makeWrapper ];
        postFixup = ''
          wrapProgram $out/bin/nix-enter \
            --prefix PATH : ${pkgs.lib.makeBinPath [
              pkgs.podman
              pkgs.util-linux
            ]}
        '';
      };
    });

    overlays.default = final: prev: {
      nix-enter = self.packages.${final.system}.default;
    };

    devShells = forAllSystems ({ pkgs }: {
      default = pkgs.mkShell {
        packages = with pkgs; [
          python3
          python3Packages.pytest
          podman
          util-linux
        ];
        env.PYTHONPATH = "src";
      };
    });
  };
}
