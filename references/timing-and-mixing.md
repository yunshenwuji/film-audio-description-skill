# Timing and dialogue-safe mixing

## Build a speech-aware timeline

Combine reliable subtitle timings, ASR, voice activity, waveform inspection, and listening. ASR text may be wrong; use it to locate speech, then verify important lines by ear or subtitle. Mark dialogue, breaths that belong to a line, narratively important effects, music transitions, and intentional silence. Add modest guard margins around dialogue boundaries, normally about 150–300 ms, then adjust by listening rather than treating the margin as law.

For each cue, record the visual-event time, available slot, actual synthesized file, measured audible start/end (silence trimmed), voice/rate, nearby dialogue/effects, overlap permission, placement decision, and temporal displacement. Derive overlap from the audible interval intersected with subtitle/VAD/dialogue intervals; never trust a hand-written `nearby_dialogue: false`. A gap is usable only when narration plus natural entry/exit fits; do not force a cue into numeric silence if it clips a syllable, laugh, gasp, door slam, reveal sting, or other meaningful sound.

## Placement order

Run `scripts/optimize_placement.py PROJECT_DIR` to execute the move → shorten → rate part of this order deterministically on the merged draft; it records every attempt in `placement_attempts` and writes `qc/placement-optimisation.json`. Splitting (step 3) is a semantic judgment — it is only performed by the coordinator when two visual moments genuinely support two cues, applied through `scripts/continuity_editor.py`, and never invented automatically. Try these options in order:

1. Place the cue in a genuine nearby gap while keeping it close enough to the visual event. A cue displaced more than 5 seconds from its event (15 for location changes and title credits) must carry `displacement_justification` describing the documented conflict.
2. Rewrite to retain subject + concrete action and remove lower-priority detail.
3. Split only when two visual moments naturally support two cues.
4. Increase speech rate modestly after measuring the actual voice; stay within the approved maximum.
5. If the user permits limited overlap, overlap only the least important portion of dialogue or ambience and record why it was necessary.

For an overlap, store every attempted move/rewrite/split/rate result. “Necessary overlap” without failed earlier attempts is not sufficient. Build `timeline/dialogue-events.json`; mark names, numbers, first identifications, clues, punchlines, whispers, emotional lines, commands, and scene-critical lines as `protected`. Protected dialogue cannot overlap narration unless the user explicitly approves that exact exception during review.

Never cover a character's first identification, key name/number, punchline, whispered clue, emotional confession, command that drives action, or line needed to understand the next scene. Avoid starting narration and dialogue on the same instant. If an approved overlap is unavoidable, prefer a dialogue tail or redundant phrase, keep the original speech intelligible, and review the mixed result by listening—not waveform alone. User permission for “limited overlap” is not blanket permission to narrate across dialogue.

## Gain automation and ducking

Use the narration's actual audible envelope—not the whole export duration—as the sidechain/control signal. Apply smooth automation or compression only around narration: a useful starting point is about 300 ms attack, 650 ms release, and light reduction near a 3:1 ratio. Tune by listening. The aim is separation, not suppression: the source dialogue, music, and effects remain recognizable beneath narration.

Outside narration plus its short transition tails, source gain is exactly unity. Do not lower the whole film, do not duck because dialogue is absent, and do not let padded control silence hold the compressor open. Route narration audibly to the final mix as well as separately to the control path. Keep source, narration master, control envelope, and mixed output separable for revision.

Export the actual duck envelope with `duck_start`, `narration_audible_start/end`, `duck_end`, and `unity_restored_at` for each cue. Bound attack/release by the selected settings; joined tails may not create continuous attenuation between cues unless narration itself is continuous. Measure non-narration regions against source to catch permanent or overlong reduction.

## Dialogue-protection verification

Listen to every cue that overlaps or sits within one second of dialogue, every rate over `+25%`, every cue dense with proper names/numbers, plus samples from ordinary cues. Record cue ID, listened interval, reviewer, result, required change, and successful re-listen after change. Compare source and mix at the beginning, middle, and end. Confirm that words remain understandable, effects retain their function, narration is audible, and source returns to unity. A checklist written by the producing model is not a completed human/user listening approval; unresolved required listening keeps QC incomplete. Move or rewrite a failing cue; stronger ducking is not the default fix.
