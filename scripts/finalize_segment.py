#!/usr/bin/env python3
r"""Expand compact agent analysis into canonical segment artifacts.

Segment ids must match `segment-\d+`: audit_project.py discovers segment
artifacts with the same glob. Cues may carry a `displacement_justification`
string that audit_project.py accepts as the documented exemption for
`cue_too_far_from_visual_event`; a warning is printed when a cue exceeds the
displacement limit without one.
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

SEGMENT_ID_RE = re.compile(r"segment-\d+")

def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def intersect(a, b, c, d):
    return max(0, min(b, d) - max(a, c))

def require(value, fields, label):
    missing = [field for field in fields if value.get(field) in (None, "", [])]
    if missing:
        raise SystemExit(f"{label} missing: {', '.join(missing)}")

def main():
    p = argparse.ArgumentParser(description="Validate compact semantic input and write canonical segment JSON.")
    p.add_argument("project_dir")
    p.add_argument("segment_id")
    args = p.parse_args()
    if not SEGMENT_ID_RE.fullmatch(args.segment_id):
        raise SystemExit(f"segment_id must match segment-NNN (audit_project.py only discovers segments/segment-*): {args.segment_id}")
    root = Path(args.project_dir).resolve()
    segment = root / "segments" / args.segment_id
    package = load(segment / "work-package.json")
    data = load(segment / "analysis-input.json")
    if data.get("segment_id") != args.segment_id:
        raise SystemExit("analysis-input segment_id mismatch")
    evidence = {item["id"]: item for item in package.get("evidence", [])}
    transcript = package.get("transcript_context", [])
    observations, local = [], {}
    for index, item in enumerate(data.get("observations", []), 1):
        require(item, ("local_id", "evidence_ids", "subject", "action", "location", "confidence"), f"observation {index}")
        if item["local_id"] in local:
            raise SystemExit(f"Duplicate local_id: {item['local_id']}")
        missing = [value for value in item["evidence_ids"] if value not in evidence]
        if missing:
            raise SystemExit(f"Unknown evidence IDs for {item['local_id']}: {missing}")
        frames = sorted(evidence[value]["timestamp"] for value in item["evidence_ids"])
        observation_id = f"{args.segment_id}-obs-{index:04d}"
        local[item["local_id"]] = observation_id
        sound_sufficient = bool(item.get("sound_sufficient", False))
        observation = {"id": observation_id, "start": float(item.get("start", frames[0])), "end": float(item.get("end", frames[-1])), "subject": item["subject"], "action": item["action"], "object": item.get("object"), "location": item["location"], "evidence_frames": frames, "evidence_ids": item["evidence_ids"], "evidence_type": "visual", "sound_sufficient": sound_sufficient, "dialogue_support_only": bool(item.get("dialogue_support_only", True)), "confidence": float(item["confidence"]), "uncertainty": item.get("uncertainty"), "subject_character_ids": item.get("subject_character_ids", [])}
        if sound_sufficient:
            require(item, ("visible_state", "stability_reason", "sound_conveys"), f"no-cue observation {item['local_id']}")
            observation.update({"visible_state": item["visible_state"], "stability_reason": item["stability_reason"], "sound_conveys": item["sound_conveys"], "crosses_visual_event": False})
        observations.append(observation)
    cues = []
    for index, item in enumerate(data.get("cues", []), 1):
        require(item, ("observation_ref", "text"), f"cue {index}")
        if item["observation_ref"] not in local:
            raise SystemExit(f"Unknown observation_ref: {item['observation_ref']}")
        observation = next(value for value in observations if value["id"] == local[item["observation_ref"]])
        if observation["sound_sufficient"]:
            raise SystemExit(f"Cue references sound-sufficient observation: {item['observation_ref']}")
        event = float(item.get("visual_event_time", observation["evidence_frames"][0]))
        start = float(item.get("start", event))
        duration = float(item.get("review_duration", max(2.2, len(str(item["text"])) * 0.24)))
        end = start + duration
        overlaps = [str(line.get("id", f"asr-{i}")) for i, line in enumerate(transcript, 1) if intersect(start, end, float(line["start"]), float(line["end"])) > 0]
        facts = item.get("atomic_facts") or [{"role": "subject", "text": item.get("subject", observation["subject"]), "priority": "required"}, {"role": "action", "text": item.get("action", observation["action"]), "priority": "required"}]
        displacement = round(start - event, 3)
        limit = 15 if item.get("visual_event_type", "action") in ("location_change", "title_credit") else 5
        if abs(displacement) > limit and not item.get("displacement_justification"):
            print(json.dumps({"warning": f"cue {index} is {displacement}s from its visual event; provide displacement_justification in analysis-input or move it back within {limit}s"}, ensure_ascii=False), file=sys.stderr)
        cues.append({"id": f"{args.segment_id}-cue-{index:03d}", "start": start, "text": item["text"], "observation_ids": [observation["id"]], "evidence_frames": observation["evidence_frames"], "evidence_ids": observation["evidence_ids"], "subject_character_ids": item.get("subject_character_ids", observation.get("subject_character_ids", [])), "reason": item.get("reason", "补充声轨未明确传达的可见信息"), "confidence": float(item.get("confidence", observation["confidence"])), "requires_user_review": bool(item.get("requires_user_review", False)), "placement_class": "C" if overlaps else item.get("placement_class", "B"), "available_slot": {"start": start, "end": end}, "computed_dialogue_overlaps": overlaps, "overlap_permission": "limited_user_approved" if overlaps else "none_needed", "placement_decision": item.get("placement_decision", "候选位置；由协调者执行最终对白审计"), "visual_event_time": event, "visual_event_type": item.get("visual_event_type", "action"), "temporal_displacement": displacement, "displacement_justification": item.get("displacement_justification"), "atomic_facts": facts, "placement_attempts": item.get("placement_attempts", []), "review_duration": duration, "duration": duration, "voice": None, "rate": None, "uncertainty": item.get("uncertainty")})
    write(segment / "manifest.json", {"schema_version": 1, "segment_id": args.segment_id, "start": package["start"], "end": package["end"], "overlap_before": package.get("overlap_before", 0), "overlap_after": package.get("overlap_after", 0), "status": "drafted", "source_shot_ids": [value.get("id") for value in package.get("shots", [])], "evidence_frame_count": len(evidence)})
    write(segment / "evidence-index-proposal.json", {"schema_version": 1, "segment_id": args.segment_id, "frames": list(evidence.values())})
    write(segment / "observations.json", {"schema_version": 1, "segment_id": args.segment_id, "observations": observations})
    write(segment / "draft-cues.json", {"schema_version": 1, "segment_id": args.segment_id, "cues": cues})
    proposals = data.get("bible_proposals", {})
    write(segment / "bible-proposals.json", {"schema_version": 1, "segment_id": args.segment_id, "characters": proposals.get("characters", []), "locations": proposals.get("locations", []), "objects": proposals.get("objects", []), "story_state": proposals.get("story_state", {})})
    print(json.dumps({"segment": args.segment_id, "observations": len(observations), "cues": len(cues), "dialogue_overlaps": sum(bool(value["computed_dialogue_overlaps"]) for value in cues)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
