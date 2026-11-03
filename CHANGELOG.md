# Changelog

[简体中文](CHANGELOG.zh-CN.md) | English

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

## [0.6.0] - 2026-11-03

### Added

- Added merge_draft.py: builds the canonical `script/merged-draft.json` from segment cues with per-cue `derivation`, coverage union, cue-overlap detection, and a `merged_edits` guard against silent rebuilds.
- Added converge_identities.py: applies the coordinator's identity map, absorbs provisional ids, rewrites labels with the mask-first order, registers guarded `label_variants`, and emits `qc/identity-convergence.json` (single `review_range` or `review_ranges` blocks whose union covers the batch).
- Added optimize_placement.py: executes the move → shorten → rate placement order on the merged draft and records every attempt.
- Added continuity_editor.py: applies auditable rewrite/delete/move edits matched by cue id, never by sorted position.
- Added contact_sheet.py: Pillow-based labeled contact sheets (avoids FFmpeg `drawtext`/`pattern_type glob` portability traps).
- Added segment_brief.py: compact sha-free agent briefs from work packages.
- Added merge_bible.py: `collect`/`apply` consolidation of segment bible proposals into canonical bible files.
- Added `--script-only` to init_project.py (script-only outputs, no TTS/mix defaults) and a delivery-form question to the intake questionnaire.
- Added hash caching (mtime+size, `qc/hash-cache.json`) to audit_project.py so multi-gigabyte sources are not re-hashed every run.
- prepare_segment.py now validates `segment-NNN` ids, clamps near-end samples below the last decodable frame (ffprobe), retries the final sample, removes orphaned frames on `--force` rebuilds, and normalizes bible snapshots to the object-with-key shape.
- finalize_segment.py now validates segment ids, passes `displacement_justification` through, and warns on over-displaced cues.
- All bundled scripts reconfigure stdout/stderr to UTF-8 for Windows consoles.

### Changed

- `script/merged-draft.json` is now the canonical script artifact: the auditor checks dialogue restatement, summary drift, displacement, title/credit matching, identity labels, and review-file alignment against the merged cues, while segment files remain the untouched evidence layer. Merged cues must carry `derivation` provenance.
- The density-drift gate now uses the median of narrative segments and exempts opening/end-title credit segments.
- Recycled-evidence detection now flags only same-subject re-use; one frame may support one observation per subject.
- `first_speech_once` mode now requires principal characters to establish `first_spoken_line_time` or record `speech_evidence_reviewed`; silent omission is an audit failure.
- Registered `label_variants` left in cue text produce audit warnings; generic or short variants are rejected at convergence.
- Bible files use one top-level shape (`{"characters": [...]}` ...); init/merge_bible write it, prepare normalizes it, the audit still reads legacy lists.
- Convergence reports may split a single review batch into `review_ranges` blocks whose union covers the batch (contiguously — internal holes now fail the audit).
- Review-stage audit errors now include repair hints; a `scene_table_too_fine` warning guards over-fine scene tables.
- Contract changes for downstream consumers: audit reports move to `schema_version: 3`, and all bundled scripts reconfigure stdout/stderr to UTF-8 (set `PYTHONIOENCODING=utf-8` for subprocess consumers on legacy code pages).
- optimize_placement.py executes move → shorten → rate; splitting is a coordinator decision applied through continuity_editor.py, never automatic.
- The first-speech identity tier (`character_speech_timing_unestablished`) is enforced at review stages only.

### Fixed

- Segment directories named outside `segment-*` no longer silently skip the segment audit — the tools reject the naming at packaging time.
- Merged-draft edits no longer require a fragile write-back step or fail `review_srt_text_or_id_mismatch`.
- `displacement_justification` is now expressible end to end instead of existing only in the auditor.
- Orphaned evidence frames from denser re-preparation are removed instead of polluting glob-based consumers.
- Final-sample extraction no longer crashes FFmpeg's mjpeg encoder at end of stream.
- A dense 2-minute title unit no longer inflates the film-wide drift baseline and forces padded coverage records on ending credits.
- Fixed the final-sample retry path writing to the old filename and then reading a nonexistent path; the retried frame is now renamed before indexing.
- Fixed mask-first label rewriting corrupting referenced characters when their labels are substrings of each other (e.g. 衬衫男人/花衬衫男人); all labels are now masked globally, longest first.
- Fixed absorbed provisional ids surviving in cue `subject_character_ids`; convergence now rewrites them to canonical ids.
- Fixed merge_bible `apply` overwriting canonical bible files before orphan validation completed; validation now precedes all writes.
- Fixed the convergence-range gate accepting blocks with internal holes, and the auditor now reports nonstandard segment directories instead of silently ignoring them.
- Fixed hash-cache entries ignoring ctime, rate adjustments leaving `review_duration`/`available_slot` stale, and contact-sheet indexes ignoring `--timestamps` overrides.

### Validation

- Expanded the suite with pipeline-tool tests (merge provenance, mask-first convergence, placement order, briefs, bible merge, continuity edits) and new audit-gate tests (median drift, same-frame different-subject, provenance, variants, convergence blocks, speech tiering, hash cache, fine scene tables).

