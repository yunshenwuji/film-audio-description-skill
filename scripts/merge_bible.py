#!/usr/bin/env python3
"""Consolidate the bible proposals that segment agents emit, and apply the
coordinator's identity map to the canonical bible.

  python scripts/merge_bible.py collect PROJECT   -> qc/bible-candidates.json
  python scripts/merge_bible.py apply PROJECT MAP -> bible/characters|locations|objects|story-state.json

`apply` never invents identity: every field comes from the coordinator-authored
map, and the tool refuses to write a record that drops a provisional id that no
alias list covers. Bible files use the canonical object-with-key shape, e.g.
{"characters": [...]}, matching init_project.py and the audit rows() reader.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

KINDS = ("characters", "locations", "objects")

def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else None

def rows(value, key):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return value.get(key, [])
    return []

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def collect(root):
    buckets = {k: defaultdict(list) for k in KINDS}
    states = {}
    segments_with_proposals = set()
    for directory in sorted((root / "segments").glob("segment-*")):
        proposal = load(directory / "bible-proposals.json")
        if not isinstance(proposal, dict):
            continue
        has_proposal = False
        for kind in KINDS:
            for item in rows(proposal, kind):
                pid = str(item.get("provisional_id") or item.get("id"))
                buckets[kind][f"{directory.name}/{pid}"].append({"segment": directory.name, "pid": pid, **item})
                has_proposal = True
        story = proposal.get("story_state") or {}
        if story:
            states[directory.name] = story
        if has_proposal or story:
            segments_with_proposals.add(directory.name)
    out = {"schema_version": 1, "characters": {}, "locations": {}, "objects": {}, "story_state_by_segment": states}
    for kind in KINDS:
        for pid, entries in sorted(buckets[kind].items()):
            merged = {"proposals": entries, "segments": [e["segment"] for e in entries],
                      "first_visual_appearance": min([float(e["first_visual_appearance"]) for e in entries
                                                      if e.get("first_visual_appearance") is not None], default=None),
                      "labels": sorted({str(e.get("safe_label")) for e in entries if e.get("safe_label")}),
                      "descriptions": [str(e.get("visual_description") or "") for e in entries],
                      "name_evidence": [e.get("name_evidence") for e in entries if e.get("name_evidence")],
                      "person_binding": [e.get("person_binding") for e in entries if e.get("person_binding")],
                      "notes": [str(e.get("notes") or "") for e in entries if e.get("notes")],
                      "label_conflict": len({str(e.get("safe_label")) for e in entries if e.get("safe_label")}) > 1}
            out[kind][pid] = merged
    write(root / "qc/bible-candidates.json", out)
    print(json.dumps({"characters": len(out["characters"]), "locations": len(out["locations"]),
                      "objects": len(out["objects"]), "segments_with_proposals": len(segments_with_proposals)}, ensure_ascii=False))
    return 0

def apply_map(root, map_path):
    mapping = json.loads(map_path.read_text(encoding="utf-8-sig"))
    candidates = load(root / "qc/bible-candidates.json") or {}
    # Validate every kind BEFORE writing anything: a failed apply must never
    # leave the canonical bible half-overwritten.
    planned = {}
    for kind in KINDS:
        records = [dict(rec) for rec in mapping.get(kind, [])]
        for rec in records:
            rec.setdefault("aliases", [])
            rec.pop("provisional_id", None)
        used = set()
        for rec in records:
            used.add(str(rec.get("id")))
            for alias in rec.get("aliases", []):
                used.add(str(alias))
                used.add(str(alias).split("/")[-1])
        orphan = [key for key in (candidates.get(kind) or {})
                  if key not in used and key.split("/")[-1] not in used]
        if orphan:
            print(json.dumps({kind: len(records), "unmapped": orphan}, ensure_ascii=False))
            return 1
        planned[kind] = records
    for kind in KINDS:
        write(root / "bible" / f"{kind}.json", {"schema_version": 1, kind: planned[kind]})
        print(json.dumps({kind: len(planned[kind])}, ensure_ascii=False))
    write(root / "bible/story-state.json", {"story-state": mapping.get("story_state", {})})
    return 0

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    command, project = sys.argv[1], sys.argv[2]
    root = Path(project).resolve()
    if command == "collect":
        return collect(root)
    if command == "apply":
        return apply_map(root, Path(sys.argv[3]).resolve())
    print("unknown command")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
