# PG2 — Shadow puppets: real-time moves between held poses (offline)

Read `_house_rules.md`. Offline only (Python/numpy/PIL). Do not touch `Saved/CodexConductor/animated_gobo.py`.

## Gary, 9 Oct (watching the I2 boy test, his words)
"The boy shadow is off to a very good start. Note that the animation when the limbs DO move could be smoother as in
real shadow puppetry - the limitation is movement but movement is in real time. ... The shadow is good! Could be a
touch softer."

So: HOLDS stay single still frames (the puppet held still; UE adds the live handheld wobble). But when a joint moves,
the move must be in REAL TIME: rendered at the DISPLAY rate (25 fps; I2's sequence is 25 fps, measured), with eased
in-betweens, not 2-3 snapped steps at 8 fps.

## Current pipeline (reference, all committed on master)
- `Tools/ShadowGobo/Puppets/boy_rig.py`: `rubbing_eyes_clip()` (keys = (seconds, pose, move_frames)), `clip_frames()`
  (8 fps, linear lerp, face swaps snap at u>=0.5, tears quantised), `render_clip()` (sharp transmission PNGs of a
  square world window).
- `Tools/ShadowGobo/pack_rig_flipbook.py`: de-duplicates identical frames into atlas cells, writes RG atlas (R sharp,
  G blurred) + manifest with `schedule` [[seconds, cell], ...]; `test_pack_rig_flipbook.py` (9/9).
- `Tools/ShadowGobo/gobo_twin.py`: offline twin of the UE light function (renders what the camera sees).
- `Tools/ShadowGobo/Puppets/cat_rig.py`: Puss (same architecture; check its clip/pose API).
- UE side keys the schedule as CONSTANT MPC Frame keys at display frames, so a 25 fps schedule plays every
  in-between exactly once per display frame (no change needed in UE).

## Build
1. A shared clip renderer (e.g. `Tools/ShadowGobo/Puppets/clip_render.py`) used by BOTH rigs: clip = list of
   (seconds, pose, move_seconds, ease). Holds render once; a move renders one frame per display frame (25 fps
   default, arg) with an ease curve (ease-in-out default; per-move override: "snap", "linear", "ease_out" for a flinch).
   Face swaps happen at a set point of the move (arg, default 0.5). Tears slide continuously at the display rate
   while held (they are a moving cut piece) with a tear speed arg.
2. Cell budget: report rendered frames, unique cells and the atlas grid/cell px for 4096 and 8192. Save cells:
   (a) a move that exactly reverses a previous move (rub A->B->A) reuses the forward cells in reverse; (b) identical
   poses dedupe (packer already does); (c) a `max_cells` arg that, if exceeded, reduces in-betweens of the LONGEST
   moves first (never below 4 per move) and reports what it did. Packer: add `--atlas 8192` support check (cells up to
   ~200 at >= 560 px) and a manifest field `display_fps`.
3. Re-render the boy "rubbing eyes" clip with real-time moves (same beats/timings as `rubbing_eyes_clip`) into
   `Tools/ShadowGobo/Puppets/clip_rub_rt/` (frames are scratch; commit atlas + manifest + contact + twin GIF only), and
   a twin GIF via gobo_twin at 25 fps with params {"BorderDepth":1,"BorderAspect":1.88,"Scale":0.7071,
   "Defocus":0.25}. Gary wants "a touch softer": Defocus 0.25 is the proposed default; also render 0.15 and 0.35 stills
   side by side so he can pick.
4. One short Puss clip (e.g. sit_upright -> look_up -> meow -> sit_upright) through the same renderer + packer, to
   prove the shared interface.

## Traps
- Lerping joint angles is fine, but IK hand targets must be interpolated as POINTS (then solved per frame), or the
  hand swims off the face mid-move (boy_rig `*_hand_on_head`).
- Do not bake the handheld wobble (UE does it live from MPC Clock); a baked wobble would also defeat de-duplication.
- Floating-point noise defeats de-duplication: quantise angles/targets before rendering (e.g. 0.01 deg / 0.01 unit)
  so a held pose renders byte-identical every time.
- The schedule must place each in-between on its own display frame; at 25 fps, two events that round to the same
  frame collapse (later wins) - assert none are lost.

## Harness (+ and - controls)
Holds produce 1 cell; a 0.4 s move at 25 fps produces 10 in-betweens; the reverse rub reuses cells (count); eased
moves have smaller first/last steps than middle steps (measure joint deltas); IK target stays within N units of the
face throughout a hand-to-face move (- control: angle-lerped IK drifts and fails); schedule events strictly increasing
display frames; byte-identical held frames.

## Deliver (rule 8)
Paths, commit hash (or the list of files if your sandbox cannot commit), run order, harness counts, the cell budget
table, open questions for Gary. Apply nothing.
