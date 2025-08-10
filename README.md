
---

## Documentation

### `README.md`
```md
# onecopy

**onecopy** is a minimal, reliable file copy GUI for Linux (PyQt5). It supports:

- File I/O with progress and SHA-256 verification (optional)
- Overwrite policy
- Preserve file mode
- Dark/Light modes (persistent)
- Status bar feedback
- Keyboard shortcuts
- On-demand elevation via `pkexec` to copy into protected paths
- Packaging: Source, pip, AppImage

## Install (source)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
onecopy