"""Application entry point for the PySide6 GUI."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def run() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Voice Writing Robot")

    # Load QSS stylesheet
    qss_path = Path(__file__).parent / "styles" / "style.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    window = MainWindow()
    window.show()

    # Show current model info in bottom bar
    window.set_model_info("faster-whisper small")

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
