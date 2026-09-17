"""Launcher for LocalTune.

Run from the project directory with:
    python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from localtune.config import APP_NAME, APP_VERSION, ensure_data_dirs
from localtune.window import MainWindow


def main() -> int:
    ensure_data_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("LocalTune")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
