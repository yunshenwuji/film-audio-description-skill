# Quality control

## Before approval

- Every cue is supported by visible evidence and does not reveal future knowledge.
- Every cue cites valid observation IDs and frame timestamps; `sound_sufficient` observations produce no cue.
- The cue adds visible information rather than restating nearby dialogue, subtitles, broadcasts, or plans.
- The scene table spans the full film, observations cover every scene, and unexplained gaps or later-segment density collapse have been resolved. Scene-table granularity (20–60 second analysis units) is a recorded coordinator decision; the effective observation floor is the tighter of one observation per scene and one per minute per segment.
- Continuity bibles have been merged (`scripts/merge_bible.py collect/apply`) before later segment work begins.
- Character names have film-local identity evidence and respect reveal order.
- The current batch has a completed identity-convergence report (`scripts/converge_identities.py`, possibly with `review_ranges` blocks whose union covers the batch). No duplicate/provisional character records remain; every appearing character is confirmed, deliberately not yet revealed, or explicitly unresolved after evidence review. Character cues reference canonical IDs, and obsolete neutral labels — including registered `label_variants` — do not survive past the allowed naming point.
- If opening/end-title description was selected, the title/credit inventory covers the chosen scope through the final frame and every event has a cue or approved omission. Company logos use the displayed company name; cast pairings use “演员名饰角色名”.
- Canonical names, locations, and objects are consistent.
- Low-confidence claims are listed for review.
- `script/review.srt`, `script/review-map.json`, and the merged script cues have identical order, spoken text, and review timing. SRT contains no editorial notes. The merged draft (`script/merged-draft.json`) is the canonical script artifact; every cue's `derivation` resolves to a segment cue, segment files are untouched evidence inputs, and a `merge_draft.py` rebuild is refused once the draft carries edits.
- Supplied-material provenance and hashes are recorded. A trusted SRT or labeled reference gallery replaces redundant analysis only after validation passes; conflicts remain visible.
- `scripts/audit_project.py` passes its hard gates; investigate its similarity and summary-drift findings even when a heuristic needs human judgment. The density-drift gate applies to narrative segments only (median baseline); title/credit segments are held to the title/credit coverage gates. Material and evidence hashes are cached by mtime+size (`qc/hash-cache.json`).
- `awaiting_user_review` has frozen later waves: no future segment directory, manifest, observation, cue, or work package has been created beyond the current review range.
- Segment directories contain analysis artifacts, not ad hoc code. Mechanical evidence extraction, hashing, transcript slicing, ID assignment, overlap calculation, and schema expansion were performed by the bundled tools.
- Scene intervals are ordered and continuously cover the media; observations cannot manufacture density with recycled, out-of-range, or nonexistent frames. Every cited frame resolves to a hashed extracted image in the visual-evidence index. Adjacent cues are reviewed together for distributed plot summary.

## After synthesis

- Record actual duration, voice, and rate for every cue.
- Compute audible intervals from rendered narration and intersect them with verified dialogue events. Missing duration/audio metadata blocks mixing.
- No narration-to-narration overlaps.
- Rates above `+40%` require rewriting instead.
- Meaning-changing rewrites invalidate approval; mechanical timing/rate adjustments do not.

## Mix

- Keep a separate narration master.
- Use smooth light ducking by default; source remains clearly audible.
- Duck the source only while narration is audibly active. When no narration is speaking, source gain must be unity. Source dialogue activity is irrelevant: a music-only or dialogue-free passage is not a reason to lower the source.
- Allow only the configured attack/release transition around a narration cue. After the release tail, verify that the source returns to its pre-narration level.
- Narration is routed both to the audible mix and, separately, to ducking control. Never use an audible bus only as a sidechain.
- Pad only the silent sidechain control when needed. The padded zero signal must not trigger compression or change source level, and source audio must not truncate when the last cue ends.
- One render owns one temporary target. Rename to final only after checks pass.
- Every cue within one second of dialogue is listened to in the mix. Key names, numbers, clues, punchlines, emotional lines, and action-driving commands remain intelligible; failed overlaps are moved or rewritten before increasing ducking.
- Export and audit the duck envelope; attack/release tails cannot become continuous attenuation between cues.
- Store measured source/output level comparisons for representative non-narration intervals before, between, and after cues, plus source/narration presence measurements during cues. A boolean “unity verified” without interval, command/method, measured values, tolerance, and source/output artifact hashes is not evidence.

## Final verification

- Output duration matches source within the allowed tolerance and contains the complete ending.
- Expected video and audio streams exist and decode.
- Narration is audibly present at sampled cue locations; absence is a failure even if the stream exists.
- Source is audibly present beneath sampled narration.
- At sampled non-narration locations before, between, and after cues, output source level matches the unducked source within the chosen encoding/limiting tolerance.
- No clipping, corrupt container, abandoned process, or `.partial` file is delivered.
- Required listening records must be complete; a manual-check reminder is not a pass. Provide a QC report with commands, results, deviations, and unresolved issues.
