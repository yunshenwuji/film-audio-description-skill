---
name: film-audio-description
description: Interactively analyze films, create reviewable time-coded Chinese audio-description scripts, and only after user approval synthesize narration, mix it with the original soundtrack, and verify the finished video. Use for short or feature-length audio-description production, script review, or remastering existing descriptions.
---

# Film Audio Description

Create accessible audio description as a staged, reviewable production. Never treat a visual caption dump as a finished script. Preserve the film's dialogue, sound design, suspense, character continuity, and the user's control over the final mix.

## Start interactively

Inventory all supplied materials before analysis: media, embedded/external subtitles, scripts, cast lists, character sheets, costume/reference photos, existing description tracks, and production notes. Report what each artifact can replace or only assist. With a reliable external SRT, skip redundant full ASR and verify/correct its timing and text by sampling; with cast references, build candidate identities but still bind each reference person to the on-screen track. With media alone, perform transcription and film-local identity discovery. The film remains the final authority when materials conflict. Then read [references/intake-questionnaire.md](references/intake-questionnaire.md) and ask the adaptive questionnaire.

Create a project with `scripts/init_project.py`. Record decisions and stage in `project.json`. Do not infer permission to process unrelated files or publish copyrighted media.

Read [references/recommended-tools.md](references/recommended-tools.md) when choosing the production toolchain. The listed tools are recommendations, not mandatory dependencies; prefer an already available equivalent when it meets the same observable requirements.

## Choose the production path

- For a short work up to about 30 minutes, one agent may analyze it end to end.
- For a longer work, read [references/long-film-orchestration.md](references/long-film-orchestration.md). Use scene-aware batches, shared structured state, overlap context, and subagents when delegation is available and authorized. Subagents write only their assigned segment artifacts; the coordinating agent owns the film-wide bible and final script.
- For script-only work, stop after reviewable script delivery.
- For an existing script or described track, preserve it and perform the requested review or revision rather than rebuilding automatically.

Before visual analysis, read [references/writing-rules.md](references/writing-rules.md). Maintain canonical character, location, object, and reveal-state records. Identify characters from film-local evidence, never actor recognition or prior plot knowledge alone. Build structured visual observations before writing prose; every normal cue must cite observation IDs and evidence timestamps. Read [references/anti-summary-quality-gates.md](references/anti-summary-quality-gates.md) for long works or whenever a draft risks becoming plot summary.

Use the bundled segment tools for mechanical work. Segment directories must be named `segment-NNN` (e.g. `segment-001`); `prepare_segment.py` and `finalize_segment.py` enforce the pattern and `audit_project.py` discovers segments with it. The coordinator runs `scripts/prepare_segment.py` to package shots, transcript context, current bible, and extracted evidence. A segment agent analyzes those materials and edits only the compact `analysis-input.json`; it does not write Python, PowerShell, shell, batch files, FFmpeg commands, hashing code, or schema-building utilities. The coordinator runs `scripts/finalize_segment.py` to produce canonical artifacts and compute overlaps. If a needed reusable capability is missing, stop that segment and improve the skill-level tool once; do not improvise a per-segment program.

`script/merged-draft.json` is the canonical script artifact: `scripts/merge_draft.py` builds it from segment cues (each cue carries its `derivation`), `scripts/converge_identities.py`, `scripts/optimize_placement.py`, and `scripts/continuity_editor.py` apply edits to it, and `scripts/render_review_srt.py` renders review files from it. Segment files stay as untouched evidence inputs; there is no write-back step. Companion tools `scripts/segment_brief.py` and `scripts/contact_sheet.py` produce compact agent briefs and labeled contact sheets, and `scripts/merge_bible.py` consolidates bible proposals.

Treat questionnaire choices as requirements. If the user chooses opening/end-title description, inventory those events across both ends of the media and write the requested logo, title, and credit cues; do not silently omit them.

Do not satisfy schemas with self-authored assertions. Coverage, identity, dialogue overlap, omissions, listening checks, and approvals require the evidence artifacts defined in [references/project-schema.md](references/project-schema.md). An agent's statement that it checked or that the user approved is not evidence.

## Draft and review

