#!/usr/bin/env python3
"""Render deterministic review SRT and cue map from merged cues."""
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

def stamp(value):
    millis = max(0, round(float(value) * 1000))
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cue_json")
    parser.add_argument("srt_output")
    parser.add_argument("map_output")
    parser.add_argument("--script-version", type=int, required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.cue_json).read_text(encoding="utf-8-sig"))
    cues = data if isinstance(data, list) else data.get("cues", [])
    cues = sorted(cues, key=lambda cue: float(cue["start"]))
    blocks, mapping = [], []
    for index, cue in enumerate(cues, 1):
        start = float(cue["start"])
        duration = cue.get("measured_duration", cue.get("duration", cue.get("review_duration")))
        if duration is None:
            raise SystemExit(f"Cue {cue.get('id', index)} lacks review/measured duration")
        end = start + float(duration)
        text = str(cue.get("text", "")).strip()
        if end <= start or not text:
            raise SystemExit(f"Cue {cue.get('id', index)} has invalid timing or text")
        blocks.append("\n".join((str(index), f"{stamp(start)} --> {stamp(end)}", text)) + "\n")
        mapping.append({"srt_index": index, "cue_id": cue.get("id"), "script_version": args.script_version,
            "start": start, "end": end, "text": text, "observation_ids": cue.get("observation_ids", []),
            "evidence_frames": cue.get("evidence_frames", []), "uncertainty": cue.get("uncertainty"),
            "placement_class": cue.get("placement_class"),
            "timing_kind": "measured" if cue.get("measured_duration") is not None else "estimated",
            "review_status": "pending"})
    Path(args.srt_output).write_text("\n".join(blocks), encoding="utf-8-sig")
    Path(args.map_output).write_text(json.dumps({"script_version": args.script_version, "entries": mapping}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
