# Puss — rehearsal and venue checklist

What has to be practised, measured or drilled rather than built. Most of this
needs the show machine, the dog and the room — not the editor.

Companion lists: [engineering](ShowBuildTodo.md) · [creative](ShowCreativeTodo.md)
Reasoning behind each line: https://claude.ai/code/artifact/7d8d8c4f-885c-436b-8b7c-9f7ef709d29a

**G** Gary · **K** Klara · **C** Cameron

---

## Rehearsal entry points — engineering cleared 28 August

**Opening / keyboard, 14 September:** normal production PIE plays the opening
and holds at Passage 1 after 15 seconds. Click the game viewport for keyboard
focus; Space is play/hold, Right Arrow advances a segment and Left Arrow goes
back. Use Space to begin Passage 1 from its ready hold. The curtain now reveals
that Passage through its starting camera. [Evidence](OpeningPlaybackRepair-20260914.md).

- [x] **0.6** ✅ The visible **Rehearsal** toggle now pushes the external-clock bypass into live PIE. Performance mode still enforces the lock by design.
- [x] **G.3** ✅ Select a Scene/SEQ and use **Play Selected** to cue its first frame and play to its boundary. Production Next Segment auto-plays Scene/SEQ cues. Passage playback now continues through the following Scene before holding (14 Sept).

**14 September transition checkpoint:** all six Passage → Scene boundaries and
Scene-end holds passed in normal PIE. The Show player reached the Shore content,
switched to `ClamCam1`, and drove all six bodies. An uninterrupted Passage 3 run
was captured and inspected. [Evidence and operation](SceneTransitionRepair-20260914.md).
The full eighteen-seam run-through below remains open.

These no longer block rehearsal. The current blocker is confidence, not access:
the latest full suite is 43/44 on a curtain marker check, and rendered curtain
composition has not yet been signed off by eye.

## Run-throughs, in order

- [ ] **J.3** (G) Boundary run-through — `Play Through Boundaries` on, watch all 18 seams in one pass. Most failures in this show will be seams.
- [ ] **J.4** (G) Full technical run, no performers, timed, on the show machine.
- [ ] **B.8** (G) Rehearse the physical handover at each curtain — the moment the live dog and the projected image swap focus. Verify all five interaction curtains fully cover both Passage states at frame 375, the intended boy/cat–curtain depth order reads correctly, and there is no one-frame background flash.
- [ ] **J.5** (G/K/C) Full run with performers and dog. This is where the sound-authority decision stops being a paragraph.

## Drills

- [ ] **J.6** (G/K/C) Failure drills: dog offline, audio device change, editor dialog appearing mid-show, a hitch at a curtain.
- [ ] **F.4** (G) Dog-failure drill specifically — wifi drop → Force Timeline via Live Camera Owner. Rehearse to reflex; it must not be a decision made live.
- [ ] **G.5** (G) Emergency controls tested **under performance mode**, where unpausable Scenes reject some of them by design: hold, blackout, skip to next section, restart from the last curtain.

## Measurements that need a real run

- [ ] **F.2** (G) Measure yaw drift across a full run, and across the Void specifically — the longest unanchored look, with no route tangent pulling the view back.
- [ ] **F.5** (G) Void camera in practice: Free Look, not Gaze. Check whether its camera also carries keyed rotation, since dog look and authored rotation write the same orientation.
- [ ] **F.1** (G) Confirm the gaze/turn mode values with the dog **standing** — it reports `mode=0` while prone, so the defaults are unverified.
- [ ] **G.6** (G) Profile on the show machine: chunk budgets, GC hitches at scene boundaries, worst-case passage. A hitch during a curtain reveal is a visible failure.

## Venue — Wapping

- [ ] **K.1** (G) Re-measure screen geometry and update the yaw mapping. Currently calibrated 3.5 m wide at 3 m → 30.3° against a 60.5° FOV.
- [ ] **K.2** (G) Treadmill position and the dog's working area; mark the physical zero.
- [ ] **K.3** (G/K/C) Sightlines — nobody in the projection path, and Gary can see screen, dog and HUD at once.
- [ ] **K.4** (G) Ambient light at show time. The image and the surtitles both depend on it.
- **C.7** → [creative](ShowCreativeTodo.md). Surtitle legibility in the room.
- **D.7** → [creative](ShowCreativeTodo.md). Sound room test.

## The document you hold on the night

- [ ] **G.7** (G/K/C) Run sheet: 19 cues × who does what. Downstream of every other decision, so write it last — but write it.
