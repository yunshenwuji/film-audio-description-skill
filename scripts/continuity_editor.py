#!/usr/bin/env python3
"""Apply the coordinator's film-wide continuity edits to the merged script in
an auditable way.

  python scripts/continuity_editor.py PROJECT qc/continuity-edits.json

Each edit is {"action": "rewrite" | "delete" | "move", "cue_id": ..., "text"?: ...,
"start"?: ..., "reason": ...}. Rewrites and deletions invalidate any earlier
approval by design: the merged file's version is bumped and every change is
recorded in qc/continuity-pass.json. Cues are matched by id, never by sorted
position, so reordered timings cannot corrupt the wrong cue.
"""
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

def norm(s):
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", str(s))

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    root, edits_path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    edits = json.loads(edits_path.read_text(encoding="utf-8-sig"))
    merged_path = root / "script/merged-draft.json"
    doc = json.loads(merged_path.read_text(encoding="utf-8-sig"))
    cues = {str(c["id"]): c for c in doc["cues"]}
    applied, missing = [], []
    for edit in edits:
        cid = str(edit.get("cue_id"))
        cue = cues.get(cid)
        if cue is None:
            missing.append(cid)
            continue
        action = edit.get("action")
        if action == "delete":
            doc["cues"] = [c for c in doc["cues"] if str(c["id"]) != cid]
            cues.pop(cid, None)
        elif action == "rewrite":
            text = str(edit["text"]).strip()
            if not text:
                missing.append(f"{cid}:empty rewrite")
                continue
            cue["text_original"] = cue.get("text_original") or cue["text"]
            cue["text"] = text
            cue["review_duration"] = round(max(2.2, len(norm(text)) * 0.24), 2)
            cue["duration"] = cue["review_duration"]
        elif action == "move":
            cue["start"] = float(edit["start"])
            event = float(cue.get("visual_event_time", cue["start"]))
            cue["temporal_displacement"] = round(cue["start"] - event, 3)
            duration = float(cue.get("duration") or cue.get("review_duration") or 0)
            cue["available_slot"] = {"start": cue["start"], "end": round(cue["start"] + duration, 2)}
            cue.setdefault("placement_attempts", []).append({"to": cue["start"], "rule": edit.get("reason", "连贯性调整")})
        else:
            missing.append(f"{cid}:unknown action {action}")
            continue
        applied.append({"cue_id": cid, "action": action, "reason": edit.get("reason"),
                        "text": (cue.get("text") if action != "delete" else None)})
    doc["cues"].sort(key=lambda c: float(c["start"]))
    collisions = []
    for a, b in zip(doc["cues"], doc["cues"][1:]):
        gap = float(b["start"]) - (float(a["start"]) + float(a.get("duration") or a.get("review_duration") or 0))
        if gap < -0.01:
            collisions.append({"first": a["id"], "second": b["id"], "seconds": round(gap, 2)})
    doc["script_version"] = int(doc.get("script_version") or 1) + 1
    doc["counts"] = {"cues": len(doc["cues"])}
    doc["merged_edits"] = True
    merged_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "qc/continuity-pass.json").write_text(json.dumps(
        {"schema_version": 1, "script_version": doc["script_version"], "applied": applied,
         "unresolved_targets": missing, "new_collisions": collisions}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"applied": len(applied), "missing": missing, "collisions": collisions,
                      "cues": len(doc["cues"]), "script_version": doc["script_version"]}, ensure_ascii=False))
    return 1 if missing or collisions else 0

if __name__ == "__main__":
    raise SystemExit(main())
