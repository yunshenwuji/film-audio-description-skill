#!/usr/bin/env python3
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

def main():
    p = argparse.ArgumentParser(description="Audit time-coded audio-description cues.")
    p.add_argument("cue_json")
    p.add_argument("--media-duration", type=float)
    p.add_argument("--report")
    p.add_argument("--require-rendered", action="store_true", help="Require measured duration, audio path, and audible bounds after TTS.")
    args = p.parse_args()
    cues = json.loads(Path(args.cue_json).read_text(encoding="utf-8"))
    if not isinstance(cues, list):
        raise SystemExit("Cue file must contain a JSON array.")
    issues = []
    previous_start = -1.0
    previous_end = -1.0
    ids = set()
    for index, cue in enumerate(cues):
        label = cue.get("id", f"index-{index}")
        for field in ("start", "text"):
            if field not in cue:
                issues.append({"cue": label, "type": "missing_field", "field": field})
        if label in ids:
            issues.append({"cue": label, "type": "duplicate_id"})
        ids.add(label)
        try:
            start = float(cue["start"])
        except (KeyError, TypeError, ValueError):
            continue
        duration = cue.get("measured_duration") if args.require_rendered else cue.get("duration", cue.get("review_duration"))
        if args.require_rendered:
            for field in ("measured_duration", "audio_path", "audible_start", "audible_end"):
                if cue.get(field) in (None, ""):
                    issues.append({"cue": label, "type": "missing_rendered_field", "field": field})
            try:
                audible_duration = float(cue["audible_end"]) - float(cue["audible_start"])
                if abs(audible_duration - float(cue["measured_duration"])) > 0.2:
                    issues.append({"cue": label, "type": "rendered_duration_mismatch"})
            except (KeyError, TypeError, ValueError):
                pass
        end = float(cue.get("audible_end")) if args.require_rendered and cue.get("audible_end") is not None else start + float(duration) if duration is not None else start
        if start < 0:
            issues.append({"cue": label, "type": "negative_start"})
        if start < previous_start:
            issues.append({"cue": label, "type": "out_of_order"})
        if duration is not None and float(duration) <= 0:
            issues.append({"cue": label, "type": "invalid_duration"})
        if duration is not None and start < previous_end - 0.001:
            issues.append({"cue": label, "type": "narration_overlap", "overlap_seconds": round(previous_end - start, 3)})
        if args.media_duration is not None and end > args.media_duration + 0.05:
            issues.append({"cue": label, "type": "beyond_media", "end": end})
        rate = cue.get("rate")
        if isinstance(rate, str) and rate.startswith("+") and rate.endswith("%"):
            try:
                if float(rate[1:-1]) > 40:
                    issues.append({"cue": label, "type": "rate_above_40_percent", "rate": rate})
            except ValueError:
                issues.append({"cue": label, "type": "invalid_rate", "rate": rate})
        previous_start, previous_end = start, max(previous_end, end)
    report = {"cue_count": len(cues), "passed": not issues, "issues": issues}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        Path(args.report).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    sys.exit(0 if not issues else 1)

if __name__ == "__main__":
    main()
