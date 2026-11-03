# Anti-summary quality gates

Use these gates for long films and for any draft that begins explaining plot instead of describing images.

## Evidence gate

Create structured visual observations before candidate cues. Every normal cue must cite existing observation IDs and concrete evidence timestamps. Continuous action needs beginning/process/result evidence. Reject unsupported cues; an exceptional nonvisual editorial clarification must be labeled, justified, and presented for explicit review.

## Soundtrack-value gate

Ask: “What visible information does this add that the soundtrack does not already convey?” Reject a cue whose main source is dialogue, subtitles, transcript, synopsis, franchise knowledge, or model memory. In particular, do not narrate audible mission objectives, failed plans, broadcasts, causal explanations, or lists of steps. Describe visible gestures, screens, reactions, movement, spatial relationships, object state, and necessary on-screen text.

## Coverage gate

The complete scene table precedes drafting. Scene-table entries are analysis units of roughly 20–60 seconds; the granularity is a coordinator decision because it sets the effective observation floor: every scene needs at least one observation (scene coverage gate), while each analysis segment needs at least one observation per minute (density gate) — the tighter of the two binds. Every scene has a visual observation or an explicit no-cue coverage record. Any gap longer than 60–90 seconds must be justified as visually stable or soundtrack-sufficient. Treat sparse contact sheets as indexes, not sufficient evidence. Inspect more densely around action, silent reactions, scene transitions, and object changes. The auditor warns when the average scene drops under 15 seconds; an over-coarse table is not separately blocked because the density and per-scene coverage gates already bound it from below, so keep entries within the 20–60 second contract yourself.

A no-cue record is not a waiver. It identifies the visible subject/state, why the image is stable, what the soundtrack already conveys, and evidence frames. It cannot cross a cut, entrance, exit, expression change, object transfer, or meaningful action. Repeated boilerplate such as “画面稳定、声音足够” is summary drift, not coverage.

## Drift gate

Compare each narrative analysis segment with accepted earlier ones; the auditor uses the median observations-per-minute across narrative segments as the baseline and flags segments below 55% of it. Opening/end-title credit segments are exempt from the drift comparison — they are held to the title/credit coverage gates instead, and a dense 2-minute title unit must not inflate the film-wide baseline. Stop and re-analyze when observation density falls sharply, average cue length rises sharply while observations fall, large unexplained gaps appear, or prose becomes abstract and causal. Cue counts are not quotas: a quiet scene may need few cues, but it still needs evidence coverage. A 20-minute interval with only a handful of observations is not adequate analysis.

## State gate

The coordinator merges proposed bible updates after each wave before issuing later work packages. Character, location, object, and story-state files cannot all remain empty after substantive analysis. Scene coverage, completed segment artifacts, merged draft coverage, script versions, per-batch approvals, and project stage must agree.

Run `scripts/audit_project.py PROJECT_DIR --report qc/project-audit.json`. A nonzero exit blocks review delivery, approval, synthesis, and mixing until hard failures are corrected. Similarity and synopsis-like language checks are conservative heuristics; review the cited cue and nearby dialogue rather than automatically deleting it.
