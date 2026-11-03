#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

DIRS = [
    "media", "materials/character-references", "materials/subtitles", "timeline", "bible", "segments", "script",
    "narration/cues", "qc", "output"
]

DEFAULTS = {
    "description_density": "medium_detailed",
    "opening_credits": {"scope": "opening_and_principal_ending", "required_when_selected": True},
    "character_naming": "first_speech_once",
    "emotion_description": "plot_relevant",
    "spoiler_policy": "preserve_reveal_order",
    "dialogue_overlap": "limited",
    "voice": None,
    "speech_rate": {"mode": "adaptive", "minimum": "+10%", "maximum": "+40%"},
    "ducking": {"strength": "light", "duck_only_during_narration": True, "outside_narration_gain": 1.0, "attack_ms": 300, "release_ms": 650, "ratio": 3.0},
    "review": {"required_before_synthesis": True, "long_film_batch_minutes": 20, "require_final_full_script_approval": True},
    "analysis": {"segment_minutes": [8, 15], "context_overlap_seconds": [15, 30], "maximum_unexplained_observation_gap_seconds": 90, "evidence_first": True}
}

def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    p = argparse.ArgumentParser(description="Initialize an audio-description project.")
    p.add_argument("project_dir")
    p.add_argument("source_media")
    p.add_argument("--title")
    p.add_argument("--script-only", action="store_true",
                    help="Script-only delivery: skip narration/mix outputs and TTS-related preferences questions.")
    args = p.parse_args()
    root = Path(args.project_dir).resolve()
    source = Path(args.source_media).resolve()
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"Refusing to initialize non-empty directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for name in DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    project = {
        "schema_version": 2,
        "title": args.title or source.stem,
        "source_media": str(source),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": "initialized",
        "script_version": 0,
        "approved_script_version": None,
        "batch_approvals": [],
        "preferences": DEFAULTS,
        "outputs": ["review_script", "machine_script", "uncertainty_report"] if args.script_only else ["review_script", "machine_script", "narration_track", "mixed_video", "quality_report"]
    }
    write_json(root / "project.json", project)
    for name, empty in [("characters", {"characters": []}), ("locations", {"locations": []}), ("objects", {"objects": []}), ("story-state", {"story-state": {}})]:
        write_json(root / "bible" / f"{name}.json", empty)
    write_json(root / "materials" / "manifest.json", {"schema_version": 1, "artifacts": [], "skipped_steps": [], "conflicts": []})
    print(root)

if __name__ == "__main__":
    main()
