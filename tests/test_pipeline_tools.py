import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).parents[1]

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

def run(*args, expect=0):
    result = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    assert result.returncode == expect, (result.returncode, result.stdout, result.stderr)
    return result

def cue(segment, index, start, text, duration=2.4):
    return {"id": f"{segment}-cue-{index:03d}", "start": start, "text": text,
            "duration": duration, "review_duration": duration,
            "visual_event_time": start, "visual_event_type": "action",
            "temporal_displacement": 0, "observation_ids": [f"{segment}-obs-{index:04d}"],
            "evidence_frames": [start], "evidence_ids": [], "atomic_facts": [
                {"role": "subject", "text": "人", "priority": "required"},
                {"role": "action", "text": "动作", "priority": "required"}]}

class PipelineToolTests(unittest.TestCase):
    def make_segments(self, root):
        for segment, start in (("segment-001", 0), ("segment-002", 60)):
            write(root / f"segments/{segment}/manifest.json",
                  {"segment_id": segment, "start": start, "end": start + 60, "status": "drafted"})
            write(root / f"segments/{segment}/observations.json",
                  {"observations": [{"id": f"{segment}-obs-{i:04d}", "start": start + i * 10,
                   "end": start + i * 10 + 2, "subject": "人", "action": "动作", "location": "地点",
                   "evidence_frames": [start + i * 10], "evidence_ids": [], "evidence_type": "visual",
                   "sound_sufficient": False, "dialogue_support_only": True, "confidence": 0.9,
                   "uncertainty": None} for i in range(1, 4)]})
            write(root / f"segments/{segment}/draft-cues.json",
                  {"cues": [cue(segment, 1, start + 10, "第一句旁白。"), cue(segment, 2, start + 30, "第二句旁白。")]})

    def test_merge_draft_adds_derivation_and_guards_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_segments(root)
            run(str(SKILL / "scripts/merge_draft.py"), str(root))
            merged = json.loads((root / "script/merged-draft.json").read_text(encoding="utf-8"))
            self.assertEqual(len(merged["cues"]), 4)
            self.assertEqual(merged["cues"][0]["derivation"],
                             {"segment": "segment-001", "cue_id": "segment-001-cue-001"})
            self.assertFalse(merged["merged_edits"])
            merged["merged_edits"] = True
            write(root / "script/merged-draft.json", merged)
            result = run(str(SKILL / "scripts/merge_draft.py"), str(root), expect=1)
            self.assertIn("merged_edits", result.stderr)
            run(str(SKILL / "scripts/merge_draft.py"), str(root), "--force")
            self.assertFalse(json.loads((root / "script/merged-draft.json").read_text(encoding="utf-8"))["merged_edits"])

    def test_converge_mask_first_prevents_variant_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_segments(root)
            run(str(SKILL / "scripts/merge_draft.py"), str(root))
            merged = json.loads((root / "script/merged-draft.json").read_text(encoding="utf-8"))
            merged["cues"][0]["subject_character_ids"] = ["chr-003"]
            merged["cues"][0]["text"] = "花衬衫男人把赤膊男子推出门口。"
            merged["cues"][0]["visual_event_time"] = 2000
            merged["cues"][0]["start"] = 2000
            # cue 1: two referenced characters with substring-colliding labels, plus an absorbed provisional id
            merged["cues"][1]["subject_character_ids"] = ["pr-021", "chr-008"]
            merged["cues"][1]["text"] = "花衬衫男人拉住衬衫男人。"
            merged["cues"][1]["visual_event_time"] = 2000
            merged["cues"][1]["start"] = 2000
            write(root / "script/merged-draft.json", merged)
            write(root / "bible/characters.json", {"characters": []})
            identity = {"characters": [
                {"id": "chr-003", "canonical_name": "莫三妹", "safe_label": "花衬衫男人",
                 "label_variants": ["花衬衫男子"], "resolution_status": "confirmed",
                 "narration_allowed_after": 1850.0, "aliases": [], "merge_ids": ["pr-021"],
                 "name_evidence": [{"type": "spoken_address", "start": 1, "end": 2, "source_text": "三妹",
                                    "observation_ids": ["segment-001-obs-0001"], "evidence_frames": [1.0], "confidence": 0.9}],
                 "person_binding": [{"method": "continuity", "observation_ids": ["segment-001-obs-0001"], "evidence_frames": [1.0], "confidence": 0.9}],
                 "evidence_sources_checked": ["production_srt"]},
                {"id": "chr-007", "canonical_name": None, "safe_label": "赤膊男子",
                 "resolution_status": "unresolved_after_evidence_review",
                 "unresolved_reason": "无姓名证据", "uncertainty_item_id": "u-1",
                 "narration_allowed_after": 999999, "evidence_sources_checked": ["production_srt"]},
                {"id": "chr-008", "canonical_name": "老王", "safe_label": "衬衫男人",
                 "resolution_status": "confirmed", "narration_allowed_after": 0.0,
                 "name_evidence": [{"type": "spoken_address", "start": 1, "end": 2, "source_text": "老王",
                                    "observation_ids": ["segment-001-obs-0001"], "evidence_frames": [1.0], "confidence": 0.9}],
                 "person_binding": [{"method": "continuity", "observation_ids": ["segment-001-obs-0001"], "evidence_frames": [1.0], "confidence": 0.9}],
                 "evidence_sources_checked": ["production_srt"]}]}
            write(root / "qc/identity-map.json", identity)
            run(str(SKILL / "scripts/converge_identities.py"), str(root), str(root / "qc/identity-map.json"),
                "--blocks", "0-120")
            result = json.loads((root / "script/merged-draft.json").read_text(encoding="utf-8"))
            text0 = result["cues"][0]["text"]
            # chr-003 rewritten to canonical (allowed at 1850), chr-007's label masked and preserved
            self.assertIn("莫三妹", text0)
            self.assertIn("赤膊男子", text0)
            cue1 = result["cues"][1]
            # global masking: 花衬衫男人 -> 莫三妹, 衬衫男人 -> 老王, pr-021 absorbed into chr-003
            self.assertEqual(cue1["text"], "莫三妹拉住老王。")
            self.assertEqual(cue1["subject_character_ids"], ["chr-003", "chr-008"])
            convergence = json.loads((root / "qc/identity-convergence.json").read_text(encoding="utf-8"))
            self.assertIn("review_ranges", convergence)

    def test_optimize_placement_moves_cue_off_dialogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_segments(root)
            run(str(SKILL / "scripts/merge_draft.py"), str(root))
            write(root / "timeline/dialogue-events.json", {"events": [
                {"id": "d1", "kind": "speech", "start": 10, "end": 13, "provenance": "srt", "source_ids": ["s1"]},
                {"id": "d2", "kind": "speech", "start": 30, "end": 33, "provenance": "srt", "source_ids": ["s1"]}]})
            result = run(str(SKILL / "scripts/optimize_placement.py"), str(root))
            self.assertIn('"moved": 2', result.stdout)
            merged = json.loads((root / "script/merged-draft.json").read_text(encoding="utf-8"))
            for c in merged["cues"]:
                if c.get("placement_attempts"):
                    self.assertTrue(any(a.get("rule") == "先找无对白空档" for a in c["placement_attempts"]))

    def test_segment_brief_writes_compact_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_segments(root)
            write(root / "segments/segment-001/work-package.json", {
                "segment_id": "segment-001", "start": 0, "end": 60, "overlap_before": 0, "overlap_after": 20,
                "shots": [{"id": "s1", "start": 0, "end": 60}],
                "transcript_context": [{"id": 1, "start": 10, "end": 12, "text": "对白"}],
                "bible_snapshot": {"characters": {"characters": [{"id": "c1", "safe_label": "红衣男子"}]},
                                   "locations": {"locations": []}, "objects": {"objects": []}, "story-state": {}},
                "evidence": [{"id": "segment-001-ev-0001", "timestamp": 0,
                              "path": "segments/segment-001/evidence/frame-0001-0000000000ms.jpg",
                              "sha256": "a" * 64}]})
            result = run(str(SKILL / "scripts/segment_brief.py"), str(root), "segment-001")
            self.assertIn('"evidence": 1', result.stdout)
            brief = (root / "segments/segment-001/brief.md").read_text(encoding="utf-8")
            self.assertIn("## 场景表", brief)
            self.assertNotIn("a" * 64, brief)

    def test_merge_bible_collect_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "segments/segment-001/bible-proposals.json", {"characters": [
                {"provisional_id": "pr-1", "safe_label": "红衣男子", "first_visual_appearance": 10}]})
            run(str(SKILL / "scripts/merge_bible.py"), "collect", str(root))
            candidates = json.loads((root / "qc/bible-candidates.json").read_text(encoding="utf-8"))
            self.assertIn("segment-001/pr-1", candidates["characters"])
            write(root / "qc/bible-map.json", {"characters": [{"id": "c1", "safe_label": "红衣男子", "aliases": ["pr-1"]}]})
            run(str(SKILL / "scripts/merge_bible.py"), "apply", str(root), str(root / "qc/bible-map.json"))
            bible = json.loads((root / "bible/characters.json").read_text(encoding="utf-8"))
            self.assertEqual(bible["characters"][0]["id"], "c1")

    def test_continuity_editor_matches_cues_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_segments(root)
            run(str(SKILL / "scripts/merge_draft.py"), str(root))
            write(root / "qc/continuity-edits.json", [
                {"action": "rewrite", "cue_id": "segment-002-cue-001", "text": "改写后的第二段。", "reason": "跨段连贯"}])
            run(str(SKILL / "scripts/continuity_editor.py"), str(root), str(root / "qc/continuity-edits.json"))
            merged = json.loads((root / "script/merged-draft.json").read_text(encoding="utf-8"))
            target = next(c for c in merged["cues"] if c["id"] == "segment-002-cue-001")
            self.assertEqual(target["text"], "改写后的第二段。")
            self.assertTrue(merged["merged_edits"])

    def test_shorten_text_strips_trailing_units(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("optimize_placement", SKILL / "scripts/optimize_placement.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.shorten_text("王磊夺过火石，转身冲向舱门。", 6), "王磊夺过火石")
        self.assertEqual(module.shorten_text("王磊夺过火石。", 2), "王磊夺过火石")

if __name__ == "__main__":
    unittest.main()
