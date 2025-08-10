# Upgraded OneCopy main window with restored destination target handling.
# Supports single-file, multi-file, and folder copies with auto-creation of destination folder.

import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict

from PyQt5.QtCore import QThread, QSettings, Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QFileDialog, QLabel, QPushButton, QGridLayout, QLineEdit,
    QProgressBar, QMessageBox, QCheckBox, QStatusBar, QToolBar, QAction,
    QDialog, QVBoxLayout, QTextBrowser, QListWidget, QListWidgetItem, QHBoxLayout
)

from .workers import BatchCopyWorker
from .utils import needs_elevation, apply_theme
from .io import walk_tree


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("onecopy")
        self.resize(900, 560)

        self._build_ui()
        self._wire_actions()
        self._restore_state()

    # --- UI ---
    def _build_ui(self):
        central = QWidget(self)
        grid = QGridLayout(central)

        # Sources panel (supports multiple files and folders)
        self.sources_list = QListWidget()
        self.sources_list.setSelectionMode(self.sources_list.ExtendedSelection)
        self.sources_list.setAlternatingRowColors(True)

        src_btns = QHBoxLayout()
        self.btn_add_files = QPushButton("Add Files…")
        self.btn_add_folder = QPushButton("Add Folder…")
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_clear = QPushButton("Clear")
        src_btns.addWidget(self.btn_add_files)
        src_btns.addWidget(self.btn_add_folder)
        src_btns.addStretch(1)
        src_btns.addWidget(self.btn_remove)
        src_btns.addWidget(self.btn_clear)

        # Destination (RESTORED)
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText(
            "Destination folder (or a full file path when copying a single file to rename)"
        )
        btn_dst = QPushButton("Browse…")

        # Options
        self.chk_overwrite = QCheckBox("Overwrite if exists")
        self.chk_preserve = QCheckBox("Preserve permissions")
        self.chk_hash = QCheckBox("Verify (SHA-256)")

        # Progress + Copy
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        btn_copy = QPushButton("Copy")

        # Layout
        grid.addWidget(QLabel("Sources"), 0, 0)
        grid.addWidget(self.sources_list, 1, 0, 1, 3)
        grid.addLayout(src_btns, 2, 0, 1, 3)

        grid.addWidget(QLabel("Destination"), 3, 0)
        grid.addWidget(self.dst_edit, 3, 1)
        grid.addWidget(btn_dst, 3, 2)

        grid.addWidget(self.chk_overwrite, 4, 1)
        grid.addWidget(self.chk_preserve, 5, 1)
        grid.addWidget(self.chk_hash, 6, 1)

        grid.addWidget(btn_copy, 7, 1)
        grid.addWidget(self.progress, 8, 0, 1, 3)

        self.setCentralWidget(central)

        # Toolbar + Menus
        tb = QToolBar("Main")
        self.addToolBar(tb)

        self.act_add_files = QAction("Add Files…", self)
        self.act_add_files.setShortcut("Ctrl+O")
        self.act_add_folder = QAction("Add Folder…", self)
        self.act_add_folder.setShortcut("Ctrl+Shift+O")
        self.act_choose_dest = QAction("Choose Destination…", self)
        self.act_choose_dest.setShortcut("Ctrl+D")
        self.act_copy = QAction("Copy", self)
        self.act_copy.setShortcut("Ctrl+C")
        self.act_quit = QAction("Quit", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_dark = QAction("Dark Mode", self, checkable=True)
        self.act_dark.setShortcut("Ctrl+Shift+D")

        for a in (self.act_add_files, self.act_add_folder, self.act_copy):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.act_dark)
        tb.addSeparator()
        tb.addAction(self.act_quit)

        # Menu bar
        m_file = self.menuBar().addMenu("&File")
        m_file.addAction(self.act_add_files)
        m_file.addAction(self.act_add_folder)
        m_file.addAction(self.act_choose_dest)
        m_file.addSeparator()
        m_file.addAction(self.act_copy)
        m_file.addSeparator()
        m_file.addAction(self.act_quit)

        m_view = self.menuBar().addMenu("&View")
        m_view.addAction(self.act_dark)

        # Help menu (kept)
        self.act_about = QAction("About OneCopy", self)
        self.act_usage = QAction("How To Use", self)
        m_help = self.menuBar().addMenu("&Help")
        m_help.addAction(self.act_about)
        m_help.addAction(self.act_usage)

        # Status bar
        sb = QStatusBar()
        self.setStatusBar(sb)

        # Buttons wiring (widgets)
        self.btn_add_files.clicked.connect(self._add_files)
        self.btn_add_folder.clicked.connect(self._add_folder)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self.sources_list.clear)

        btn_dst.clicked.connect(self._browse_dst)     # RESTORED
        btn_copy.clicked.connect(self._start_copy)

    def _wire_actions(self):
        self.act_add_files.triggered.connect(self._add_files)
        self.act_add_folder.triggered.connect(self._add_folder)
        self.act_choose_dest.triggered.connect(self._browse_dst)
        self.act_copy.triggered.connect(self._start_copy)
        self.act_quit.triggered.connect(self.close)
        self.act_dark.toggled.connect(self._toggle_dark)

        # Help actions
        self.act_about.triggered.connect(self._show_about)
        self.act_usage.triggered.connect(self._show_usage)

    # --- Settings/state ---
    def _restore_state(self):
        self.chk_overwrite.setChecked(self.settings.value("copy/overwrite", True, type=bool))
        self.chk_preserve.setChecked(self.settings.value("copy/preserve", True, type=bool))
        self.chk_hash.setChecked(self.settings.value("copy/hash", False, type=bool))
        self.dst_edit.setText(self.settings.value("paths/last_dst", ""))
        theme = self.settings.value("ui/theme", "dark")
        self.act_dark.setChecked(theme == "dark")

    def _save_state(self):
        self.settings.setValue("copy/overwrite", self.chk_overwrite.isChecked())
        self.settings.setValue("copy/preserve", self.chk_preserve.isChecked())
        self.settings.setValue("copy/hash", self.chk_hash.isChecked())
        self.settings.setValue("paths/last_dst", self.dst_edit.text())
        self.settings.sync()

    # --- Help dialogs ---
    def _show_about(self):
        html = (
            "<h2 style='margin:0'>OneCopy</h2>"
            "<p style='margin:4px 0 0 0'>Version 1</p>"
            "<p style='margin:0'>August 10, 2025</p>"
            "<p style='margin:8px 0 0 0'><i>EFrad Developed Application</i></p>"
        )
        QMessageBox.information(self, "About OneCopy", html)

    def _show_usage(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("How To Use OneCopy")
        dlg.resize(720, 560)
        layout = QVBoxLayout(dlg)

        tb = QTextBrowser(dlg)
        tb.setOpenExternalLinks(True)
        tb.setReadOnly(True)
        tb.setHtml(self._usage_html())
        layout.addWidget(tb)

        dlg.setLayout(layout)
        dlg.setModal(True)
        dlg.show()
        dlg.exec_()

    def _usage_html(self) -> str:
        return """
<style>
body { font-family: sans-serif; }
code, kbd { background: #eee; padding: 2px 4px; border-radius: 4px; }
</style>
<h2>How To Use OneCopy</h2>
<ol>
  <li><b>Add sources</b><br>
      Use <i>File → Add Files…</i> (<kbd>Ctrl</kbd>+<kbd>O</kbd>) to select one or more files.<br>
      Use <i>File → Add Folder…</i> (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>O</kbd>) to add an entire directory (recursively).</li>
  <li><b>Choose destination</b><br>
      Click <i>Choose Destination…</i> (<kbd>Ctrl</kbd>+<kbd>D</kbd>) and select a folder. For a single source you may type a full path with a new filename to rename while copying.</li>
  <li><b>Options</b>:
    <ul>
      <li><b>Overwrite if exists</b>: replace existing files at the destination. If off, you’ll be prompted if conflicts are found.</li>
      <li><b>Preserve permissions</b>: copy the source file mode (chmod).</li>
      <li><b>Verify (SHA-256)</b>: after copy, compute a SHA-256 digest (destination) and show it in the status bar.</li>
    </ul>
  </li>
  <li><b>Start</b><br>
      Click <i>Copy</i> (<kbd>Ctrl</kbd>+<kbd>C</kbd>). The progress bar shows aggregate progress; the status bar shows which file is copying.</li>
</ol>
<h3>Admin (Elevated) Copies</h3>
<p>If the destination requires admin rights (e.g., <code>/usr/local/share</code>), OneCopy will request authorization using <code>pkexec</code> and perform the entire batch with elevated permissions.</p>
<h3>Shortcuts</h3>
<ul>
  <li><kbd>Ctrl</kbd>+<kbd>O</kbd> – Add Files</li>
  <li><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>O</kbd> – Add Folder</li>
  <li><kbd>Ctrl</kbd>+<kbd>D</kbd> – Choose Destination</li>
  <li><kbd>Ctrl</kbd>+<kbd>C</kbd> – Copy</li>
  <li><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>D</kbd> – Toggle Dark Mode</li>
  <li><kbd>Ctrl</kbd>+<kbd>Q</kbd> – Quit</li>
</ul>
"""

    # --- Source management ---
    def _add_files(self):
        last = self.settings.value("paths/last_src_dir", "")
        paths, _ = QFileDialog.getOpenFileNames(self, "Add files", last)
        if not paths:
            return
        for p in paths:
            self._add_source_item(p)
        self.settings.setValue("paths/last_src_dir", str(Path(paths[-1]).parent))

    def _add_folder(self):
        last = self.settings.value("paths/last_src_dir", "")
        folder = QFileDialog.getExistingDirectory(self, "Add folder (recursive)", last)
        if not folder:
            return
        self._add_source_item(folder)
        self.settings.setValue("paths/last_src_dir", folder)

    def _add_source_item(self, path: str):
        it = QListWidgetItem(path)
        if Path(path).is_dir():
            it.setText(f"[DIR] {path}")
            it.setData(Qt.UserRole, {"path": path, "is_dir": True})
        else:
            it.setData(Qt.UserRole, {"path": path, "is_dir": False})
        self.sources_list.addItem(it)

    def _remove_selected(self):
        for it in self.sources_list.selectedItems():
            row = self.sources_list.row(it)
            self.sources_list.takeItem(row)

    # --- Destination selection ---
    def _browse_dst(self):
        last = self.settings.value("paths/last_dst_dir", "")
        path = QFileDialog.getExistingDirectory(self, "Choose destination folder", last)
        if path:
            self.dst_edit.setText(path)
            self.settings.setValue("paths/last_dst_dir", path)

    def _toggle_dark(self, checked: bool):
        apply_theme("dark" if checked else "light")
        self.settings.setValue("ui/theme", "dark" if checked else "light")

    # --- Copy logic with destination creation ---
    def _start_copy(self):
        # Collect sources
        sources: List[Dict] = []
        for i in range(self.sources_list.count()):
            it = self.sources_list.item(i)
            meta = it.data(Qt.UserRole)
            if not meta:
                p = it.text().replace("[DIR] ", "")
                sources.append({"path": p, "is_dir": Path(p).is_dir()})
            else:
                sources.append({"path": meta["path"], "is_dir": bool(meta["is_dir"])})

        if not sources:
            QMessageBox.warning(self, "onecopy", "Add at least one file or folder to copy.")
            return

        dst_input = self.dst_edit.text().strip()
        if not dst_input:
            QMessageBox.warning(self, "onecopy", "Choose a destination folder (or a full file path for a single file).")
            return

        dst_p = Path(dst_input)
        single_source = (len(sources) == 1 and not sources[0]["is_dir"])

        # Build items (src/dst pairs) and ensure destination folder exists
        items: List[Dict[str, str]] = []

        if single_source:
            src = Path(sources[0]["path"])
            # Determine base dir + final dst for single file (keep rename support)
            if dst_p.exists() and dst_p.is_dir():
                base_dir = dst_p
                final_dst = base_dir / src.name
            elif dst_input.endswith(os.sep):
                base_dir = Path(dst_input)
                final_dst = base_dir / src.name
            else:
                base_dir = dst_p.parent
                final_dst = dst_p

            # Ensure base destination directory exists
            try:
                base_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "onecopy", f"Cannot create destination folder:\n{e}")
                return

            items.append({"src": str(src), "dst": str(final_dst)})

        else:
            # Multiple files and/or folders: destination MUST be a folder
            if dst_p.exists() and dst_p.is_dir():
                dest_root = dst_p
            elif dst_input.endswith(os.sep):
                dest_root = Path(dst_input)
            else:
                # Treat as folder path even if not ending with os.sep; we will create it.
                dest_root = dst_p

            # Ensure destination root exists
            try:
                dest_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "onecopy", f"Cannot create destination folder:\n{e}")
                return

            for s in sources:
                p = Path(s["path"])
                if s["is_dir"]:
                    # Preserve structure under dest_root / <top_dir_name>
                    for src_file, dst_file in walk_tree(str(p), str(dest_root / p.name)):
                        items.append({"src": src_file, "dst": dst_file})
                else:
                    items.append({"src": str(p), "dst": str(dest_root / p.name)})

        if not items:
            QMessageBox.warning(self, "onecopy", "Nothing to copy.")
            return

        # Overwrite policy
        if not self.chk_overwrite.isChecked():
            conflicts = [i for i in items if Path(i["dst"]).exists()]
            if conflicts:
                sample = "\n".join(Path(c["dst"]).as_posix() for c in conflicts[:5])
                more = "" if len(conflicts) <= 5 else f"\n… and {len(conflicts)-5} more"
                r = QMessageBox.question(
                    self,
                    "Overwrite?",
                    f"The following files already exist at the destination:\n\n{sample}{more}\n\n"
                    f"Overwrite them?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if r != QMessageBox.Yes:
                    return

        # Persist destination
        self.settings.setValue("paths/last_dst", dst_input)
        # Save a sensible dir for the dialog next time
        self.settings.setValue(
            "paths/last_dst_dir",
            str(dst_p if dst_p.is_dir() or dst_input.endswith(os.sep) else dst_p.parent)
        )

        # Determine if elevation is needed for any destination
        needs_elev = any(needs_elevation(Path(i["dst"]).as_posix()) for i in items)

        if needs_elev:
            self._run_elevated_batch(items)
            return

        # Non-elevated batch copy
        self.statusBar().showMessage("Copy in progress…")
        self.progress.setValue(0)

        self._thread = QThread(self)
        self._batch_worker = BatchCopyWorker(items, self.chk_preserve.isChecked(), self.chk_hash.isChecked())
        self._batch_worker.moveToThread(self._thread)

        self._thread.started.connect(self._batch_worker.run)
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.file_done.connect(self._on_batch_file_done)
        self._batch_worker.done.connect(self._on_batch_done)
        self._batch_worker.failed.connect(self._on_failed)
        self._batch_worker.done.connect(lambda _: self._cleanup_thread_batch())
        self._batch_worker.failed.connect(lambda _: self._cleanup_thread_batch())

        self._thread.start()

    # --- Elevated path (batch) ---
    def _run_elevated_batch(self, items: List[Dict[str, str]]):
        self.statusBar().showMessage("Destination requires elevated permissions. Requesting authorization…")
        try:
            manifest = {
                "items": items,
                "preserve_mode": self.chk_preserve.isChecked(),
                "calc_hash": self.chk_hash.isChecked(),
            }
            args = ["pkexec", "python3", "-m", "onecopy.elevated_copy", "--manifest"]
            res = subprocess.run(args, input=json.dumps(manifest), capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(res.stderr.strip() or "Elevated batch copy failed")
            out = json.loads(res.stdout or "{}")
            if not out.get("ok"):
                raise RuntimeError(out.get("error", "Elevated batch copy failed"))
            summary = out.get("summary", {})
            count = summary.get("count", len(items))
            bytes_copied = summary.get("bytes", 0)
            self.progress.setValue(100)
            self.statusBar().showMessage(
                f"Elevated copy complete. Files: {count} | Bytes: {bytes_copied}", 6000
            )
        except Exception as e:
            QMessageBox.critical(self, "onecopy", f"Elevated copy failed: {e}")
        finally:
            self._save_state()

    # --- Worker signal handlers ---
    def _on_batch_progress(self, agg_copied: int, agg_total: int, index: int, name: str):
        pct = int((agg_copied / max(1, agg_total)) * 100)
        self.progress.setValue(pct)
        self.statusBar().showMessage(f"Copying ({index+1}) {name} … {pct}%")

    def _on_batch_file_done(self, index: int, result: Dict):
        # Reserved for future per-file logging
        pass

    def _on_batch_done(self, summary: Dict):
        self.progress.setValue(100)
        msg = f"Copy complete. Files: {summary.get('count', 0)} | Bytes: {summary.get('bytes', 0)}"
        self.statusBar().showMessage(msg, 6000)
        self._save_state()

    def _on_failed(self, err: str):
        self.statusBar().clearMessage()
        self.progress.setValue(0)
        QMessageBox.critical(self, "onecopy", f"Copy failed: {err}")

    def _cleanup_thread_batch(self):
        self._thread.quit()
        self._thread.wait()
        self._batch_worker = None
        self._thread = None
