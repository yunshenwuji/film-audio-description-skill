# Interactive intake

Ask no more than five short questions at a time. Give a recommended option and explain only the material tradeoff. Do not repeat already confirmed preferences.

## Round 0: supplied materials

First list discovered materials and ask only about ambiguous provenance or intended use. Accept media alone, or any combination of external SRT/ASS/VTT, dialogue scripts, cast-role lists, character/costume reference photos, speaker maps, shot lists, existing descriptions, and production notes.

- Reliable external SRT: use it as the primary dialogue/timing source after sampled synchronization and text checks. Do not run full ASR merely to recreate it; use ASR/VAD only for gaps, doubtful regions, or speech boundaries.
- Character photos plus a cast-role manifest: use them as a candidate gallery. Record image-to-name provenance, then verify the on-screen binding through visual continuity and film-local evidence. A filename alone is not proof.
- Unlabeled photos: ask who/what they represent or keep them as unknown references; never infer a canonical name from a face alone.
- Conflicts: the film is authoritative for timing and visible events. Report conflicts among film, SRT, cast list, photos, and transcript instead of silently choosing.

## Round 1: writing

1. **Delivery form** (ask first): script only, or full production with narration and mix. Script-only projects skip Round 2's voice, overlap, and ducking questions and initialize with script outputs (`init_project.py --script-only`).
2. **Description density**: medium-detailed (recommended), concise, or detailed. Medium-detailed covers characters, locations, important actions, plot-relevant expressions, and objects without narrating every visible item.
3. **Character naming**: name once before first speech (recommended), repeat after scene changes, or only when voices are confusing. A scene-setting cue that already names the character satisfies first identification.
4. **Expressions**: only plot-relevant or marked changes (recommended), minimal, or detailed.
5. **Reveal policy**: preserve the film's reveal order (recommended). Never use model or actor recognition to reveal a concealed identity early.
6. **Opening and ending titles/credits**: opening companies/title/all opening credits plus principal ending cast/crew (recommended); opening only; all ending cast; complete ending roll; user-specified names/roles; or skip. Store the exact enum and any named selection. If selected, it is binding; never reinterpret “ending” as merely saying that credits roll. Every scope — including opening only — still requires the ending to be checked through the final frame (to bound the media and prove nothing opening-like appears at the end); only the opening events are narrated under that scope.

## Round 2: audio and review

1. **Voice**: recommend by genre; offer the user's previous voice first when known.
2. **Dialogue overlap**: limited overlap (recommended), avoid where possible, or prohibit.
3. **Ducking during narration**: light with source clearly audible (recommended), medium, or strong. Duck only when narration speaks. With no narration, preserve the source at its original level regardless of whether the source contains dialogue, music, effects, ambience, or silence. Describe perceived sound rather than compressor jargon.
4. **Outputs**: mixed film plus script; or recommend mixed film, narration master, scripts, and QC report for serious production. Skip this question when the user chose script-only delivery in Round 1.
5. **Review**: for over 30 minutes recommend roughly 20-minute batches plus final merged approval; otherwise one full-script review. A single full-film batch is allowed, but identity convergence then covers every character appearing anywhere in the film at once — for a large cast, convergence may be split into sub-range blocks whose union covers the batch.

Ask whether to save choices as defaults only after the user chooses them. Do not silently promote a per-film choice to a durable preference.

## Adaptive questions

- Multiple audio tracks: ask which source track to use.
- Reliable subtitles: explain they replace redundant full transcription after synchronization/provenance checks and are not redundantly narrated.
- Foreign-language source: ask whether to retain original dialogue, use a dub track, or read essential on-screen subtitles.
- Existing description track: ask whether to audit, supplement, or rebuild it.
- Silent or music-only work: replace dialogue questions with music and intertitle handling.
