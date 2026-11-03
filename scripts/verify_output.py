#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

def probe(path: Path):
    raw = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,sample_rate,channels",
        "-of", "json", str(path)], text=True, encoding="utf-8")
    return json.loads(raw)

def main():
    p = argparse.ArgumentParser(description="Verify a rendered audio-described video container.")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--duration-tolerance", type=float, default=0.25)
    p.add_argument("--report")
    p.add_argument("--listening-review", help="Completed listening-review JSON; required for a full QC pass.")
    p.add_argument("--duck-envelope", help="Duck-envelope JSON; required for a full QC pass.")
    p.add_argument("--audio-measurements", help="Reproducible source/output level and narration-presence measurements.")
    args = p.parse_args()
    source, output = Path(args.source), Path(args.output)
    issues = []
    if output.suffix.lower() == ".partial" or ".partial." in output.name.lower():
        issues.append({"type": "partial_output_name"})
    if not output.exists() or output.stat().st_size == 0:
        issues.append({"type": "missing_or_empty_output"})
        result = {"passed": False, "issues": issues}
    else:
        try:
            src, out = probe(source), probe(output)
            src_duration = float(src["format"]["duration"]); out_duration = float(out["format"]["duration"])
            if abs(src_duration - out_duration) > args.duration_tolerance:
                issues.append({"type": "duration_mismatch", "source": src_duration, "output": out_duration})
            types = [s.get("codec_type") for s in out.get("streams", [])]
            if "video" not in types: issues.append({"type": "missing_video_stream"})
            if "audio" not in types: issues.append({"type": "missing_audio_stream"})
            if not args.listening_review:
                issues.append({"type": "listening_review_required"})
            else:
                review = json.loads(Path(args.listening_review).read_text(encoding="utf-8-sig"))
                if review.get("all_required_items_complete") is not True or review.get("reviewer_kind") == "producing_model":
                    issues.append({"type": "listening_review_incomplete"})
            if not args.duck_envelope:
                issues.append({"type": "duck_envelope_required"})
            else:
                envelope = json.loads(Path(args.duck_envelope).read_text(encoding="utf-8-sig"))
                if not envelope.get("entries") or envelope.get("non_narration_unity_verified") is not True:
                    issues.append({"type": "duck_envelope_incomplete"})
            if not args.audio_measurements:
                issues.append({"type": "audio_measurements_required"})
            else:
                measurements = json.loads(Path(args.audio_measurements).read_text(encoding="utf-8-sig"))
                required = ("source_sha256", "output_sha256", "method", "tolerance_db",
                            "non_narration_samples", "narration_presence_samples", "source_under_narration_samples")
                if any(measurements.get(field) in (None, "", []) for field in required):
                    issues.append({"type": "audio_measurements_incomplete"})
            result = {"passed": not issues, "issues": issues, "source_probe": src, "output_probe": out}
        except Exception as exc:
            result = {"passed": False, "issues": issues + [{"type": "probe_failure", "error": str(exc)}]}
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report: Path(args.report).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    sys.exit(0 if result["passed"] else 1)

if __name__ == "__main__":
    main()
