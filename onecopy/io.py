import os
import hashlib
from pathlib import Path
from typing import Callable, Iterable, List, Dict, Tuple

BUFFER = 1024 * 1024  # 1 MiB


def _hash(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            block = f.read(BUFFER)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def copy_with_progress(
    src: str,
    dst: str,
    preserve_mode: bool = True,
    calc_hash: bool = False,
    progress_cb: Callable[[int, int], None] | None = None,
) -> Dict:
    """
    Copy a single file with progress callback (bytes_copied, total_bytes).
    Ensures destination directory exists and optionally preserves mode.
    """
    src_p = Path(src)
    dst_p = Path(dst)

    total = src_p.stat().st_size
    copied = 0

    # Ensure destination directory
    dst_p.parent.mkdir(parents=True, exist_ok=True)

    with open(src_p, "rb") as fsrc, open(dst_p, "wb") as fdst:
        while True:
            buf = fsrc.read(BUFFER)
            if not buf:
                break
            fdst.write(buf)
            copied += len(buf)
            if progress_cb:
                progress_cb(copied, total)

    if preserve_mode:
        os.chmod(dst_p, src_p.stat().st_mode)

    digest = _hash(dst_p) if calc_hash else None
    return {"bytes": total, "hash": digest, "dst": str(dst_p)}


def walk_tree(src_dir: str, dest_root: str) -> List[Tuple[str, str]]:
    """
    Expand a directory copy into (src_file, dst_file) pairs, preserving structure.
    """
    src_dir_p = Path(src_dir).resolve()
    dest_root_p = Path(dest_root).resolve()
    items: List[Tuple[str, str]] = []
    for root, _, files in os.walk(src_dir_p):
        r = Path(root)
        rel = r.relative_to(src_dir_p)
        for name in files:
            s = r / name
            d = dest_root_p / rel / name
            items.append((str(s), str(d)))
    return items


def total_size_of_sources(sources: Iterable[str]) -> int:
    total = 0
    for s in sources:
        p = Path(s)
        if p.is_file():
            total += p.stat().st_size
        elif p.is_dir():
            for root, _, files in os.walk(p):
                for name in files:
                    total += (Path(root) / name).stat().st_size
    return total


def copy_batch(
    items: List[Dict[str, str]],
    preserve_mode: bool = True,
    calc_hash: bool = False,
    progress_cb: Callable[[int, int, int, str], None] | None = None,
    file_done_cb: Callable[[int, Dict], None] | None = None,
) -> Dict:
    """
    Copy a list of {src, dst} items with aggregate progress.
    progress_cb receives (aggregate_copied, aggregate_total, index, basename).
    file_done_cb receives (index, result_dict).
    Returns {"bytes": total_bytes, "count": N}
    """
    # Aggregate total size (from sources)
    total_bytes = 0
    for item in items:
        p = Path(item["src"])
        total_bytes += p.stat().st_size

    agg_copied = 0
    for idx, item in enumerate(items):
        src = item["src"]
        dst = item["dst"]

        def inner_cb(copied: int, total: int):
            if progress_cb:
                progress_cb(agg_copied + copied, total_bytes, idx, Path(src).name)

        result = copy_with_progress(src, dst, preserve_mode, calc_hash, inner_cb)
        agg_copied += Path(src).stat().st_size
        if file_done_cb:
            file_done_cb(idx, result)

    return {"bytes": total_bytes, "count": len(items)}
