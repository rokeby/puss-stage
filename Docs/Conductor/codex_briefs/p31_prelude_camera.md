# P31: move the Opening/prelude camera back to frame the new stage front (Gary 8 Oct: "Yes, ~24 m back")
Blender MCP Hyper3D measured (Blender render of the stage-front block-out) that from the current Opening camera
(-1400, 0, 150) pitch +14 deg 15 mm the new outer frame (paper proscenium, valance, crest) is out of frame; Gary chose the
prelude camera at ~x -2400, y 0, z 150, pitch ~+9 deg, 15 mm (render DerivedAssets/StageFrontBuild/blockout_v1_cam_x2400_15mm.png;
paper proscenium layout DerivedAssets/StageFront_PaperProscenium/PAPER_PROSCENIUM_SPEC.md; the house wash "Wash C" sits at x -2600).
The Opening camera is the binding "Opening — Stalls Camera" in LS_Opening_Curtain_Baked (OPENING_SEQUENCE_PLAN_2026-10-04.md:30),
walk-in keys from WALKIN-OPENING-APPLY-20261002-A (Saved/CodexCameraPilot/walkin_OPENING_record.json, walkin_plan.py).
It may have been re-keyed since (long Opening 96.36 s, P13 flurries): the tool's DRY must read the LIVE keys and print them.
Job (offline): tool prelude_camera_move.py DRY/APPLY/REVERT:
- PRELUDE HOLD: the camera holds at the new pose (args: x -2400, z 150, pitch 9, focal 15) from Opening start until the walk-in
  begins; the walk-in END pose and END time stay exactly as live (the arrival into P01 must not move).
- Walk-in: re-plan from the new start pose to the unchanged end using walkin_plan.py's ease law; args choose (a) keep the
  walk-in duration (faster) or (b) start the walk-in earlier by the extra 10 m at the same speed (default b if the prelude
  timing allows; DRY reports both, with max speed in m/s and the frame where the stage front leaves frame).
- Check from the new pose nothing un-dressed is in frame: list actors whose bounds fall in the 15 mm frustum between x -2600
  and -480 (house walls, Wash C lanterns, floor edge) in the DRY report (compute from level JSON exports if available, else
  mark UNCLEAR for the conductor's live DRY).
House rules (rule 9). Saves only LS_Opening_Curtain_Baked (+ Show only if the camera is a Show attachment: check). Harness +/-.
