import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).parents[1]

PREPARE_SPEC = importlib.util.spec_from_file_location("prepare_segment", SKILL / "scripts/prepare_segment.py")
PREPARE = importlib.util.module_from_spec(PREPARE_SPEC)
PREPARE_SPEC.loader.exec_module(PREPARE)

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

class SegmentToolTests(unittest.TestCase):
    def test_prepare_packages_existing_evidence_and_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); media = root / "movie.mp4"; media.write_bytes(b"movie")
            write(root / "project.json", {"source_media": str(media), "preferences": {"density": "medium"}})
            write(root / "timeline/scenes.json", {"scenes": [{"id": "s1", "start": 0, "end": 10}]})
            write(root / "timeline/transcript.json", {"segments": [{"id": 1, "start": 3, "end": 4, "text": "对白"}]})
            for name, value in (("characters", []), ("locations", []), ("objects", []), ("story-state", {})):
                write(root / f"bible/{name}.json", value)
            evidence = root / "segments/segment-001/evidence"
            evidence.mkdir(parents=True)
            # start, midpoint, and near-end timestamps chosen by the packager
            for index, millis in enumerate((0, 5000, 9950), 1):
                (evidence / f"frame-{index:04d}-{millis:010d}ms.jpg").write_bytes(f"frame-{index}".encode())
            subprocess.run([sys.executable, str(SKILL / "scripts/prepare_segment.py"), str(root), "segment-001",
                "--start", "0", "--end", "10", "--max-gap", "20", "--reuse-evidence"], check=True)
            package = json.loads((root / "segments/segment-001/work-package.json").read_text(encoding="utf-8"))
            self.assertEqual(package["shots"][0]["id"], "s1")
            self.assertEqual(package["transcript_context"][0]["text"], "对白")
            self.assertEqual(len(package["evidence"]), 3)
            self.assertEqual(package["bible_snapshot"]["characters"], {"characters": []})
            self.assertTrue((root / "segments/segment-001/analysis-input.json").is_file())

    def test_prepare_rejects_non_segment_naming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); media = root / "movie.mp4"; media.write_bytes(b"movie")
            write(root / "project.json", {"source_media": str(media)})
            write(root / "timeline/scenes.json", {"scenes": [{"id": "s1", "start": 0, "end": 10}]})
            result = subprocess.run([sys.executable, str(SKILL / "scripts/prepare_segment.py"), str(root), "seg-01",
                "--start", "0", "--end", "10"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("segment-NNN", result.stderr)

    def test_prepare_force_removes_orphaned_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); media = root / "movie.mp4"; media.write_bytes(b"movie")
            write(root / "project.json", {"source_media": str(media)})
            write(root / "timeline/scenes.json", {"scenes": [{"id": "s1", "start": 0, "end": 10}]})
            write(root / "timeline/transcript.json", {"segments": []})
            evidence = root / "segments/segment-001/evidence"
            evidence.mkdir(parents=True)
            for index, millis in enumerate((0, 5000, 9950), 1):
                (evidence / f"frame-{index:04d}-{millis:010d}ms.jpg").write_bytes(b"x")
            subprocess.run([sys.executable, str(SKILL / "scripts/prepare_segment.py"), str(root), "segment-001",
                "--start", "0", "--end", "10", "--max-gap", "20", "--reuse-evidence"], check=True)
            # second run over a shorter range: 2500/4950ms frames pre-created, stale 5000/9950 frames must go
            for index, millis in enumerate((0, 2500, 4950), 1):
                (evidence / f"frame-{index:04d}-{millis:010d}ms.jpg").write_bytes(b"y")
            subprocess.run([sys.executable, str(SKILL / "scripts/prepare_segment.py"), str(root), "segment-001",
                "--start", "0", "--end", "5", "--max-gap", "20", "--reuse-evidence", "--force"], check=True)
            names = sorted(p.name for p in evidence.glob("frame-*.jpg"))
            self.assertEqual(names, ["frame-0001-0000000000ms.jpg", "frame-0002-0000002500ms.jpg",
                                     "frame-0003-0000004950ms.jpg"], names)

    def test_finalize_expands_compact_analysis_and_computes_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); segment = root / "segments/segment-001"
            write(segment / "work-package.json", {"segment_id": "segment-001", "start": 0, "end": 60,
                "overlap_before": 0, "overlap_after": 20, "shots": [{"id": "s1"}],
                "evidence": [{"id": "ev-1", "timestamp": 10, "path": "x.jpg", "sha256": "x", "source_media_id": "m"}],
                "transcript_context": [{"id": 7, "start": 11, "end": 13, "text": "对白"}]})
            write(segment / "analysis-input.json", {"segment_id": "segment-001", "observations": [{
                "local_id": "o1", "evidence_ids": ["ev-1"], "subject": "女人", "action": "关门",
                "location": "走廊", "confidence": .9, "subject_character_ids": ["c1"]}],
                "cues": [{"observation_ref": "o1", "text": "女人关门。", "start": 10, "review_duration": 3}],
                "bible_proposals": {"characters": [], "locations": [], "objects": [], "story_state": {}}})
            subprocess.run([sys.executable, str(SKILL / "scripts/finalize_segment.py"), str(root), "segment-001"], check=True)
            cues = json.loads((segment / "draft-cues.json").read_text(encoding="utf-8"))["cues"]
            self.assertEqual(cues[0]["computed_dialogue_overlaps"], ["7"])
            for name in ("manifest.json", "observations.json", "draft-cues.json", "evidence-index-proposal.json", "bible-proposals.json"):
                self.assertTrue((segment / name).is_file(), name)

    def test_finalize_passes_displacement_justification_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); segment = root / "segments/segment-001"
            write(segment / "work-package.json", {"segment_id": "segment-001", "start": 0, "end": 60,
                "overlap_before": 0, "overlap_after": 20, "shots": [{"id": "s1"}],
                "evidence": [{"id": "ev-1", "timestamp": 10, "path": "x.jpg", "sha256": "x", "source_media_id": "m"}],
                "transcript_context": []})
            write(segment / "analysis-input.json", {"segment_id": "segment-001", "observations": [{
                "local_id": "o1", "evidence_ids": ["ev-1"], "subject": "女人", "action": "关门",
                "location": "走廊", "confidence": .9}],
                "cues": [{"observation_ref": "o1", "text": "女人关门。", "start": 25, "review_duration": 3,
                          "visual_event_time": 10, "displacement_justification": "开场音乐需要完整保留，只能后移"}],
                "bible_proposals": {"characters": [], "locations": [], "objects": [], "story_state": {}}})
            subprocess.run([sys.executable, str(SKILL / "scripts/finalize_segment.py"), str(root), "segment-001"], check=True)
            cue = json.loads((segment / "draft-cues.json").read_text(encoding="utf-8"))["cues"][0]
            self.assertEqual(cue["temporal_displacement"], 15.0)
            self.assertEqual(cue["displacement_justification"], "开场音乐需要完整保留，只能后移")

    def test_prepare_retry_renames_final_sample_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); media = root / "movie.mp4"; media.write_bytes(b"movie")
            write(root / "project.json", {"source_media": str(media)})
            write(root / "timeline/scenes.json", {"scenes": [{"id": "s1", "start": 0, "end": 10}]})
            write(root / "timeline/transcript.json", {"segments": []})
            counts = {}
            def fake_run(cmd, check=True, **kwargs):
                if cmd[0] == "ffprobe":
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                ts = cmd[cmd.index("-ss") + 1]
                counts[ts] = counts.get(ts, 0) + 1
                if ts == "9.950000" and counts[ts] == 1:
                    raise subprocess.CalledProcessError(1, cmd)
                out = Path(cmd[-1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"frame:" + ts.encode())
                return subprocess.CompletedProcess(cmd, 0, "", "")
            with mock.patch.object(PREPARE.subprocess, "run", side_effect=fake_run):
                with mock.patch.object(sys, "argv", ["prepare_segment.py", str(root), "segment-001",
                                                     "--start", "0", "--end", "10", "--max-gap", "20"]):
                    PREPARE.main()
            package = json.loads((root / "segments/segment-001/work-package.json").read_text(encoding="utf-8"))
            last = package["evidence"][-1]
            self.assertEqual(last["timestamp"], 9.45)
            frame = root / "segments/segment-001/evidence/frame-0003-0000009450ms.jpg"
            self.assertTrue(frame.is_file())
            self.assertEqual(last["sha256"], hashlib.sha256(b"frame:9.450000").hexdigest())

if __name__ == "__main__":
    unittest.main()
