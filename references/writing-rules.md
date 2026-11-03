# Audio-description writing rules

## Core sentence shape

Prefer **subject + action**, adding object or consequence when useful: “光头强按下按钮。”“女人把钥匙藏进花盆。” Avoid subjectless ambiguity and decorative prose that consumes time without improving access.

## Fit meaning into the available slot

Start from the indispensable visual change, not from a full sentence that is later trimmed. Rank facts: actor/action and plot-critical object first; direction/result second; appearance and atmosphere only when they change comprehension. Use an already established name instead of repeating clothing or relationships. Prefer one precise verb over a verb plus explanation, delete “正在”“可以看到”“画面中”“这时” and redundant causes, and avoid narrating what dialogue or effects already establish.

Draft in semantic units that may be removed from the end without damaging the core: “王磊夺过火石，转身冲向舱门” can become “王磊夺过火石” when the slot is short. Never compress by dropping the subject or replacing concrete action with a plot-summary label. Measure the chosen TTS voice at the intended rate; do not rely on a fixed characters-per-second estimate. If it does not fit, try in order: move into a nearby safe gap, remove lower-priority facts, split across two genuine visual moments, then modestly increase rate within the approved limit.

Before compression, store atomic facts and mark required facts. A cue must retain the required subject, concrete visible action/state change, and any plot-critical object or result. “众人开始行动”“救援失败”“他们陷入危机” are not acceptable compression because they replace images with abstractions. Audit adjacent cues as a 30–60 second passage: splitting a summary into short sentences does not make it visual description. Record the visual-event time and narration displacement; action and expression cues stay close to the event unless a documented conflict forces movement — a cue displaced more than 5 seconds from its event (15 for location changes and title credits) must carry `displacement_justification` describing that conflict. Rates above `+25%`, proper names, numbers, and dense credits require listening review even when below the absolute `+40%` ceiling.

## Describe when sound alone is insufficient

- Location and meaningful scene changes.
- A character's first identification before first speech.
- Entrances, exits, silent reactions, and who performs an audible action.
- Causal action chains, object transfers, and important object state or location.
- Plot-relevant expressions, especially when they contradict speech or reveal concealed emotion.
- On-screen text needed for the story.
- Montages, time jumps, dreams, memories, surveillance, imagination, or split-screen status.
- Scale, spatial relationships, and fast action that source sound does not establish.

Do not mechanically repeat dialogue, narrate every background object, identify every blink or head turn, or read all end credits unless requested. Preserve important effects, music transitions, and purposeful silence.

Before accepting a cue, ask: **What visible information does this add that the soundtrack does not already convey?** Dialogue, subtitles, transcripts, synopses, franchise knowledge, and model memory may orient analysis, but they are not visual evidence. Do not convert audible mission briefings, broadcasts, plans, causes, or consequences into narration. Describe the visible screen, gesture, action, expression, spatial relationship, object change, or necessary on-screen text instead.

Write observations before cues. A continuing action needs evidence of its beginning, process, and result rather than one isolated still. A normal cue cites the supporting observation IDs and frame timestamps. One frame that shows several subjects may support one observation per subject, but the same subject reusing the same frames for a different action is evidence recycling and fails the audit. If a nonvisual editorial clarification is exceptionally needed, label it explicitly and require user review; never disguise it as observed fact.

## Naming and continuity

Assign canonical character IDs. Name a character once before first speech; do not repeat on every line. Re-identify only after a long absence, severe disguise or costume change, confusing voices, or a discontinuous scene where comprehension requires it.

Determine identity from a film-local evidence chain. Strong evidence includes an on-screen name/title, reliable subtitle speaker label, an unambiguous spoken introduction or address, and a credit explicitly pairing actor and role. Separate **name evidence** from **person binding**: a shouted name does not identify one of several people unless reaction, gaze, action continuity, clothing, face, companions, or voice binds it to that track. Record source text, source IDs, timestamps, observation/frame IDs, subtitle provenance, confidence, conflicts, and the binding steps. A transcript spelling, face recognition, actor familiarity, synopsis, or model memory is only a lead and cannot establish the character by itself. When evidence is incomplete, use a stable neutral label such as “红衣男子”; ask for review rather than guessing.

