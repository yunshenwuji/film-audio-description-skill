#!/usr/bin/env python3
"""Execute the placement order from the writing rules on the merged script:
move into a nearby dialogue-free gap first, shorten trailing semantic units
second, and raise the speech rate last. Splitting is a coordinator decision
made only when two visual moments exist and is applied through
continuity_editor.py, never invented automatically. Cues that still overlap
dialogue afterwards are flagged requires_user_review and recorded in
qc/placement-optimisation.json.

  python scripts/optimize_placement.py PROJECT_DIR [--max-rate 40]
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

def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else None

def rows(value, key):
    return value if isinstance(value, list) else value.get(key, []) if isinstance(value, dict) else []

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def norm_len(text):
    return len(re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", str(text)))

def speech_intervals(root):
    events = rows(load(root / "timeline/dialogue-events.json"), "events")
    intervals = []
    for e in events:
        if "kind" in e and e["kind"] != "speech":
            continue
        try:
            intervals.append((float(e["start"]), float(e["end"])))
        except (TypeError, ValueError):
            continue
    return intervals

def hit(intervals, start, end):
    return round(sum(max(0, min(end, b) - max(start, a)) for a, b in intervals), 3)

def shorten_text(text, target_length):
    """Strip trailing semantic units (after ，。；) until the text fits the
    target length or only the first unit remains. Returns the shortened text."""
    if norm_len(text) <= target_length:
        return text
    parts = re.split(r"(?<=[，。；])", text)
    head = [p for p in parts if p.strip()]
    while head:
        candidate = "".join(head).rstrip("，。；")
        if norm_len(candidate) <= target_length or len(head) == 1:
            return candidate
        head.pop()
    return text

def main():
    p = argparse.ArgumentParser()
    p.add_argument("project_dir")
    p.add_argument("--max-rate", type=float, default=40.0, help="Absolute rate ceiling in percent (default 40).")
    args = p.parse_args()
    root = Path(args.project_dir).resolve()
    path = root / "script/merged-draft.json"
    doc = load(path)
    if not isinstance(doc, dict):
        raise SystemExit("script/merged-draft.json missing; run merge_draft.py first")
    cues = doc.get("cues", [])
    speech = speech_intervals(root)
    cues.sort(key=lambda c: float(c["start"]))
    moved, shortened, rated, kept = [], [], [], []
    for i, c in enumerate(cues):
        start = float(c["start"])
        dur = float(c.get("duration") or c.get("review_duration") or 0)
        event = float(c.get("visual_event_time", start))
        kind = c.get("visual_event_type", "action")
        limit = 15.0 if kind in ("location_change", "title_credit") else 5.0
        overlap = hit(speech, start, start + dur)
        if overlap <= 0.5:
            continue
        prev_end = float(cues[i - 1]["start"]) + float(cues[i - 1].get("duration") or cues[i - 1].get("review_duration") or 0) if i else -1.0
        next_start = float(cues[i + 1]["start"]) if i + 1 < len(cues) else float("inf")
        best = None
        for step in [x * 0.25 for x in range(0, 41)]:
            for cand in (round(event + step, 2), round(event - step, 2)):
                if abs(cand - event) > limit or cand < prev_end + 0.25 or cand + dur > next_start - 0.25:
                    continue
                score = (hit(speech, cand, cand + dur), abs(cand - event))
                if best is None or score < best[0]:
                    best = (score, cand)
                if score[0] == 0.0:
                    break
            if best and best[0][0] == 0.0:
                break
        attempts = c.get("placement_attempts") or []
        if best and best[0][0] < overlap - 0.25:
            attempts.append({"from": start, "to": best[1], "dialogue_overlap_before": overlap,
                             "dialogue_overlap_after": best[0][0], "rule": "先找无对白空档"})
            c["start"] = best[1]
            c["temporal_displacement"] = round(best[1] - event, 3)
            c["available_slot"] = {"start": best[1], "end": round(best[1] + dur, 2)}
            c["placement_decision"] = "移到可见事件附近的无对白空档"
            c["placement_attempts"] = attempts
            moved.append((c["id"], start, best[1], best[0][0]))
            continue
        available = min(next_start, start + limit + dur) - max(prev_end, start - limit, start)
        needed_chars = int(available / 0.24)
        shortened_text = shorten_text(str(c.get("text", "")), max(2, needed_chars))
        if shortened_text != str(c.get("text", "")):
            attempts.append({"rule": "再缩短：删去低优先级尾部语义单元",
                             "text_before": c.get("text"), "text_after": shortened_text})
            c["text"] = shortened_text
            c["review_duration"] = round(max(2.2, norm_len(shortened_text) * 0.24), 2)
            c["duration"] = c["review_duration"]
            c["placement_decision"] = "缩短后放入可用空档"
            c["placement_attempts"] = attempts
            shortened.append(c["id"])
            continue
        rate = 0.0
        if available > 0 and dur > available:
            rate = round(min((dur / available - 1) * 100, args.max_rate), 1)
            if rate > 0:
                attempts.append({"rule": "最后提语速", "rate": f"+{rate}%", "measured_or_estimated": "estimated",
                                 "note": "估算：以实测时长重跑为准"})
                c["rate"] = f"+{rate}%"
                c["duration"] = round(dur / (1 + rate / 100), 2)
                c["review_duration"] = c["duration"]
                c["available_slot"] = {"start": start, "end": round(start + c["duration"], 2)}
                c["placement_attempts"] = attempts
                rated.append((c["id"], f"+{rate}%"))
                continue
        c["requires_user_review"] = True
        c["overlap_note"] = "这条只能压在对白上：移动、缩短、提速都无法放入空档。已按“允许有限重叠”保留，可在审阅时要求删短或改位置。"
        c["placement_attempts"] = attempts
        kept.append((c["id"], overlap))
    cues.sort(key=lambda c: float(c["start"]))
    doc["cues"] = cues
    doc["merged_edits"] = True
    write(path, doc)
    report = {"schema_version": 1, "moved": moved, "shortened": shortened, "rate_increased": rated,
              "left_on_dialogue": kept,
              "rule": "先移动、再缩短、最后才提语速；拆分仅由协调者在确认两个视觉时刻后通过 continuity_editor.py 手动执行；压对白的条目已标记 requires_user_review"}
    write(root / "qc/placement-optimisation.json", report)
    print(json.dumps({"moved": len(moved), "shortened": len(shortened), "rate_increased": len(rated),
                      "left_on_dialogue": len(kept)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
