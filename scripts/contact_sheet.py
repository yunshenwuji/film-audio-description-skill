#!/usr/bin/env python3
"""Build labeled contact sheets from already-extracted evidence frames so
analysis agents can navigate dense footage.

Evidence frames are never modified: labels are drawn on scaled copies inside the
sheet only, and the sheet is written outside the evidence directory. Sheets are
indexed in a companion JSON so every cell maps back to a frame timestamp.

Uses Pillow instead of FFmpeg's drawtext/tile filters because drawtext
segfaults on fontconfig-less Windows builds and `pattern_type glob` is not
available everywhere. Requires Pillow (>= 11, Python >= 3.11; Pillow 13.x is
current).

  python scripts/contact_sheet.py SEGMENT_EVIDENCE_DIR OUT_PREFIX
      [--cols 4] [--rows 4] [--cell-width 960] [--pattern 'frame-*.jpg']
"""
import argparse
import json
import re
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Pillow is required for contact sheets: pip install Pillow (>= 11)") from exc

MS_RE = re.compile(r"(\d{10})ms")

def stamp(path):
    m = MS_RE.search(path.name)
    return int(m.group(1)) / 1000.0 if m else None

def label(seconds, index):
    if seconds is None:
        return f"#{index}"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    frac = round(seconds - int(seconds), 2)
    return f"{h:02d}:{m:02d}:{s:02d}.{int(frac * 100):02d}"

def font(size):
    for candidate in ("arialbd.ttf", "arial.ttf", "segoeui.ttf"):
        p = Path("C:/Windows/Fonts") / candidate
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                continue
    return ImageFont.load_default()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("out_prefix")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--cell-width", type=int, default=960)
    ap.add_argument("--pattern", default="frame-*.jpg")
    ap.add_argument("--timestamps", help="Optional JSON file of {path, timestamp} overrides.")
    args = ap.parse_args()
    src = Path(args.source)
    frames = sorted(src.glob(args.pattern)) if src.is_dir() else sorted(Path(x).resolve() for x in src.read_text(encoding="utf-8").split())
    if not frames:
        print(f"no frames matched under {src}", file=sys.stderr)
        return 2
    override = {}
    if args.timestamps:
        for item in json.loads(Path(args.timestamps).read_text(encoding="utf-8")):
            override[Path(item["path"]).name] = float(item["timestamp"])
    per = args.cols * args.rows
    cell_h = int(args.cell_width * 1440 / 3840)
    big, small = font(max(28, args.cell_width // 26)), font(max(18, args.cell_width // 40))
    out = Path(args.out_prefix).parent
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(args.out_prefix).stem
    sheets = []
    for start in range(0, len(frames), per):
        chunk = frames[start:start + per]
        grid = Image.new("RGB", (args.cols * args.cell_width, args.rows * cell_h), (12, 12, 12))
        draw = ImageDraw.Draw(grid)
        for offset, frame in enumerate(chunk):
            try:
                im = Image.open(frame).convert("RGB")
            except OSError as exc:
                print(f"skip {frame}: {exc}", file=sys.stderr)
                continue
            im = im.resize((args.cell_width, cell_h))
            x, y = (offset % args.cols) * args.cell_width, (offset // args.cols) * cell_h
            grid.paste(im, (x, y))
            seconds = override.get(frame.name, stamp(frame))
            text = label(seconds, start + offset + 1)
            w = draw.textlength(text, font=big)
            draw.rectangle([x + 4, y + 4, x + 14 + w, y + 12 + big.size], fill=(0, 0, 0))
            draw.text((x + 9, y + 6), text, fill=(255, 220, 0), font=big)
            draw.rectangle([x, y, x + args.cell_width - 1, y + cell_h - 1], outline=(60, 60, 60))
        name = out / f"{stem}-{len(sheets) + 1:03d}.jpg"
        grid.save(name, quality=90)
        sheets.append({"path": name.as_posix(),
                       "cells": [{"cell": i + 1, "frame": chunk[i].name,
                                  "timestamp": override.get(chunk[i].name, stamp(chunk[i])), "index": start + i + 1}
                                 for i in range(len(chunk))]})
    index_path = out / f"{stem}-index.json"
    index_path.write_text(json.dumps({"sheets": sheets, "cols": args.cols, "rows": args.rows},
                                     ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sheets": len(sheets), "frames": len(frames), "index": index_path.as_posix()},
                     ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
