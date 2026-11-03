#!/usr/bin/env python3
"""Apply the coordinator's identity decisions to the canonical bible and merged
script, and emit qc/identity-convergence.json for the current review range.

  python scripts/converge_identities.py PROJECT_DIR IDENTITY_MAP [--blocks "0-2400,2400-4800"]

The identity map is authored by the coordinator and carries the evidence
chains; this tool never invents a name, it only applies and checks what the map
says. Each map entry may list `merge_ids` (provisional records to absorb),
`aliases`, `label_variants`, the three legal resolution statuses, and the
evidence fields audit_project.py requires.

Label rewriting uses the mask-first order: ALL registered labels across ALL
characters (referenced by the cue or not) are masked into placeholders first,
longest label first, so substring collisions such as "蓝袍男子"/"黄袍男子",
"衬衫男人"/"花衬衫男人" or a stray "赤膊男子" can never be rewritten into the
wrong person. Then referenced characters' placeholders are replaced with the
canonical name (only from their narration-allowed reveal time onward) and all
remaining placeholders are restored to their original labels. Variants must be
at least three normalized characters and must not be a generic term ("男子",
"女人", "孩子" ...); such variants are reported as problems and skipped instead
of being registered.

When --blocks is given (or the identity map carries `review_ranges`), the
convergence report lists sub-range blocks whose union covers the review batch,
so a single full-film batch can be converged wave by wave.
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

LEGAL = ("confirmed", "not_yet_revealed", "unresolved_after_evidence_review")
GENERIC_LABELS = ("男人", "女人", "男子", "女子", "男孩", "女孩", "孩子", "老人", "小孩", "少年", "少女", "青年")
MASK = "\u0001{cid}:{lab}\u0001"

def n(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def rows(v, k):
    return v if isinstance(v, list) else (v.get(k, []) if isinstance(v, dict) else [])

def norm(s):
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", str(s)).lower()

def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def labels_of(c):
    labels = ([str(c.get("safe_label"))] if c.get("safe_label") else []) + [str(v) for v in (c.get("label_variants") or [])]
    return sorted({x for x in labels if x and len(norm(x)) >= 3}, key=lambda x: -len(x))

def rewrite_text(text, cue_ids, by_id, all_chars, event):
    """Mask every character's labels (referenced or not) in ONE regex pass over
    the original text, longest label first, then replace referenced characters'
    placeholders with their canonical name when the cue's visual event is
    at/after their narration-allowed reveal time; every other placeholder is
    restored to its original label. The single-pass alternation never matches
    inside an already-inserted placeholder, so substring labels such as
    衬衫男人/花衬衫男人 cannot corrupt each other, and the rewrite is
    independent of subject_character_ids ordering."""
    target_ids = {str(x) for x in cue_ids if str(x) in by_id}
    by_lab = {}
    for cid, c in all_chars:
        for lab in labels_of(c):
            by_lab.setdefault(lab, set()).add(cid)
    pattern = re.compile("|".join(re.escape(lab) for lab in sorted(by_lab, key=lambda x: -len(x))))
    tokens = []
    def mask(match):
        lab = match.group(0)
        cid = sorted(by_lab[lab])[0]
        tok = MASK.format(cid=cid, lab=norm(lab))
        tokens.append((tok, cid, lab))
        return tok
    text = pattern.sub(mask, text)
    for tok, cid, lab in tokens:
        replacement = lab
        if cid in target_ids:
            c = by_id.get(cid) or {}
            name = c.get("canonical_name")
            allow = c.get("narration_allowed_after")
            if name and allow is not None and event is not None and event >= float(allow) and lab != name:
                replacement = name
        text = text.replace(tok, replacement)
    return text

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("project_dir")
    p.add_argument("identity_map")
    p.add_argument("--blocks", help='Comma-separated "start-end" sub-ranges whose union covers the review batch.')
    args = p.parse_args()
    root = Path(args.project_dir).resolve()
    identity = load(Path(args.identity_map).resolve())
    bible_path = root / "bible/characters.json"
    bible = {"schema_version": 1, "characters": rows(load(bible_path), "characters")} if bible_path.is_file() else {"schema_version": 1, "characters": []}
    by_id = {str(c.get("id")): c for c in bible["characters"]}
    problems = []
    absorbed = set()
    absorbed_map = {}
    for rec in identity.get("characters", []):
        cid = str(rec["id"])
        for mid in rec.get("merge_ids", []):
            absorbed.add(str(mid))
            absorbed_map[str(mid)] = cid
        base = by_id.get(cid, {})
        merged = {**base, **{k: v for k, v in rec.items() if k not in ("aliases", "merge_ids", "label_variants")}}
        merged.setdefault("aliases", [])
        merged["aliases"] = sorted({str(x) for x in (base.get("aliases", []) + rec.get("aliases", []))})
        variants = [str(v) for v in rec.get("label_variants", [])]
        registered = []
        for v in variants:
            nv = norm(v)
            if len(nv) < 3 or nv in GENERIC_LABELS:
                problems.append(f"{cid}: variant '{v}' is too generic (>=3 normalized chars, not a generic term); not registered")
            elif v == rec.get("canonical_name") or v == rec.get("safe_label"):
                problems.append(f"{cid}: variant '{v}' duplicates safe_label/canonical name; not registered")
            else:
                registered.append(v)
        merged["label_variants"] = sorted(set(registered))
        if rec.get("resolution_status") == "confirmed" and not rec.get("canonical_name"):
            problems.append(f"{cid}: confirmed without canonical_name")
        if rec.get("canonical_name"):
            for key, req in (("name_evidence", ("type", "start", "end", "source_text", "observation_ids", "evidence_frames", "confidence")),
                             ("person_binding", ("method", "observation_ids", "evidence_frames", "confidence"))):
                entries = rec.get(key) or []
                if not entries:
                    problems.append(f"{cid}: canonical name lacks {key}")
                for z in entries:
                    miss = [f for f in req if z.get(f) in (None, "", [])]
                    if miss:
                        problems.append(f"{cid}: {key} entry missing {miss}")
        if rec.get("resolution_status") not in LEGAL:
            problems.append(f"{cid}: resolution_status must be one of {LEGAL}")
        if rec.get("resolution_status") == "unresolved_after_evidence_review":
            if not rec.get("unresolved_reason") or not rec.get("uncertainty_item_id"):
                problems.append(f"{cid}: unresolved identity needs unresolved_reason + uncertainty_item_id")
        merged.pop("provisional_id", None)
        by_id[cid] = merged
    records = [by_id[k] for k in sorted(by_id) if k not in absorbed]
    write(bible_path, {"schema_version": 1, "characters": records})
    for name in ("locations", "objects"):
        bp = root / "bible" / f"{name}.json"
        if not bp.is_file():
            continue
        local = {str(x.get("id")): x for x in rows(load(bp), name)}
        merged = [x for k, x in sorted(local.items()) if k not in absorbed]
        write(bp, {"schema_version": 1, name: merged})

    merged_path = root / "script/merged-draft.json"
    if not merged_path.is_file():
        print("script/merged-draft.json missing; run merge_draft.py first", file=sys.stderr)
        return 1
    merged_doc = load(merged_path)
    cues = merged_doc.get("cues", [])
    for cue in cues:
        if absorbed_map:
            mapped = []
            for x in cue.get("subject_character_ids", []):
                mapped.append(absorbed_map.get(str(x), str(x)))
            cue["subject_character_ids"] = list(dict.fromkeys(mapped))
    renamed = 0
    all_chars = sorted(by_id.items())
    for cue in cues:
        ids = [str(x) for x in cue.get("subject_character_ids", [])]
        text = str(cue.get("text", ""))
        event = n(cue.get("visual_event_time"))
        if event is None:
            event = n(cue.get("start", 0)) or 0.0
        new_text = rewrite_text(text, ids, by_id, all_chars, event)
        if new_text != text:
            cue["text"] = new_text
            cue["text_original"] = cue.get("text_original") or text
            cue["review_duration"] = round(max(2.2, len(norm(new_text)) * 0.24), 2)
            cue["duration"] = cue["review_duration"]
            renamed += 1
    for cue in cues:
        text = str(cue.get("text", ""))
        for cid, c in by_id.items():
            name = c.get("canonical_name")
            if name and name in text and cid not in [str(x) for x in cue.get("subject_character_ids", [])]:
                cue.setdefault("subject_character_ids", []).append(cid)
    for cid, c in by_id.items():
        name = c.get("canonical_name")
        if not name:
            c["first_naming_cue_time"] = None
            continue
        hits = [float(q["start"]) for q in cues if name in str(q.get("text", ""))
                and cid in [str(x) for x in q.get("subject_character_ids", [])]]
        c["first_naming_cue_time"] = round(min(hits), 3) if hits else None
    merged_doc["cues"] = cues
    merged_doc["identity_pass"] = {"applied": True, "cues_renamed": renamed, "characters": len(by_id), "problems": problems}
    merged_doc["merged_edits"] = True
    write(merged_path, merged_doc)

    blocks = identity.get("review_ranges")
    if args.blocks:
        try:
            blocks = [{"start": float(part.split("-")[0]), "end": float(part.split("-")[1])}
                      for part in args.blocks.split(",") if "-" in part]
        except (ValueError, IndexError):
            raise SystemExit(f"invalid --blocks '{args.blocks}': expected comma-separated start-end ranges like 0-2400,2400-4800")
    if isinstance(blocks, list) and blocks:
        ranges = {"review_ranges": blocks}
    else:
        project = load(root / "project.json") or {}
        batch = project.get("current_review_batch") or {}
        ranges = {"review_range": {"start": batch.get("start", 0.0), "end": batch.get("end")}}
        if batch.get("end") is None:
            ranges["review_range"]["end"] = None
    entries = []
    for cid, c in sorted(by_id.items()):
        first = c.get("first_visual_appearance")
        cue_ids = sorted({str(q["id"]) for q in cues if cid in [str(x) for x in q.get("subject_character_ids", [])]})
        entry = {"character_id": cid, "merged_source_ids": c.get("aliases", []),
                 "resolution_status": c.get("resolution_status"),
                 "evidence_sources_checked": c.get("evidence_sources_checked", []),
                 "cue_ids": cue_ids, "first_visual_appearance": first,
                 "canonical_name": c.get("canonical_name"),
                 "narration_allowed_after": c.get("narration_allowed_after")}
        if c.get("resolution_status") == "unresolved_after_evidence_review":
            entry["unresolved_reason"] = c.get("unresolved_reason")
            entry["uncertainty_item_id"] = c.get("uncertainty_item_id")
        entries.append(entry)
    convergence = {"schema_version": 2, "characters": entries, "generated_by": "scripts/converge_identities.py", "problems": problems}
    convergence.update(ranges)
    write(root / "qc/identity-convergence.json", convergence)
    print(json.dumps({"characters": len(entries), "cues_renamed": renamed, "problems": problems}, ensure_ascii=False))
    return 1 if problems else 0

if __name__ == "__main__":
    raise SystemExit(main())
