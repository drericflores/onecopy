"""
Helper invoked via pkexec to perform elevated copies.
Supports:
- Single file copy (legacy):  onecopy.elevated_copy SRC DST [--preserve-mode] [--hash]
- Batch via manifest on stdin:  onecopy.elevated_copy --manifest [--preserve-mode] [--hash]  < manifest.json
  where manifest = {"items":[{"src": "...", "dst":"..."}], "preserve_mode": bool?, "calc_hash": bool?}
Prints a JSON summary to stdout.
"""
import argparse
import json
import sys
from typing import List, Dict

from .io import copy_with_progress, copy_batch


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src", nargs="?")
    p.add_argument("dst", nargs="?")
    p.add_argument("--preserve-mode", action="store_true")
    p.add_argument("--hash", dest="calc_hash", action="store_true")
    p.add_argument("--manifest", action="store_true", help="Read batch copy manifest from stdin (JSON)")
    args = p.parse_args()

    preserve = args.preserve_mode
    calc_hash = args.calc_hash

    if args.manifest:
        data = json.load(sys.stdin)
        items: List[Dict[str, str]] = data.get("items", [])
        if "preserve_mode" in data:
            preserve = bool(data["preserve_mode"])
        if "calc_hash" in data:
            calc_hash = bool(data["calc_hash"])
        summary = copy_batch(items, preserve_mode=preserve, calc_hash=calc_hash)
        print(json.dumps({"ok": True, "summary": summary}))
        return

    if not args.src or not args.dst:
        print(json.dumps({"ok": False, "error": "missing SRC/DST or --manifest"}))
        sys.exit(2)

    result = copy_with_progress(args.src, args.dst, preserve_mode=preserve, calc_hash=calc_hash)
    print(json.dumps({"ok": True, "result": result}))


if __name__ == "__main__":
    main()
