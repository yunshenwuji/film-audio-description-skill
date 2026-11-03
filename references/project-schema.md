# Project layout and schemas

Use this layout when producing a film project:

```text
project/
  project.json
  media/probe.json
  materials/manifest.json
  materials/subtitles/source.srt
  materials/character-references/
  timeline/transcript.json
  timeline/scenes.json
  timeline/candidate-slots.json
  timeline/dialogue-events.json
  timeline/visual-evidence.json
  timeline/title-credit-events.json
  bible/characters.json
  bible/locations.json
  bible/objects.json
  bible/story-state.json
  segments/segment-001/manifest.json
  segments/segment-001/work-package.json
  segments/segment-001/analysis-input.json
  segments/segment-001/observations.json
  segments/segment-001/draft-cues.json
  script/merged-draft.json
  script/review.srt
  script/review-map.json
  script/approved.json
  narration/cues/
  narration/narration-master.wav
  qc/uncertainty-report.json
  qc/identity-convergence.json
  qc/timeline-audit.json
  qc/listening-review.json
  qc/duck-envelope.json
  qc/final-report.json
  qc/hash-cache.json
  qc/merge-report.json
  qc/placement-optimisation.json
  qc/continuity-pass.json
  qc/bible-candidates.json
  output/
```

`project.json` records source path, detected media facts, preferences, current script version, approval version, per-batch approvals, stage, and output choices. Stages are `initialized`, `preferences_confirmed`, `media_analyzed`, `segments_analyzed`, `script_drafted`, `awaiting_user_review`, `script_approved`, `narration_generated`, `mixed`, `quality_checked`, and `complete`. `awaiting_user_review` means the current version is not yet approved; `approved_script_version` must identify a real approved merged artifact. Merged-draft coverage must equal the union of completed segments. An empty segment directory is never evidence of completed work.

Segment directories must be named `segment-NNN` (`segment-001`, `segment-00` ...). `prepare_segment.py` and `finalize_segment.py` reject other names, and `audit_project.py` only discovers `segments/segment-*`.

`script/merged-draft.json` is the canonical script artifact (schema_version 2). `merge_draft.py` builds it from segment cues; every cue carries `derivation: {"segment": ..., "cue_id": ...}` so the auditor can prove the merged script resolves to real segment artifacts. `render_review_srt.py`, `converge_identities.py`, `optimize_placement.py`, and `continuity_editor.py` all read the merged draft; editing tools set `merged_edits: true` and a plain `merge_draft.py` run refuses to overwrite an edited draft, preventing obsolete labels from resurrecting from segment files. Segment artifacts stay untouched evidence inputs — there is no write-back step, and cues are always matched by id, never by sorted position.

`materials/manifest.json` records every supplied/generated artifact with type, path, SHA-256, provenance (`user`, `production`, `embedded`, or `generated`), trust level, intended use, validation result, conflicts, and which expensive step was skipped. A supplied SRT replaces full ASR only after encoding, duration, synchronization, and sampled text checks. Character references require an explicit label/role manifest; unlabeled images remain unidentified.

`script/approved.json` is independent evidence, not a project flag. It contains script version, SHA-256 of the exact merged artifact and exact review SRT, approval time, and a reference to the verbatim user message. Recompute both hashes before TTS and mixing. Omission and protected-overlap approvals reference this or another immutable approval record; an agent-authored paraphrase is invalid.

Minimum cue fields:

```json
{
  "id": "cue-0001",
  "start": 137.0,
  "text": "一个蓝色手电筒从坡上滚落。",
  "observation_ids": ["obs-0042"],
  "evidence_frames": [136.8, 137.4, 138.1],
  "reason": "重要物品首次出现",
  "confidence": 0.98,
  "requires_user_review": false,
  "placement_class": "A",
  "available_slot": {"start": 136.7, "end": 139.2},
  "computed_dialogue_overlaps": [],
  "overlap_permission": "none_needed",
  "placement_decision": "dialogue-free gap",
  "visual_event_time": 137.0,
  "temporal_displacement": 0.0,
  "displacement_justification": null,
  "atomic_facts": [
    {"role": "subject", "text": "蓝色手电筒", "priority": "required"},
    {"role": "action", "text": "滚落", "priority": "required"}
  ],
  "placement_attempts": [],
  "voice": null,
  "rate": null,
  "duration": null
}
```