## [0.5.0] - 2026-11-01

### Added

- Added prepare_segment.py to select shots, slice transcript context, snapshot the bible, extract and hash evidence frames, and create ready-to-analyze work packages.
- Added finalize_segment.py to expand compact agent analysis into canonical manifests, observations, cues, evidence proposals, and bible proposals while calculating dialogue intersections.
- Added analysis-input.json as the only normal segment-agent-authored artifact.
- Added mandatory per-batch identity convergence with confirmed, not_yet_revealed, and unresolved_after_evidence_review outcomes.
- Added canonical subject_character_ids on character-bearing cues.

### Changed

- Neutral character labels are now analysis scaffolding only. Review-ready scripts use canonical names after the permitted reveal, or expose unresolved identity to the user.
- Coordinators merge duplicate provisional IDs, aliases, safe labels, and evidence tracks before generating review SRT.
- awaiting_user_review now freezes later work packages and analysis waves until approval or corrections are incorporated.
- Segment agents now focus on watching and writing instead of creating FFmpeg, hashing, schema, or JSON-builder scripts.
- Coverage audits are clipped to the active review batch; without one, they use completed segment coverage.
- Observation-gap detection now merges real start/end intervals before finding uncovered time.

### Fixed

- Fixed review-batch audits checking scenes outside the active batch.
- Fixed long observations being mistaken for gaps because only their start points were compared.
- Fixed confirmed characters retaining obsolete neutral labels after their narration-allowed reveal.
- Fixed duplicate/provisional character records surviving into review-ready bibles.
- Fixed agents creating one-off code inside segment directories; unregistered executables now fail project audit.

### Validation

- Expanded the suite to 19 passing tests, including segment-tool, identity, review-scope, crossing-scene, and long-interval regressions.

## [0.4.0] - 2026-11-01

### Added

- Made standard SRT the primary review artifact, with deterministic rendering and a companion evidence map.
- Added material-aware paths for media-only projects, validated subtitles, cast-role manifests, scripts, and character or costume references.
- Added material provenance and hashes, a hashed visual-evidence index, approval records, dialogue events, listening review, duck envelopes, and reproducible audio measurements.
- Added project-wide auditing for evidence integrity, scene coverage, dialogue similarity, summary drift, bible readiness, merged coverage, and state consistency.

### Changed

- Validated external SRT can replace redundant full ASR; cast references accelerate but do not replace on-screen identity binding.
- Approvals bind both the exact reviewed SRT and matching merged cue artifact.
- Dialogue overlap is computed from measured narration-audible intervals.
- Final QC requires listening, duck-envelope, and source/output measurements instead of container checks alone.

### Fixed

- Prevented arbitrary timestamps, recycled frames, unvalidated subtitles, unlabeled photos, self-authored approvals, and self-attested listening from passing as evidence.

## [0.3.0] - 2026-11-01

### Added

- Added dialogue-safe placement and mixing rules, slot-aware Chinese compression, film-local identity evidence, and binding opening/ending credit coverage.
- Added title/credit inventories for company names, film titles, actor-role pairs, and crew credits.

### Changed

- Placement now tries nearby gaps, rewriting, semantic splitting, and measured rate adjustment before limited overlap.
- Names, numbers, clues, punchlines, whispers, emotional lines, and action-driving commands are protected.

### Fixed

- Prevented selected title/credit coverage from being silently omitted, outside knowledge from establishing identity, and long duck tails from becoming permanent attenuation.

## [0.2.0] - 2026-11-01

### Added

- Added evidence-first observations, cue-to-evidence links, anti-summary gates, and deterministic project auditing.
- Added scene-aware 8–15 minute analysis segments distinct from roughly 20-minute review batches.
- Added coverage, dialogue-restatement, summary-language, density-drift, bible, merged-coverage, empty-segment, and approval-state checks.

### Fixed

- Prevented sparse visual sampling plus noisy ASR from degrading into plot summaries.
- Prevented audible broadcasts, mission plans, and causal exposition from being repeated as narration.
- Prevented fixed review batches from becoming coarse analysis units.

## [0.1.0] - 2026-10-31

### Added

- Initial open-source interactive film audio-description skill.
- Added adaptive intake, short/feature-film paths, structured projects, long-film orchestration, and mandatory user approval before TTS or mixing.
- Added natural neural voice recommendations, adaptive rate, independent narration masters, cue/output checks, temporary renders, and narration-gated ducking with unity source gain outside narration.
- Added bilingual documentation, MIT licensing, installation instructions, and a recommended production toolchain.

Note: the initial public release was not tagged; formal release tags begin with v0.2.0.

[0.5.0]: https://github.com/wangru2025/film-audio-description-skill/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/wangru2025/film-audio-description-skill/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/wangru2025/film-audio-description-skill/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/wangru2025/film-audio-description-skill/releases/tag/v0.2.0
[0.1.0]: https://github.com/wangru2025/film-audio-description-skill/commit/b45d22a
