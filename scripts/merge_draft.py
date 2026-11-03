#!/usr/bin/env python3
"""Build the canonical merged script draft from segment artifacts.

script/merged-draft.json is the canonical script artifact: render_review_srt.py
reads it, audit_project.py checks the script layer against it, and identity
convergence, placement optimization, and continuity edits all apply to it.
Segment files remain the evidence layer and are never rewritten by edits.

Every merged cue records `derivation` (`segment`, `cue_id`) so the auditor can
prove the merged script resolves to real segment artifacts. Once tools or the
coordinator edit the merged draft they set `merged_edits: true`; a plain
re-run of this tool then refuses to overwrite those edits unless --force is
given, preventing obsolete labels from silently resurrecting.

  python scripts/merge_draft.py PROJECT_DIR [--force]
"""
import argparse
import json
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

DONE_STATUSES = ("analyzed", "drafted", "reviewed", "approved", "complete")

def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else None

def rows(value, key):
    return value if isinstance(value, list) else value.get(key, []) if isinstance(value, dict) else []

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("project_dir")
    p.add_argument("--force", action="store_true", help="Overwrite a merged draft that carries manual/derived edits.")
    args = p.parse_args()
    root = Path(args.project_dir).resolve()
    segments_dir = root / "segments"
    dirs = sorted(x for x in segments_dir.glob("segment-*") if x.is_dir()) if segments_dir.is_dir() else []
    if not dirs:
        raise SystemExit("No segment directories found under segments/")
    merged_path = root / "script/merged-draft.json"
    existing = load(merged_path)
    if isinstance(existing, dict) and existing.get("merged_edits") and not args.force:
        raise SystemExit("merged-draft.json carries edits (merged_edits=true); refusing to overwrite. Re-run with --force after reconciling, or apply edits through the editing tools.")
    segments, cues, observations = [], [], []
    for directory in dirs:
        manifest = load(directory / "manifest.json")
        if not isinstance(manifest, dict):
            continue
        start, end = float(manifest["start"]), float(manifest["end"])
        segments.append({"id": directory.name, "start": start, "end": end, "status": manifest.get("status")})
        for cue in rows(load(directory / "draft-cues.json"), "cues"):
            cid = str(cue.get("id", ""))
            if not cid:
                continue
            merged = dict(cue)
            merged["derivation"] = {"segment": directory.name, "cue_id": cid}
            cues.append(merged)
        observations += rows(load(directory / "observations.json"), "observations")
    cues.sort(key=lambda c: (float(c.get("start", 0)), str(c.get("id"))))
    cue_overlaps = []
    for a, b in zip(cues, cues[1:]):
        end = float(a["start"]) + float(a.get("duration") or a.get("review_duration") or 0)
        gap = float(b["start"]) - end
        if gap < -0.01:
            cue_overlaps.append({"first": a.get("id"), "second": b.get("id"), "overlap_seconds": round(-gap, 3)})
    covered = sorted((s["start"], s["end"]) for s in segments)
    union = []
    for a, b in covered:
        if union and a <= union[-1][1] + 0.5:
            union[-1][1] = max(union[-1][1], b)
        else:
            union.append([a, b])
    coverage_holes = [{"start": round(a[1], 2), "end": round(b[0], 2)} for a, b in zip(union, union[1:]) if b[0] - a[1] > 0.5]
    done_union = [s for s in segments if s["status"] in DONE_STATUSES]
    out = {"schema_version": 2,
           "coverage": {"start": union[0][0] if union else None, "end": union[-1][1] if union else None,
                        "segments": segments},
           "counts": {"observations": len(observations), "cues": len(cues)},
           "cues": cues,
           "cue_overlaps": cue_overlaps,
           "merged_edits": False}
    write(merged_path, out)
    write(root / "qc/merge-report.json", {"schema_version": 1, "cue_count": len(cues),
        "observation_count": len(observations), "coverage": out["coverage"],
        "cue_overlaps": cue_overlaps, "coverage_holes": coverage_holes,
        "unfinished_segments": [s["id"] for s in segments if s["status"] not in DONE_STATUSES]})
    print(json.dumps({"cues": len(cues), "observations": len(observations),
                      "cue_overlaps": len(cue_overlaps), "coverage_holes": len(coverage_holes),
                      "merged": str(merged_path)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
