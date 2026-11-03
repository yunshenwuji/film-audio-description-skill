import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_project.py"
SPEC = importlib.util.spec_from_file_location("audit_project", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

def observation(index, start, end=None, sufficient=False):
    finish = end or start + 2
    return {"id": f"obs-{index}", "start": start, "end": finish,
            "subject": "女人", "action": "抬手指向屏幕", "object": "屏幕",
            "location": "控制室", "evidence_frames": [start, start + 1, finish],
            "evidence_ids": [f"frame-{start}", f"frame-{start + 1}", f"frame-{finish}"],
            "evidence_type": "visual", "sound_sufficient": sufficient,
            "dialogue_support_only": True, "confidence": 0.95, "uncertainty": None}

class AuditProjectTests(unittest.TestCase):
    def test_long_observation_interval_does_not_create_false_middle_gap(self):
        gaps = MODULE.clipped_coverage_gaps([(0, 20), (20, 180), (180, 240)], 0, 240)
        self.assertEqual(gaps, [])
        self.assertEqual(MODULE.clipped_coverage_gaps([(0, 20), (180, 240)], 0, 240), [(20, 180)])

    def test_scene_coverage_is_limited_to_current_review_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project["current_review_batch"] = {"id": "b1", "start": 0, "end": 240}
            write(root / "project.json", project)
            observations = [observation(i, t, t + 60) for i, t in enumerate((0, 60, 120, 180), 1)]
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 240, "status": "drafted"})
            write(root / "segments/segment-001/observations.json", {"observations": observations})
            write(root / "segments/segment-001/draft-cues.json", {"cues": []})
            issues = MODULE.audit(root)["issues"]
            uncovered = [item for item in issues if item["type"] == "scene_without_observation_coverage"]
            self.assertFalse(any(item.get("scene") == "s2" for item in uncovered), uncovered)

    def test_review_scope_excludes_prior_batch_and_clips_crossing_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project.update({"media_duration": 480, "current_review_batch": {"id": "b2", "start": 200, "end": 300}})
            write(root / "project.json", project)
            write(root / "timeline/scenes.json", {"scenes": [{"id": "prior", "start": 0, "end": 200},
                  {"id": "crossing", "start": 200, "end": 360}, {"id": "future", "start": 360, "end": 480}]})
            scoped_observation = observation(1, 200, 300)
            write(root / "segments/segment-001/manifest.json", {"start": 200, "end": 300, "status": "drafted"})
            write(root / "segments/segment-001/observations.json", {"observations": [scoped_observation]})
            write(root / "segments/segment-001/draft-cues.json", {"cues": []})
            uncovered = [item for item in MODULE.audit(root)["issues"] if item["type"] == "scene_without_observation_coverage"]
            self.assertEqual(uncovered, [])

    def make_base(self, root):
        write(root / "project.json", {"stage": "script_drafted", "script_version": 1,
              "approved_script_version": None, "media_duration": 480,
              "preferences": {"opening_credits": {"scope": "opening_and_principal_ending"}}})
        media = root / "media/source.mp4"; media.parent.mkdir(parents=True, exist_ok=True); media.write_bytes(b"test-media")
        write(root / "materials/manifest.json", {"artifacts": [{"id": "media-1", "type": "source_media",
              "path": "media/source.mp4", "sha256": hashlib.sha256(b"test-media").hexdigest(),
              "provenance": "user", "trust_level": "primary", "intended_use": "film authority"}],
              "skipped_steps": [], "conflicts": []})
        frame_times = sorted({value for start in (0, 70, 140, 210, 280, 350, 420, 478)
                              for value in (start, start + 1, start + 2)})
        indexed = []
        for value in frame_times:
            path = root / f"media/frames/{value}.jpg"; path.parent.mkdir(parents=True, exist_ok=True)
            payload = f"frame-{value}".encode(); path.write_bytes(payload)
            indexed.append({"id": f"frame-{value}", "timestamp": value, "path": f"media/frames/{value}.jpg",
                            "sha256": hashlib.sha256(payload).hexdigest(), "source_media_id": "media-1"})
        write(root / "timeline/visual-evidence.json", {"frames": indexed})
        write(root / "timeline/scenes.json", {"scenes": [{"id": "s1", "start": 0, "end": 240},
              {"id": "s2", "start": 240, "end": 480}]})
        write(root / "timeline/transcript.json", {"duration": 480, "segments": [
              {"start": 202, "end": 205, "text": "我们马上离开这里"}]})
        for name, value in (("characters", [{"id": "c1", "canonical_name": "李明",
                            "name_evidence": [{"type": "spoken_address", "start": 20, "end": 21,
                              "source_text": "李明", "observation_ids": ["obs-1"], "evidence_frames": [20], "confidence": .95}],
                            "person_binding": [{"method": "response_and_shot_continuity", "observation_ids": ["obs-1"],
                              "evidence_frames": [20], "confidence": .94}], "production_known_at": 20,
                            "narration_allowed_after": 20}]), ("locations", [{"id": "l1"}]),
                            ("objects", [{"id": "o1"}]), ("story-state", {"time": 0})):
            write(root / f"bible/{name}.json", value)
        write(root / "timeline/title-credit-events.json", {"scope": "opening_and_principal_ending",
              "checked_ranges": {"opening": [0, 30], "ending": [450, 480]},
              "inspection_evidence_frames": [0, 15, 450, 479.8],
              "raw_detections": [{"id": "raw-1", "start": 0, "end": 2, "evidence_frames": [1], "event_id": "credit-1"}], "events": [
              {"id": "credit-1", "type": "company_logo", "start": 0, "end": 2,
               "visible_text": "某某影业有限公司", "ocr_confidence": .99,
               "evidence_frames": [1], "cue_ids": ["cue-logo"]}]})

    def test_good_project_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            observations = [observation(i, t) for i, t in enumerate((0, 70, 140, 210, 280, 350, 420, 478), 1)]
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 480, "status": "drafted"})
            write(root / "segments/segment-001/observations.json", {"observations": observations})
            write(root / "segments/segment-001/draft-cues.json", {"cues": [
                  {"id": "cue-logo", "start": 0, "text": "某某影业有限公司。",
                   "observation_ids": ["obs-1"], "evidence_frames": [0, 1, 2],
                   "evidence_ids": ["frame-0", "frame-1", "frame-2"],
                   "visual_event_time": 0, "temporal_displacement": 0,
                   "atomic_facts": [{"role": "subject", "text": "公司名", "priority": "required"},
                                    {"role": "state", "text": "出现", "priority": "required"}]},
                  {"id": "cue-1", "start": 140, "text": "女人抬手指向屏幕。",
                   "observation_ids": ["obs-3"], "evidence_frames": [140, 141, 142],
                   "evidence_ids": ["frame-140", "frame-141", "frame-142"],
                   "visual_event_time": 140, "temporal_displacement": 0,
                   "atomic_facts": [{"role": "subject", "text": "女人", "priority": "required"},
                                    {"role": "action", "text": "抬手指向", "priority": "required"}]}]})
            write(root / "script/merged-draft.json", {"coverage": {"start": 0, "end": 480}, "cues": []})
            report = MODULE.audit(root)
            self.assertTrue(report["passed"], report["issues"])

    def test_bad_project_fails_expected_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "project.json", {"stage": "awaiting_user_review", "script_version": 5,
                  "approved_script_version": 5, "media_duration": 2400})
            write(root / "timeline/scenes.json", {"scenes": [{"id": "s1", "start": 0, "end": 1200}]})
            write(root / "timeline/transcript.json", {"duration": 2400, "segments": [
                  {"start": 400, "end": 406, "text": "救援行动失败"}]})
            for name, value in (("characters", []), ("locations", []), ("objects", []), ("story-state", {})):
                write(root / f"bible/{name}.json", value)
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 1200, "status": "drafted"})
            write(root / "segments/segment-001/observations.json", {"observations": [
                  {"time": i * 150, "subject": "人", "action": "行动"} for i in range(8)]})
            write(root / "segments/segment-001/draft-cues.json", {"cues": [
                  {"id": "cue-1", "start": 400, "text": "救援行动失败"}]})
            (root / "segments/segment-002").mkdir(parents=True)
            write(root / "script/merged-draft.json", {"coverage": {"start": 0, "end": 600}, "cues": []})
            report = MODULE.audit(root)
            kinds = {item["type"] for item in report["issues"]}
            expected = {"all_bibles_empty", "incomplete_scene_coverage", "analysis_segment_too_coarse",
                        "insufficient_observation_density", "cue_without_observation_reference",
                        "suspected_dialogue_restatement", "approval_state_contradiction",
                        "merged_coverage_incomplete", "incomplete_segment_directory"}
            self.assertFalse(report["passed"])
            self.assertTrue(expected <= kinds, expected - kinds)

    def test_selected_titles_require_inventory_and_cues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            (root / "timeline/title-credit-events.json").unlink()
            report = MODULE.audit(root)
            self.assertIn("missing_title_credit_inventory", {item["type"] for item in report["issues"]})

    def test_fake_title_claim_and_mismatched_cue_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            write(root / "timeline/title-credit-events.json", {"scope_checked": True, "no_matching_events": True, "events": []})
            report = MODULE.audit(root); kinds = {x["type"] for x in report["issues"]}
            self.assertTrue({"opening_range_not_proven", "ending_not_checked_to_final_frame",
                             "title_credit_inspection_without_evidence", "unproven_empty_title_detection"} <= kinds)

    def test_recycled_frames_and_abstract_compression_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            observations = [observation(i, t) for i, t in enumerate((0, 70, 140, 210, 280, 350, 420, 478), 1)]
            observations[1]["evidence_frames"] = observations[0]["evidence_frames"]
            observations[1]["action"] = "打开舱门"
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 480, "status": "drafted"})
            write(root / "segments/segment-001/observations.json", {"observations": observations})
            write(root / "segments/segment-001/draft-cues.json", {"cues": [{"id": "x", "start": 140,
                  "text": "众人开始行动。", "observation_ids": ["obs-3"], "evidence_frames": [140],
                  "evidence_ids": ["frame-140"],
                  "visual_event_time": 140, "temporal_displacement": 0, "atomic_facts": []}]})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertTrue({"recycled_evidence_frames", "cue_missing_required_atomic_facts", "possible_plot_summary"} <= kinds)

    def test_unvalidated_srt_cannot_replace_asr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            subtitle = root / "materials/subtitles/source.srt"; subtitle.parent.mkdir(parents=True, exist_ok=True); subtitle.write_text("x", encoding="utf-8")
            manifest = json.loads((root / "materials/manifest.json").read_text(encoding="utf-8"))
            manifest["artifacts"].append({"id": "sub-1", "type": "srt", "path": "materials/subtitles/source.srt",
                "sha256": hashlib.sha256(b"x").hexdigest(), "provenance": "production", "trust_level": "high",
                "intended_use": "dialogue timing", "replaces_full_asr": True, "validation": {"encoding_checked": True}})
            write(root / "materials/manifest.json", manifest)
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertIn("subtitle_not_validated_for_asr_replacement", kinds)

    def test_character_photo_label_needs_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            photo = root / "materials/character-references/a.jpg"; photo.parent.mkdir(parents=True, exist_ok=True); photo.write_bytes(b"image")
            manifest = json.loads((root / "materials/manifest.json").read_text(encoding="utf-8"))
            manifest["artifacts"].append({"id": "photo-1", "type": "character_photo", "path": "materials/character-references/a.jpg",
                "sha256": hashlib.sha256(b"image").hexdigest(), "provenance": "user", "trust_level": "candidate",
                "intended_use": "identity candidate", "label": "李明"})
            write(root / "materials/manifest.json", manifest)
            self.assertIn("character_reference_label_without_provenance", {x["type"] for x in MODULE.audit(root)["issues"]})

    def test_fake_approval_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project.update({"stage": "script_approved", "approved_script_version": 1})
            write(root / "project.json", project)
            write(root / "script/merged-draft.json", {"coverage": {"start": 0, "end": 0}, "cues": []})
            (root / "script/review.srt").write_text("", encoding="utf-8")
            write(root / "script/approved.json", {"script_version": 1, "script_sha256": "fake",
                  "review_srt_sha256": "fake", "approved_at": "now", "user_message_ref": "message-1",
                  "verbatim_user_approval": "Y"})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertTrue({"approved_script_hash_mismatch", "approved_review_srt_hash_mismatch"} <= kinds)

    def test_generated_stage_computes_protected_overlap_and_requires_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8")); project["stage"] = "narration_generated"
            write(root / "project.json", project)
            write(root / "timeline/dialogue-events.json", {"events": [{"id": "d1", "start": 140, "end": 144,
                  "text": "密码是三二一", "provenance": "production_srt", "source_ids": ["sub-4"],
                  "protected": True, "protection_reason": "key number"}]})
            audio = root / "narration/cues/c1.wav"; audio.parent.mkdir(parents=True, exist_ok=True); audio.write_bytes(b"wav")
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 480, "status": "drafted"})
            observations = [observation(i, t) for i, t in enumerate((0,70,140,210,280,350,420,478),1)]
            write(root / "segments/segment-001/observations.json", {"observations": observations})
            write(root / "segments/segment-001/draft-cues.json", {"cues": [{"id": "c1", "start": 140,
                  "text": "女人指向屏幕。", "observation_ids": ["obs-3"], "evidence_frames": [140,141,142],
                  "evidence_ids": ["frame-140","frame-141","frame-142"], "visual_event_time": 140,
                  "temporal_displacement": 0, "atomic_facts": [{"role":"subject","text":"女人","priority":"required"},
                  {"role":"action","text":"指向","priority":"required"}], "audible_start": 140,
                  "audible_end": 143, "measured_duration": 3, "audio_path": "narration/cues/c1.wav"}]})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertTrue({"protected_dialogue_overlap", "undeclared_computed_dialogue_overlap",
                             "overlap_without_prior_placement_attempts"} <= kinds)

    def test_mixed_and_qc_stage_rejects_long_duck_and_self_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8")); project["stage"] = "quality_checked"
            write(root / "project.json", project)
            write(root / "qc/duck-envelope.json", {"entries": [{"cue_id":"ghost","duck_start":1,
                  "narration_audible_start":2,"narration_audible_end":3,"duck_end":10,"unity_restored_at":10}]})
            write(root / "qc/listening-review.json", {"reviewer_kind":"producing_model",
                  "all_required_items_complete": False, "reviews": []})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertTrue({"self_attested_listening_review", "listening_review_not_closed"} <= kinds)

    def test_review_stage_requires_identity_convergence_and_freezes_future_waves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project.update({"stage": "awaiting_user_review", "current_review_batch": {"id": "b1", "start": 0, "end": 480}})
            write(root / "project.json", project)
            write(root / "bible/characters.json", {"characters": [
                {"provisional_id": "girl-a", "safe_label": "短发女孩", "first_visual_appearance": 100},
                {"id": "girl-b", "safe_label": "短发女孩", "first_visual_appearance": 120}]})
            (root / "segments/segment-002").mkdir(parents=True)
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            expected = {"missing_identity_convergence_report", "provisional_character_in_review_bible",
                        "duplicate_character_safe_label", "future_segment_started_during_review"}
            self.assertTrue(expected <= kinds, expected - kinds)

    def test_ad_hoc_segment_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            tool = root / "segments/segment-001/build_segment.py"; tool.parent.mkdir(parents=True, exist_ok=True)
            tool.write_text("print('mechanical work')", encoding="utf-8")
            issues = MODULE.audit(root)["issues"]
            matches = [item for item in issues if item["type"] == "ad_hoc_segment_tool"]
            self.assertEqual(len(matches), 1)
            self.assertIn("build_segment.py", matches[0]["path"])

    def test_confirmed_character_cannot_keep_obsolete_neutral_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project.update({"stage": "awaiting_user_review", "current_review_batch": {"id": "b1", "start": 0, "end": 480}})
            write(root / "project.json", project)
            character = json.loads((root / "bible/characters.json").read_text(encoding="utf-8"))[0]
            character.update({"safe_label": "红衣年轻人", "narration_allowed_after": 20, "first_visual_appearance": 0})
            write(root / "bible/characters.json", {"characters": [character]})
            write(root / "qc/identity-convergence.json", {"review_range": {"start": 0, "end": 480},
                  "characters": [{"character_id": "c1", "resolution_status": "confirmed",
                  "evidence_sources_checked": ["production_srt"], "cue_ids": ["cue-1"]}]})
            observations = [observation(i, t) for i, t in enumerate((0,70,140,210,280,350,420,478),1)]
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 480, "status": "drafted"})
            write(root / "segments/segment-001/observations.json", {"observations": observations})
            write(root / "segments/segment-001/draft-cues.json", {"cues": [{"id": "cue-1", "start": 140,
                  "text": "红衣年轻人抬手。", "subject_character_ids": ["c1"], "observation_ids": ["obs-3"],
                  "evidence_frames": [140,141,142], "evidence_ids": ["frame-140","frame-141","frame-142"],
                  "visual_event_time": 140, "temporal_displacement": 0, "atomic_facts": [
                  {"role":"subject","text":"李明","priority":"required"},
                  {"role":"action","text":"抬手","priority":"required"}]}]})
            self.assertIn("obsolete_neutral_label_after_identity_reveal", {x["type"] for x in MODULE.audit(root)["issues"]})

    def test_drift_gate_uses_median_and_exempts_credit_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            # segment-00: short, dense, title-credit cues -> exempt from drift baseline
            write(root / "segments/segment-00/manifest.json", {"start": 0, "end": 120, "status": "drafted"})
            write(root / "segments/segment-00/observations.json", {"observations": [observation(i, t, t + 10) for i, t in enumerate((0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110), 1)]})
            write(root / "segments/segment-00/draft-cues.json", {"cues": [{"id": "c0", "start": 0, "text": "某某影业有限公司。",
                  "observation_ids": ["obs-1"], "evidence_frames": [0, 1, 2], "evidence_ids": ["frame-0", "frame-1", "frame-2"],
                  "visual_event_time": 0, "visual_event_type": "title_credit", "temporal_displacement": 0,
                  "atomic_facts": [{"role": "subject", "text": "公司", "priority": "required"}, {"role": "action", "text": "出现", "priority": "required"}]}]})
            # segment-001: narrative with steady density
            write(root / "segments/segment-001/manifest.json", {"start": 120, "end": 480, "status": "drafted"})
            write(root / "segments/segment-001/observations.json", {"observations": [observation(i, t) for i, t in enumerate((140, 210, 280, 350, 420, 478), 1)]})
            write(root / "segments/segment-001/draft-cues.json", {"cues": []})
            # segment-002: sparse narrative; only flagged against the narrative median, not the dense credit unit
            write(root / "segments/segment-002/manifest.json", {"start": 120, "end": 480, "status": "drafted"})
            write(root / "segments/segment-002/observations.json", {"observations": [observation(1, 200)]})
            write(root / "segments/segment-002/draft-cues.json", {"cues": []})
            drift = [x for x in MODULE.audit(root)["issues"] if x["type"] == "possible_summary_drift"]
            self.assertEqual([x["segment"] for x in drift], ["segment-002"], drift)

    def test_same_frames_different_subjects_are_not_recycled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            observations = [observation(i, t) for i, t in enumerate((0, 70, 140, 210, 280, 350, 420, 478), 1)]
            observations[1]["evidence_frames"] = observations[0]["evidence_frames"]
            observations[1]["subject"] = "门口的男人"
            observations[1]["action"] = "回头看向屋内"
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 480, "status": "drafted"})
            write(root / "segments/segment-001/observations.json", {"observations": observations})
            write(root / "segments/segment-001/draft-cues.json", {"cues": []})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertNotIn("recycled_evidence_frames", kinds)

    def test_merged_provenance_and_missing_cues_fail_at_review_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project.update({"stage": "awaiting_user_review", "current_review_batch": {"id": "b1", "start": 0, "end": 480}})
            write(root / "project.json", project)
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 480, "status": "drafted"})
            observations = [observation(i, t) for i, t in enumerate((0, 70, 140, 210, 280, 350, 420, 478), 1)]
            write(root / "segments/segment-001/observations.json", {"observations": observations})
            write(root / "segments/segment-001/draft-cues.json", {"cues": [{"id": "cue-1", "start": 140, "text": "女人抬手指向屏幕。",
                  "observation_ids": ["obs-3"], "evidence_frames": [140, 141, 142], "evidence_ids": ["frame-140", "frame-141", "frame-142"],
                  "visual_event_time": 140, "temporal_displacement": 0, "atomic_facts": [
                  {"role": "subject", "text": "女人", "priority": "required"}, {"role": "action", "text": "抬手指向", "priority": "required"}]}]})
            write(root / "script/merged-draft.json", {"coverage": {"start": 0, "end": 480},
                  "cues": [{"id": "cue-1", "start": 140, "text": "女人抬手指向屏幕。",
                            "derivation": {"segment": "segment-001", "cue_id": "cue-9"}, "duration": 2.4}]})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertIn("merged_cue_provenance_broken", kinds)

    def test_registered_label_variant_in_cue_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project.update({"stage": "awaiting_user_review", "current_review_batch": {"id": "b1", "start": 0, "end": 480}})
            write(root / "project.json", project)
            character = json.loads((root / "bible/characters.json").read_text(encoding="utf-8"))[0]
            character.update({"label_variants": ["红衣男子"], "first_visual_appearance": 0})
            write(root / "bible/characters.json", {"characters": [character]})
            write(root / "qc/identity-convergence.json", {"review_range": {"start": 0, "end": 480},
                  "characters": [{"character_id": "c1", "resolution_status": "confirmed",
                  "evidence_sources_checked": ["production_srt"], "cue_ids": ["cue-1"]}]})
            write(root / "segments/segment-001/manifest.json", {"start": 0, "end": 480, "status": "drafted"})
            observations = [observation(i, t) for i, t in enumerate((0, 70, 140, 210, 280, 350, 420, 478), 1)]
            write(root / "segments/segment-001/observations.json", {"observations": observations})
            write(root / "segments/segment-001/draft-cues.json", {"cues": [{"id": "cue-1", "start": 140,
                  "text": "红衣男子抬手。", "subject_character_ids": ["c1"], "observation_ids": ["obs-3"],
                  "evidence_frames": [140, 141, 142], "evidence_ids": ["frame-140", "frame-141", "frame-142"],
                  "visual_event_time": 140, "temporal_displacement": 0, "atomic_facts": [
                  {"role": "subject", "text": "李明", "priority": "required"}, {"role": "action", "text": "抬手", "priority": "required"}]},
                  {"id": "cue-2", "start": 280, "text": "红衣男子走进巷子。", "observation_ids": ["obs-5"],
                  "evidence_frames": [280, 281, 282], "evidence_ids": ["frame-280", "frame-281", "frame-282"],
                  "visual_event_time": 280, "temporal_displacement": 0, "atomic_facts": [
                  {"role": "subject", "text": "男人", "priority": "required"}, {"role": "action", "text": "走进", "priority": "required"}]}]})
            variants = [x for x in MODULE.audit(root)["issues"] if x["type"] == "cue_contains_label_variant"]
            self.assertEqual(len(variants), 2)
            self.assertTrue(all(x["severity"] == "warning" for x in variants))

    def test_convergence_blocks_union_covers_single_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project.update({"stage": "awaiting_user_review", "current_review_batch": {"id": "b1", "start": 0, "end": 480}})
            write(root / "project.json", project)
            write(root / "qc/identity-convergence.json", {"review_ranges": [
                  {"start": 0, "end": 240}, {"start": 240, "end": 480}],
                  "characters": [{"character_id": "c1", "resolution_status": "confirmed",
                  "evidence_sources_checked": ["production_srt"], "cue_ids": ["cue-1"]}]})
            ranges = [x for x in MODULE.audit(root)["issues"] if x["type"] == "identity_convergence_range_mismatch"]
            self.assertEqual(ranges, [])

    def test_convergence_blocks_with_internal_hole_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project.update({"stage": "awaiting_user_review", "current_review_batch": {"id": "b1", "start": 0, "end": 480}})
            write(root / "project.json", project)
            write(root / "qc/identity-convergence.json", {"review_ranges": [
                  {"start": 0, "end": 100}, {"start": 200, "end": 480}],
                  "characters": [{"character_id": "c1", "resolution_status": "confirmed",
                  "evidence_sources_checked": ["production_srt"], "cue_ids": ["cue-1"]}]})
            mismatches = [x for x in MODULE.audit(root)["issues"] if x["type"] == "identity_convergence_range_mismatch"]
            self.assertEqual(len(mismatches), 1)
            self.assertTrue(mismatches[0].get("holes"))

    def test_nonstandard_segment_directory_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            (root / "segments/seg-01").mkdir(parents=True)
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertIn("nonstandard_segment_directory", kinds)

    def test_principal_character_speech_timing_needs_evidence_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project["preferences"]["character_naming"] = "first_speech_once"
            project["stage"] = "awaiting_user_review"
            project["current_review_batch"] = {"id": "b1", "start": 0, "end": 480}
            write(root / "project.json", project)
            character = json.loads((root / "bible/characters.json").read_text(encoding="utf-8"))[0]
            character.update({"first_visual_appearance": 0})
            write(root / "bible/characters.json", {"characters": [character]})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertIn("character_speech_timing_unestablished", kinds)
            character["speech_evidence_reviewed"] = {"evidence_sources_checked": ["production_srt"], "result": "no_speech_in_range"}
            write(root / "bible/characters.json", {"characters": [character]})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertNotIn("character_speech_timing_unestablished", kinds)

    def test_speech_tier_is_skipped_before_review_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            project = json.loads((root / "project.json").read_text(encoding="utf-8"))
            project["preferences"]["character_naming"] = "first_speech_once"
            write(root / "project.json", project)
            character = json.loads((root / "bible/characters.json").read_text(encoding="utf-8"))[0]
            write(root / "bible/characters.json", {"characters": [character]})
            kinds = {x["type"] for x in MODULE.audit(root)["issues"]}
            self.assertNotIn("character_speech_timing_unestablished", kinds)

    def test_hash_cache_populates_and_reuses_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            cache = {}
            MODULE.audit(root, cache)
            media_key = str((root / "media/source.mp4").resolve())
            self.assertIn(media_key, cache)
            self.assertEqual(cache[media_key]["sha256"], hashlib.sha256(b"test-media").hexdigest())
            first = dict(cache[media_key])
            MODULE.audit(root, cache)
            self.assertEqual(cache[media_key], first)

    def test_fine_scene_table_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make_base(root)
            write(root / "timeline/scenes.json", {"scenes": [
                  {"id": f"s{i}", "start": i * 10, "end": i * 10 + 8} for i in range(48)]})
            warnings = [x for x in MODULE.audit(root)["issues"] if x["type"] == "scene_table_too_fine"]
            self.assertEqual(len(warnings), 1)

if __name__ == "__main__":
    unittest.main()
