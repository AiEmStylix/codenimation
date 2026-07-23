{
  description = "AI Math Animator & Manim Development Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          python3
          uv
          ffmpeg
          cairo
          pango
          glib
          fontconfig
          freetype
          texlive.combined.scheme-medium
        ];

        shellHook = ''
          # Tự động trỏ LD_LIBRARY_PATH để Python / pycairo nhận diện được thư viện C hệ thống
          export LD_LIBRARY_PATH="${
            pkgs.lib.makeLibraryPath (
              with pkgs;
              [
                cairo
                pango
                glib
                fontconfig
                freetype
              ]
            )
          }:$LD_LIBRARY_PATH"

          echo "=================================================="
          echo "✨ Đã kích hoạt môi trường Nix Flake cho Codenimation!"
          echo "👉 Chạy lệnh: uv run streamlit run app.py"
          echo "=================================================="
        '';
      };
    };
}
