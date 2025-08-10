import os
import shutil
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QFile, QTextStream


APP_ID = "xyz.onecopy"  # Used by .desktop and polkit policy


def path_writable(target_path: str) -> bool:
    """Return True if the directory containing target_path is writable for the current user."""
    p = Path(target_path)
    base = p if p.is_dir() else p.parent
    try:
        testfile = base / ".onecopy_write_test"
        with open(testfile, "w") as f:
            f.write("ok")
        testfile.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def needs_elevation(dest_path: str) -> bool:
    return not path_writable(dest_path)


def run_with_pkexec(args):
    """Run the provided argument vector with pkexec.
    Raises subprocess.CalledProcessError if the command fails.
    """
    cmd = ["pkexec"] + args
    return subprocess.run(cmd, check=True)


def load_qss(resource_path: str) -> str:
    f = QFile(resource_path)
    if not f.exists():
        return ""
    f.open(QFile.ReadOnly | QFile.Text)
    ts = QTextStream(f)
    qss = ts.readAll()
    f.close()
    return qss


def apply_theme(theme: str):
    app = QApplication.instance()
    if not app:
        return
    # qss files live in the installed package; use pkg resources path
    base = Path(__file__).parent / "qss"
    if theme == "dark":
        qss = load_qss(str(base / "dark.qss"))
    else:
        qss = load_qss(str(base / "light.qss"))
    app.setStyleSheet(qss)