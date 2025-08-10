from typing import List, Dict
from PyQt5.QtCore import QObject, pyqtSignal
from .io import copy_with_progress, copy_batch


class CopyWorker(QObject):
    progress = pyqtSignal(int, int)  # copied, total
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, src, dst, preserve_mode=True, calc_hash=False):
        super().__init__()
        self.src = src
        self.dst = dst
        self.preserve_mode = preserve_mode
        self.calc_hash = calc_hash
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            def cb(copied, total):
                if self._cancel:
                    raise RuntimeError("Cancelled")
                self.progress.emit(copied, total)
            result = copy_with_progress(self.src, self.dst, self.preserve_mode, self.calc_hash, cb)
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class BatchCopyWorker(QObject):
    # Aggregate progress and per-file notifications
    progress = pyqtSignal(int, int, int, str)  # agg_copied, agg_total, index, basename
    file_done = pyqtSignal(int, dict)          # index, result
    done = pyqtSignal(dict)                    # summary
    failed = pyqtSignal(str)

    def __init__(self, items: List[Dict[str, str]], preserve_mode=True, calc_hash=False):
        super().__init__()
        self.items = items
        self.preserve_mode = preserve_mode
        self.calc_hash = calc_hash
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            def pcb(agg_copied, agg_total, idx, name):
                if self._cancel:
                    raise RuntimeError("Cancelled")
                self.progress.emit(agg_copied, agg_total, idx, name)

            def fdb(idx, result):
                self.file_done.emit(idx, result)

            summary = copy_batch(self.items, self.preserve_mode, self.calc_hash, pcb, fdb)
            self.done.emit(summary)
        except Exception as e:
            self.failed.emit(str(e))
