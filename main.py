"""Punto de entrada de KTOmusic."""

from config.settings import ensure_directories
from src.ui.main_window import MainWindow


def main() -> None:
    ensure_directories()
    MainWindow().mainloop()


if __name__ == "__main__":
    main()
