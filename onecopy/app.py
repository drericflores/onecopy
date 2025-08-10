import os
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSettings
from .main_window import MainWindow
from .utils import apply_theme

ORG = "OneCopyProject"
APP = "onecopy"


def main():
    # High-DPI friendly
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)

    # Persistent settings
    settings = QSettings(ORG, APP)
    # theme: "dark" | "light"
    theme = settings.value("ui/theme", "dark")
    apply_theme(theme)

    win = MainWindow(settings=settings)
    win.show()
    sys.exit(app.exec_())