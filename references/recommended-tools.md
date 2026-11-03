# Recommended toolchain

These are practical recommendations, not hard dependencies. Equivalent local, cloud, commercial, or open-source tools are acceptable when they produce the required timestamps, visual evidence, natural speech, or validated media output. Record the selected tools and versions in the project QC report.

## Bundled workflow tools

- `scripts/prepare_segment.py`: default for selecting segment shots, slicing transcript context, extracting and hashing evidence frames, and creating the work package. Enforces the `segment-NNN` naming convention, clamps near-end samples below the last decodable frame, and removes orphaned frames on `--force` rebuilds.
- `scripts/finalize_segment.py`: default for expanding compact agent analysis into canonical observations, cues, evidence proposals, manifests, and bible proposals while computing dialogue intersections. Passes `displacement_justification` through and warns on over-displaced cues.
- `scripts/segment_brief.py`: compact agent brief (scene table, dialogue timeline, bible summary, sha-free evidence index) so agents do not parse work-package JSON.
- `scripts/contact_sheet.py`: labeled contact sheets via Pillow; avoids FFmpeg `drawtext`/`pattern_type glob` portability traps.
- `scripts/merge_draft.py`: builds the canonical `script/merged-draft.json` from segment cues with per-cue `derivation`; refuses to overwrite an edited draft.
- `scripts/converge_identities.py`: applies the coordinator's identity map, absorbs provisional ids, rewrites labels with the mask-first order, and emits `qc/identity-convergence.json` (single range or `review_ranges` blocks).
- `scripts/optimize_placement.py`: executes move → shorten → rate placement order and records attempts.
- `scripts/continuity_editor.py`: applies auditable rewrite/delete/move edits, matched by cue id.
- `scripts/merge_bible.py`: `collect` gathers segment bible proposals, `apply` writes the coordinator's map to canonical bible files.
- `scripts/render_review_srt.py`: creates the review SRT and evidence map from merged cues.
- `scripts/audit_project.py`: enforces evidence, identity, review, mix, and no-ad-hoc-code gates.

These tools exist so coordinating and segment agents spend their context on watching, reasoning, and writing. Do not replace them with per-segment Python, PowerShell, shell, or batch scripts. Extend a bundled tool with tests when a recurring capability is genuinely missing.

## Media inspection, extraction, and mixing

**Recommended:** FFmpeg and FFprobe.

Use FFprobe to enumerate programs, video/audio/subtitle tracks, codecs, frame rate, sample rate, channel layout, duration, and language metadata. Use FFmpeg to extract a 16 kHz mono analysis track, keyframes/contact sheets, clips for difficult action, a narration master, and the final mix.

Preserve the video stream with stream copy when compatible with the output container. Use a temporary output and verify it before promotion. FFmpeg filters such as `sidechaincompress`, `amix`, `adelay`, `asplit`, and `alimiter` are useful, but explicitly verify signal routing: the narration bus must feed both the audible mix and the ducking controller.

## Windows console notes

- The bundled scripts print UTF-8 JSON; on Windows consoles with a legacy code page, set `PYTHONIOENCODING=utf-8` (or `PYTHONUTF8=1`) before running them. The scripts also reconfigure stdout/stderr to UTF-8 themselves, and `--report` outputs are unaffected because reports are written as UTF-8 files.
- FFmpeg on Windows commonly lacks `pattern_type glob` support, and `drawtext` can segfault when fontconfig is missing. Prefer the bundled Pillow-based `scripts/contact_sheet.py` (Pillow >= 11, Python >= 3.11; Pillow 13.x is current) over drawtext-based contact sheets, and pass explicit frame lists instead of glob patterns.
- The auditor caches material/evidence hashes by mtime+size in `qc/hash-cache.json`, so re-auditing a multi-gigabyte source does not re-read it every run.

## Speech transcription and voice activity

**Recommended local transcriber:** Faster-Whisper.

Request word timestamps, known source language when reliable, and VAD filtering. For Chinese content, a medium or larger model generally improves names and sentence boundaries, while smaller models reduce CPU/GPU cost. Treat transcription as evidence, not truth: correct names, homophones, speakers, and terminology against subtitles, visuals, and the character bible.

**Alternatives:** OpenAI speech-to-text APIs, Whisper implementations, platform subtitle extraction, or another ASR system that supplies dependable segment or word timestamps.

Use a separate VAD system when the transcriber does not expose speech regions. Absolute silence detection alone is not a dialogue detector because films often contain continuous music and ambience.

## Scene and shot detection

**Recommended lightweight options:** FFmpeg's scene-change filter or PySceneDetect.

Use scene detection to propose boundaries and keyframes, then revise boundaries around dialogue and action continuity. Do not split a feature film into rigid equal durations without checking scenes. Fixed-interval sampling is useful for a film-wide overview but must be supplemented around fast action, object transfers, entrances, edits, and uncertain events.

## Visual understanding

**Recommended:** a capable multimodal model that accepts ordered images or short video clips.

Provide timestamped frames in temporal order. Use sparse sampling for stable dialogue scenes and denser frames or short-video analysis for fights, chases, gestures, object exchanges, camera reveals, and cause-and-effect actions. Ask the model for structured observations before polished narration.

No single model needs to ingest an entire feature film at once. Combine deterministic scene/shot processing, contact sheets, short clips, and a shared film bible.

## Natural speech synthesis

**Recommended accessible prototype tool:** Microsoft Edge TTS via the `edge-tts` Python package.

Suggested Mandarin voices:

- `zh-CN-XiaoyiNeural`: lively delivery suited to animation, comedy, and family material.
- `zh-CN-XiaoxiaoNeural`: warmer, steadier delivery suited to drama and documentary.

Measure the actual generated audio duration. Use adaptive speech rate, normally within `+10%` to `+40%`; rewrite rather than accelerating beyond that. Cache narration by voice, rate, and text so timing or mixing changes do not require unnecessary regeneration.

**Alternatives:** Azure AI Speech, another natural neural TTS provider, a licensed studio voice, or user-supplied narration. Confirm licensing, redistribution terms, account requirements, and network availability for the chosen provider. Do not fall back to an obviously synthetic operating-system voice when the user requested natural speech.

## Subtitle and on-screen text support

Prefer embedded or sidecar subtitles when present, but verify their timing and wording. Recommended extraction tools include FFmpeg/FFprobe and subtitle-specific utilities appropriate to the format. For burned-in text, use OCR only as supporting evidence and visually verify plot-critical messages, signs, dates, or names.

## Quality control

**Recommended:** FFprobe plus the included `audit_cues.py` and `verify_output.py`.

Also use FFmpeg loudness/volume analysis or an equivalent audio meter to inspect clipping, narration level, source audibility during narration, and unity source level outside narration. Container and stream checks alone cannot prove that narration is actually audible. Sample cue and non-cue intervals from the final rendered audio.