Minimum observation fields:

```json
{
  "id": "obs-0042",
  "start": 136.8,
  "end": 138.1,
  "subject": "蓝色手电筒",
  "action": "从坡上滚落",
  "object": null,
  "location": "山坡",
  "evidence_frames": [136.8, 137.4, 138.1],
  "evidence_type": "visual",
  "sound_sufficient": false,
  "dialogue_support_only": true,
  "confidence": 0.98,
  "uncertainty": null
}
```

Evidence frames are numeric, ordered, within media and observation bounds, and tied to real extracted frames/contact-sheet cells. Continuous actions require distinct beginning/process/result frames. Reusing identical evidence for unrelated observations of the SAME subject is a failure; one frame that shows several subjects (a man at the door, a child on the bed) may legitimately support one observation per subject — prefer extracting a dedicated frame per subject when possible. A coverage observation with `sound_sufficient: true` still records visible subject/state, why the image is stable, what sound conveys, at least one frame, and cannot cross a shot change, entrance/exit, or meaningful action. It must not generate narration.

`timeline/visual-evidence.json` indexes every cited frame with a stable ID, exact timestamp, extracted image path, SHA-256, and source-media artifact ID. Observation/cue `evidence_ids` resolve to this index, and their declared timestamps agree with the indexed timestamps. Numeric timestamps without extracted evidence do not satisfy the gate.

Character records include ID, canonical name, aliases, visual description, voice notes, first visual appearance, first spoken line, reveal time, safe pre-reveal name, safe post-reveal name, reference asset IDs, and screen-track binding evidence.

In addition to `safe_label`, a character may carry `label_variants`: the alternative neutral labels segment agents actually wrote (e.g. safe_label 花衬衫男人 with variants 花衬衫男子、背心男子). Variants must be at least three normalized characters and not generic terms (男子、女人、孩子); `converge_identities.py` enforces this and rewrites cues with a mask-first order (all other characters' labels are masked before a referenced character's labels are replaced) so variant collisions such as 蓝袍男子/黄袍男子 or a stray 赤膊男子 can never be rewritten into the wrong person. After convergence, no cue may still contain a registered variant — the auditor warns on leftovers.

Character records include separate `name_evidence` and `person_binding`: type, start/end, observed/source text, transcript/subtitle provenance and IDs, linked observation/frame IDs, binding steps, confidence, and conflicts. They also record `production_known_at`, `narration_allowed_after`, first spoken line, and first naming cue. Actor recognition or outside knowledge may be an unconfirmed lead, never confirmation.

Every merged character uses one `id`; `provisional_id` is segment-agent input only and cannot remain in the review-ready bible. `merge_bible.py collect/apply` gathers segment proposals and applies the coordinator's map, and `converge_identities.py` absorbs provisional records listed in `merge_ids` into the canonical record, rewrites cue `subject_character_ids` to canonical ids, and drops `provisional_id`; the auditor rejects residual provisional ids in the bible and any cue referencing a non-canonical id. Repeated IDs or repeated safe labels are merged unless `distinct_person_evidence` proves they are different people. `qc/identity-convergence.json` covers the current review range and lists every character that appears there with `character_id`, merged source IDs/aliases, `resolution_status`, evidence sources checked, and cue IDs. Legal statuses are `confirmed`, `not_yet_revealed`, and `unresolved_after_evidence_review`. The last status also requires `unresolved_reason` and an `uncertainty_item_id`. For a full-film single batch, the report may use `review_ranges` sub-blocks whose union covers the batch instead of one monolithic `review_range`.

`first_spoken_line_time` is established from film-local evidence: reliable subtitle speaker labels, on-screen mouth-movement binding, reaction/gaze continuity, or a credit pairing actor and role. Under `character_naming: first_speech_once`, principal characters (canonical name, a first naming cue, or three or more cues) must either have the field or carry a `speech_evidence_reviewed` record (with `evidence_sources_checked`) or an uncertainty item — silent omission is an audit failure, not a waiver.

Every cue involving a person includes `subject_character_ids`. After a character becomes narration-allowed, a cue may use the canonical name or a natural pronoun/group reference, but must not use that character's obsolete `safe_label`. The first naming cue and first spoken line remain explicitly tracked.

