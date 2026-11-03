#!/usr/bin/env python3
r"""Prepare a segment package so agents analyze instead of coding.

Segment ids must match `segment-\d+` (e.g. segment-001): prepare_segment and
finalize_segment both enforce it, and audit_project.py discovers segment
directories with the same glob.

The segment evidence directory is owned exclusively by this tool. Re-running
with --force rebuilds the package and removes orphaned frame files that the new
package no longer references; re-run finalize_segment.py afterwards so
evidence-index-proposal.json and timeline/visual-evidence.json stay consistent.

Sample timestamps are clamped below the last decodable frame (probed with
ffprobe) so extraction never seeks past the end of the stream.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

SEGMENT_ID_RE = re.compile(r"segment-\d+")

def load(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else default

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def rows(value, key):
    return value if isinstance(value, list) else value.get(key, []) if isinstance(value, dict) else []

def last_frame_pts(source):
    """Best-effort probe of the last decodable video frame timestamp."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-read_intervals", "%+#1",
                              "-show_entries", "frame=pkt_dts_time,best_effort_timestamp_time",
                              "-of", "csv=p=0", "-select_streams", "v:0", str(source)],
                             capture_output=True, text=True, encoding="utf-8", timeout=120)
        values = [float(x) for x in out.stdout.replace(",", "\n").split() if x.strip()]
        return max(values) if values else None
    except Exception:
        return None