Generate machine-readable cues plus a standard SRT review file. Follow [references/project-schema.md](references/project-schema.md). Keep uncertainty, evidence, and editorial notes in companion JSON/QC artifacts rather than polluting spoken SRT text. Flag uncertain identities, illegible screen text, ambiguous actions, likely spoilers, and low-confidence speaker assignments.

Before presenting each review batch, run `scripts/audit_project.py`. Treat missing or recycled visual evidence, dialogue restatement, incomplete scene coverage, empty continuity records, title/credit omissions, weak identity binding, or analysis-density drift as drafting failures to correct, not minor warnings to defer.

Before generating a review SRT, the coordinator must run identity convergence for every character appearing in that batch: `scripts/converge_identities.py` merges duplicate provisional records, inspects available name evidence, binds confirmed identities, enforces reveal timing, and rewrites cues that still use obsolete neutral labels (masking all other characters' labels first so variants cannot collide). An unresolved identity is allowed only with a documented evidence review and user-facing uncertainty item; “leave it for later” is not a resolution. Every character-bearing cue cites canonical character IDs.

For films over 30 minutes, normally deliver review batches of roughly 20 minutes, incorporating user corrections before drafting later batches. A single full-film batch is allowed, but then identity convergence may be split into sub-range blocks (`review_ranges`) whose union covers the batch, so 40+ characters are not forced into one convergence pass. After all batches, run `scripts/optimize_placement.py` (move, shorten, then rate), apply a film-wide continuity pass with `scripts/continuity_editor.py`, and deliver the merged script for final review.

`awaiting_user_review` is a real pause. Do not create, dispatch, or analyze any segment beyond the current review batch until the user approves it or supplies corrections and the coordinator updates the bible/work packages.

### Mandatory approval gate

After writing or materially changing the script, set the stage to `awaiting_user_review` and stop production. Tell the user how to request changes and that `Y` will approve the current version. Accept other unambiguous approval language such as “开始混音” or “按这个制作”; ask a brief confirmation for ambiguous replies.

Do not batch-synthesize narration, mix audio, or create the final deliverable until the current script version is explicitly approved. Any addition, deletion, or meaning-changing rewrite invalidates approval. Purely mechanical timing shifts or modest rate changes do not.

Capture approval as a separate record containing the verbatim user approval reference and SHA-256 of both the exact review SRT the user saw and its matching merged cue artifact. Never manufacture approval from project state. If the user edits SRT, import it as a new cue/SRT/map version and review that version; never mix directly from an un-reconciled edit. Any hash mismatch or missing approval record blocks synthesis. Re-render review files whenever the merged draft changes, and never rebuild the merged draft from segments with `merge_draft.py` after it carries edits (`merged_edits: true` guards against it).

## Synthesize and mix after approval

Use a natural neural voice. Default Chinese recommendations are `zh-CN-XiaoyiNeural` for animation, comedy, and family material, and `zh-CN-XiaoxiaoNeural` for restrained drama or documentary, unless the user chose otherwise. Measure real generated duration for every cue. Prefer shortening prose over exceeding `+40%` speech rate.

Read [references/timing-and-mixing.md](references/timing-and-mixing.md). Use `scripts/audit_cues.py` before mixing. Narration cues must not overlap each other. Limited overlap with source dialogue is allowed only according to the user's preference and after placement, shortening, and measured-rate options have been considered. Keep an independent narration master so the mix can be revised without regenerating speech.

Apply ducking only while narration is actually audible. Outside narration intervals the source soundtrack must remain at its original level; never apply a permanent base reduction merely because the film has no dialogue. A short release tail after a cue is only a smooth transition back to unity, not permission to keep non-narrated sections attenuated. Default ducking is light and smooth: approximately 300 ms attack, 650 ms release, weak compression near 3:1, and clearly audible source audio under narration. Treat the timing and strength as recommended starting values, but treat narration-gated ducking and unity gain outside it as invariants.

Render to a temporary `.partial` output. Never let concurrent renders write the same target. Only replace the final deliverable after validation succeeds.

## Verify and hand off

Read [references/quality-control.md](references/quality-control.md). Run `scripts/verify_output.py` and meaningful audio checks. Confirm the narration is actually routed into the final mix, the source remains audible, duration and ending are intact, streams are valid, and no partial render is presented as finished.

Deliver the mixed video, independent narration track, review SRT, machine-readable cue file, uncertainty report, and QC report when those outputs were requested.