`work-package.json` and its transcript/shot/bible snapshots are generated by `prepare_segment.py`. `analysis-input.json` is the only normal segment-agent-authored file. It deliberately contains a compact semantic schema; `finalize_segment.py` expands it into `manifest.json`, `observations.json`, `draft-cues.json`, `evidence-index-proposal.json`, and `bible-proposals.json`. Files ending in `.py`, `.ps1`, `.sh`, `.bat`, `.cmd`, or executable binaries do not belong in segment directories. A user/production-supplied project tool is an exception only when its exact path and hash are registered as `authorized_project_tool` in `materials/manifest.json`.

When opening/end-title description is selected, `timeline/title-credit-events.json` stores exact scope enum, media end, checked opening/ending ranges, inspection evidence, raw detections, and curated events. Every raw detection is retained or linked to an exclusion reason. Each event records type, interval, exact displayed text, OCR confidence, evidence, and either matching cue IDs or an omission approval record. Empty results require evidence. Checked ending range reaches the final frame — this holds for every scope, including `opening_only`, so the ending is provably bounded even when only opening events are narrated. `visible_text` contains only the narration-readable line (for bilingual cards, the Chinese line) and its normalized form must appear as a substring of the cue text. `cue_ids` is a list: one narration cue may cover several simultaneously displayed cards (e.g. stacked job titles), which is the only way overlapping credit cards avoid narrating over each other.

`timeline/dialogue-events.json` contains verified speech intervals and provenance; protected events include their reason. Synthesized cues add actual audio path, measured duration and audible interval. The auditor computes intersection rather than accepting overlap claims. `qc/listening-review.json` accounts for every required listening item and re-listen. `qc/duck-envelope.json` records automation and return-to-unity times.

`qc/final-report.json` includes reproducible audio measurements: source/output artifact hashes, commands or method, sampled intervals, source and output levels, tolerance, narration-presence measurements at cue locations, and source-presence measurements beneath narration. Assertions without measurements do not complete QC.

The primary review artifact is `script/review.srt`, the production review interchange. Each entry contains only proposed spoken narration, sequential indices, and `HH:MM:SS,mmm --> HH:MM:SS,mmm` timing. Its end is the proposed narration end (measured after TTS, otherwise an explicit estimate), not the visual-observation end. Never put reasons, confidence, IDs, or editorial notes in spoken SRT text.

`script/review-map.json` maps every SRT index to cue ID, script version, evidence, uncertainty, placement class, estimated/measured timing, and review status. Generate both deterministically with `scripts/render_review_srt.py`. If the user edits SRT, reconcile it into a new cue version before approval, preserve the reviewed file, and invalidate the old hash. The auditor requires SRT, map, and merged cues to agree in order, timing, and text.

Review-stage interlocks the auditor enforces (all derive from `project.json`, `review-map.json`, and `qc/identity-convergence.json`):

- `awaiting_user_review` requires `current_review_batch.start/end` in project.json.
- The convergence report's `review_range` (or the union of `review_ranges` blocks) must match the batch range within 0.05 seconds.
- `review-map.json` `script_version` must equal project.json `script_version`; SRT, map entries, and merged cues must have identical counts, order, ids, text, and timing.
- Every merged cue's `derivation` must resolve to a segment cue id, and every segment cue must appear in the merged draft.

Bible files use one top-level shape: an object with the plural key (`{"characters": [...]}`, `{"locations": [...]}`, `{"objects": [...]}`, `{"story-state": {...}}`). `init_project.py` and `merge_bible.py` write this shape; `prepare_segment.py` normalizes snapshots to it; the audit `rows()` reader still accepts a bare list for legacy projects.

Scene-table entries are analysis units of roughly 20–60 seconds (a continuous action or dialogue beat, not every shot and not whole sequences). Granularity is a coordinator decision because it sets the effective observation floor: every scene needs at least one observation, while the per-segment density gate asks at least one observation per minute — the tighter of the two binds. The auditor warns (`scene_table_too_fine`) when the average scene is under 15 seconds.

Cues displaced more than 5 seconds from their visual event (15 for location changes and title credits) must carry `displacement_justification` describing the documented conflict that forced the move; `finalize_segment.py` passes the field through and warns when it is missing.