def main():
    p = argparse.ArgumentParser(description="Create a ready-to-analyze segment package with hashed evidence frames.")
    p.add_argument("project_dir")
    p.add_argument("segment_id")
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--overlap", type=float, default=20.0)
    p.add_argument("--max-gap", type=float, default=20.0)
    p.add_argument("--timestamp", type=float, action="append", default=[])
    p.add_argument("--reuse-evidence", action="store_true", help="Package already-extracted segment evidence without invoking FFmpeg.")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    if not SEGMENT_ID_RE.fullmatch(args.segment_id):
        raise SystemExit(f"segment_id must match segment-NNN (audit_project.py only discovers segments/segment-*): {args.segment_id}")
    root = Path(args.project_dir).resolve()
    segment = root / "segments" / args.segment_id
    if args.end <= args.start:
        raise SystemExit("--end must be greater than --start")
    project = load(root / "project.json", {}) or {}
    source = Path(project.get("source_media", ""))
    if not source.is_file():
        raise SystemExit(f"Source media missing: {source}")
    scenes = rows(load(root / "timeline/scenes.json", {}), "scenes")
    selected = [s for s in scenes if float(s.get("start", -1)) < args.end and float(s.get("end", -1)) > args.start]
    if not selected:
        raise SystemExit("No scene/shot records overlap the requested range")
    last_pts = last_frame_pts(source)
    if last_pts is not None and last_pts < args.start + 0.05:
        print(json.dumps({"note": f"probed last frame {round(last_pts, 3)} is before the segment start; ignoring the probe result"}, ensure_ascii=False), file=sys.stderr)
        last_pts = None
    clamp = (last_pts - 0.05) if last_pts is not None else (args.end - 0.05)
    def clamped(t):
        return min(t, clamp)
    times = []
    for shot in selected:
        left = max(args.start, float(shot["start"]))
        right = min(args.end, float(shot["end"]))
        times.append(clamped((left + right) / 2))
    cursor = args.start
    while cursor < args.end:
        times.append(clamped(cursor))
        cursor += args.max_gap
    times.extend(clamped(t) for t in args.timestamp)
    times.append(clamped(max(args.start, args.end - 0.05)))
    times = sorted({round(t, 6) for t in times if args.start <= t < args.end})
    if not times:
        raise SystemExit(f"No sample timestamps could be placed in [{args.start}, {args.end}) after clamping; check the source video stream or the segment bounds")
    if last_pts is not None and args.end > last_pts:
        print(json.dumps({"note": f"requested end {args.end} is past the last decodable frame {round(last_pts,3)}; samples near the end were clamped",
                          "clamped_to": round(max(times), 3)}, ensure_ascii=False), file=sys.stderr)
    segment.mkdir(parents=True, exist_ok=True)
    evidence_dir = segment / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    package_path = segment / "work-package.json"
    input_path = segment / "analysis-input.json"
    if package_path.exists() and not args.force:
        raise SystemExit(f"Package exists; use --force to refresh: {package_path}")
    evidence = []
    kept = set()
    for index, timestamp in enumerate(times, 1):
        evidence_id = f"{args.segment_id}-ev-{index:04d}"
        name = f"frame-{index:04d}-{round(timestamp * 1000):010d}ms.jpg"
        target = evidence_dir / name
        kept.add(target.resolve())
        if not target.is_file() and args.reuse_evidence:
            raise SystemExit(f"Reusable evidence missing: {target}")
        if not target.is_file():
            try:
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.6f}", "-i", str(source), "-frames:v", "1", "-q:v", "3", "-y", str(target)], check=True)
            except subprocess.CalledProcessError as exc:
                if index == len(times) and last_pts is None:
                    retry = max(args.start, timestamp - 0.5)
                    print(json.dumps({"note": f"final-sample extraction at {timestamp} failed; retrying at {retry}"}, ensure_ascii=False), file=sys.stderr)
                    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{retry:.6f}", "-i", str(source), "-frames:v", "1", "-q:v", "3", "-y", str(target)], check=True)
                    new_target = evidence_dir / f"frame-{index:04d}-{round(retry * 1000):010d}ms.jpg"
                    target.rename(new_target)
                    target = new_target
                    kept.add(target.resolve())
                    timestamp = round(retry, 6)
                else:
                    raise
        shot = next((s for s in selected if float(s["start"]) <= timestamp < float(s["end"])), None)
        evidence.append({"id": evidence_id, "timestamp": timestamp, "path": target.relative_to(root).as_posix(), "sha256": digest(target), "source_media_id": "source-media", "source_shot_id": shot.get("id") if shot else None})
    if args.force:
        pruned = 0
        for orphan in sorted(evidence_dir.glob("frame-*.jpg")):
            if orphan.resolve() not in kept:
                orphan.unlink()
                pruned += 1
        if pruned:
            print(json.dumps({"note": f"removed {pruned} orphaned frame file(s) from {evidence_dir.relative_to(root).as_posix()}; re-run finalize_segment.py and refresh timeline/visual-evidence.json"}, ensure_ascii=False), file=sys.stderr)
    transcript = rows(load(root / "timeline/transcript.json", {}), "segments")
    speech = [x for x in transcript if float(x.get("start", -1)) < args.end + args.overlap and float(x.get("end", -1)) > args.start - args.overlap]
    bible = {}
    for name in ("characters", "locations", "objects", "story-state"):
        value = load(root / f"bible/{name}.json", [] if name != "story-state" else {}) or ({} if name == "story-state" else [])
        bible[name] = value if name == "story-state" or isinstance(value, dict) else {name: value}
    package = {"schema_version": 1, "segment_id": args.segment_id, "start": args.start, "end": args.end, "overlap_before": args.overlap, "overlap_after": args.overlap, "source_media": str(source), "shots": selected, "transcript_context": speech, "bible_snapshot": bible, "preferences": project.get("preferences", {}), "evidence": evidence, "agent_instructions": ["Inspect evidence and request denser extraction through prepare_segment.py when needed.", "Edit analysis-input.json only; do not create scripts or canonical artifact files.", "Describe visible evidence, not plot knowledge or dialogue restatement."]}
    write(package_path, package)
    if not input_path.exists() or input_path.stat().st_size == 0:
        write(input_path, {"schema_version": 1, "segment_id": args.segment_id, "observations": [], "cues": [], "bible_proposals": {"characters": [], "locations": [], "objects": [], "story_state": {}}, "agent_notes": []})
    print(json.dumps({"segment": args.segment_id, "shots": len(selected), "evidence_frames": len(evidence), "transcript_segments": len(speech), "analysis_input": str(input_path)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