User-supplied cast photos, costume stills, and cast-role lists are high-value candidate references, not automatic on-screen identity proof. Store every asset's path/hash, supplied label, role, provenance, and trust level. Bind it to a screen track using multiple matching features across frames plus continuity; record ambiguity from similar costumes, age changes, doubles, disguises, animation redesigns, or poor frames. Once a trusted production manifest and visual binding agree, redundant discovery can be skipped. Never identify an unlabeled face from outside recognition alone.

Keep `production_known_at` separate from `narration_allowed_after`. Do not use the canonical name in a cue before `narration_allowed_after`. Credit text shown before a deliberate story reveal may inform production but does not authorize early narration. Track the first spoken line and the first naming cue; when the user chose first-speech naming, the naming cue must precede that line without covering protected dialogue.

Before an identity reveal, use the safe contemporary label such as “蒙面人” or “女医生.” Store the reveal time and switch names only after the film reveals it.

Segment agents will naturally spell the same safe label several ways (“花衬衫男人”“花衬衫的男子”“背心男子”). Record those spellings as `label_variants` on the character record (at least three normalized characters, never a generic term like 男子 or 女人). Identity convergence rewrites them with a mask-first order — every OTHER character's labels are masked before a referenced character's labels are replaced — so overlapping variants (蓝袍男子/黄袍男子) or a stray 赤膊男子 can never be rewritten into the wrong person. Never hand-apply global find-and-replace across the script; it is the single easiest way to corrupt a draft.

`first_spoken_line_time` is established from film-local evidence, not guessed: reliable subtitle speaker labels, an on-screen mouth/gaze/reaction chain, or a credit pairing actor and role. When no such evidence exists for a principal character, record `speech_evidence_reviewed` (what was checked) or raise an uncertainty item — omitting the field silently is a bypass, not a waiver.

Neutral labels are analysis scaffolding, not a permanent writing style. Before review delivery, replace an obsolete label with the canonical name from the first narration-allowed point onward. Do not rewrite earlier cues across a deliberate reveal. Pronouns or “两人” remain natural after identification, but do not repeatedly call a confirmed character “红衣年轻人”“短发女孩” or another provisional label. If identity remains unresolved after a real evidence review, keep one stable safe label and expose the uncertainty to the user.

## Opening, logos, titles, and credits

When the user selected opening/end-title description, inspect the entire opening and ending through the final media frame. Record checked time ranges and evidence frames, keep raw detections separate from the curated inventory, and account for every detection. Every in-scope event must be read or have a version-bound explicit user-approved omission. A bare `scope_checked`, `no_matching_events`, or agent-written omission reason is not evidence.

- For a company or studio logo, read the text actually displayed, for example: “某某影业有限公司。” For a pure graphic mark, use a brand name only at high confidence. Never add legal suffixes or expand an abbreviation from memory. Do not spend the slot describing decorative animation unless it carries story meaning or the user requests it.
- Read the film title as displayed. State “片名” only when it improves clarity.
- Read cast pairings in the compact form “演员名饰角色名”, for example: “张三饰李明。”
- For other credits, use “姓名，职务” or the screen's natural order: “导演，张三。”“摄影，李四。”
- Preserve the visible order. Consolidate simultaneous names only when the relationship remains unambiguous. Do not invent obscured text or silently correct uncertain OCR; inspect a clearer frame and flag unresolved text.
- Do not treat the ending as complete until the selected credit scope has been checked through the final frame.

The cue linked to an event must overlap its display interval (or document a nearby placement), use the same evidence, and contain the visible company/title/name-role content. A cue ID alone does not prove coverage.

For bilingual cards, `visible_text` carries only the narration-readable line (the Chinese line); its normalized form must be a substring of the cue text. Simultaneous cards (e.g. stacked job titles) share one narration cue through the `cue_ids` list — reading every overlaid card with its own cue would make the narration speak over itself, so consolidate them in display order and let one cue satisfy several events.

## Confidence

Do not convert guesses into facts. Record confidence and uncertainty separately. Mark cues for review when identity, action direction, text, chronology, or speaker assignment is uncertain. Use additional frames or adjacent audio before settling an ambiguity.

## Timing and density

Silence detection alone is insufficient; continuous music is common. Combine transcript timestamps, voice activity, effects, music, scene changes, and measured TTS duration. Rank placement:

- A: no dialogue; normal narration.
- B: music or ambience; preserve important effects.
- C: limited dialogue overlap when approved and necessary for comprehension.

Prefer moving or shortening a cue over excessive acceleration. Never allow narration cues to speak over each other.
