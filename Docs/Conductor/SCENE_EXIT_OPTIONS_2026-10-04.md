# Scene exits: three options for Gary (4 Oct, written offline, nothing applied)

Your note (run-through 3 Oct, item 10): *"we don't currently have an effective exit curtain cut ... prepare a subtle
exit doorway at the back of each rig hangar ... like a backstage hidden doorway."* The doors now exist, closed, in S1–S6.
This page asks you to choose how the camera leaves through them. Proof tags: **[decl]** read in source or config,
**[meas]** read back from the editor, **[arith]** arithmetic on measured numbers, **[inf]** inferred, with the reason.

## What happens today
- A Scene ends on its **Exit Handoff camera**, which is a *retained hold*: it copies the last interior shot and runs
  from that shot's end to the Scene's end (`InfinityStageSceneHandoffBuilder.cpp:186-210, 419, 440, 447`) **[decl]**.
  The Interaction that follows keeps that camera (`InfinityStageTypes.h:830`) **[decl]**, but its own cut binds the
  stalls camera from frame 0 to 500 (`Saved/CodexCameraPilot/probe_interaction_cut_binding.json`, 30 Sep, possibly
  stale) **[meas]**. So the exit is a hard cut from the hold to the drape at the next mouth, about 14 m away.
- What you saw (S1, S4: the camera looking up at the ceiling, then the curtain): **UNCLEAR.** In S1, LS_Animals_1's
  nested cuts mask the root Exit cut (memory, measured 30 Sep), and S4's look-up is the dog's. Nobody has captured this
  yet.
- **The door distance is 65 m, not 60 m.** Each hangar root sits 500 cm (the apron) ahead of the dock, and the door face
  is at root x 6000. That puts the door 6500 cm from the dock camera (S5: 15500 cm) **[arith]**, from
  `hangar_exit_doors_record.json` (`root_before`, leaf pieces) and `hangar_s*_plan.json` (dock). The probe's 6004 cm
  left out the apron, because it measured the door at dock x = depth **[decl]** (`hangar_exit_doorways_probe.py:291`).

## The three options (each ends black, then the existing Interaction cut to the drape)

**A. "The cat walks out"** is one continuous take from the dock view. The camera walks the length of the hangar at
250 cm/s, and the door swings toward us when we are about 10 m out. We walk through into black, then cut to the curtain.
```
 dock ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▶ ▌door▐ █black█
      |<------------------------- 65 m (S5: 155 m) ------------------------->|
```
- **Length** **[arith]**: 26 s of walking plus about 2 s, so about 28 s; S5 alone is about 64 s.
- **Needs:** a waypoint path per Scene, because the straight line is blocked in all six. The cast and props stand in
  the way: in S3 the clams, waves and the shadow cat **[meas]** (conservative AABB survey, not collision). It also
  needs leaf keys, camera keys and a light on the door.
- **Risks:** this is the longest option, and it walks through the cast. It reads as the Passage grammar, but the GO1
  is not engaged in Scenes. S5 is too long unless the walk speeds up.
- **Suits:** S1, S2, S4 and S6, if a path is clear.

**B. "Cut to the hidden door"** (recommended; the draft tool keys this one). We hard-cut to a camera 9 m in front of the
closed door and hold for 1.5 s, so you can just read the door. The leaf swings **in, toward us**, on its left jamb (3 s,
eased). The camera walks through at 250 cm/s into the black, then cut to the curtain.
```
        9 m              door face     Exit Black (2 cm behind wall)
  ●cam ━━━━━━━━━━━━━━━━━━━━▶ ╲leaf swings in      ▐█▌  ← camera stops 25 cm short: frame all black
                           hinge (-Y jamb)
  0      1.5 s hold   2.5 s walk starts   4.5 s door open   7.1 s arrive   7.6 s + 1.0 s Exit hold (black)
```
- **Length** **[arith, offline planner]**: 7.6 s plus the 1 s Exit hold, the same in every Scene, S5 included. The
  camera clears the swinging leaf by 100 cm at its closest.
- **Needs:** one camera per Scene (a level actor on the hangar root), leaf keys and camera and focus keys in the Scene
  sequence, one root cut, then the builder's own rematch. A soft light over the door would make it read when closed.
- **Risks:**
  1. The exit "black" is metal black, which reads tan under warm light (memory, measured 30 Sep). It wants velvet.
  2. The 7.6 s come out of each Scene's tail unless the Scene is lengthened. Lengthening moves later Passage keys
     (key gate).
  3. A cut breaks "we are always the cat". Scenes are not dog-led **[decl, your 2 Oct note]**.
- **Suits:** all six once the blockers below are cleared.

**C. "The room lets us go"** keeps the final view: no cut, no walk. The hangar's practicals dim in sequence toward the
door (the hallway ping in reverse), the door swings in, and the lens pushes slowly from 35 to about 100 mm over 6 s.
Then cut to the curtain on the black doorway.
```
 dock ● (lens 35→100 mm)                        practicals out ← ← ←   ▌door swings in▐ █black█
```
- **Length:** about 9–10 s.
- **Needs:** light keys on the hangar practicals, leaf keys, and focal keys on the Exit camera's component (never its
  actor).
- **Risks:**
  1. At 65 m the door is small: about 7% of the frame width at 35 mm and about 20% at 100 mm **[arith, Super 35]**.
     Filling the frame would take about 515 mm.
  2. The dimming touches the hangar lighting, which is yours to judge.
  3. The Exit hold is shared with the builder's copy.
- **Suits:** S4 and S5, where the room is the event. It is the weakest in S3, where the backdrop is the door.

## Blockers for any option (the draft tool refuses on each)
1. **S3: the leaf sits 0.05 cm in front of the S3 Backdrop, which was never cut** **[decl]**
   (`hangar_exit_doors.py:204-240` reads it and never edits it), so an open leaf would show the same picture behind
   it. S3 needs a hole or mask in the backdrop first **[inf: the backdrop's alpha was not inspected]**.
2. **Nested shot cuts outrank root cuts.** In S1, LS_Animals_1 covers the whole Scene, and S3's LS_Clams has a cut
   until 12573 (memory, measured 30 Sep). An exit shot is hidden unless those cuts end first.
3. **The rise must be over** before the exit starts (LS_S*_HangarRise).
4. **The exit black should become velvet**, and be measured in the actual light.

## Questions (recommendation first)
1. **Which exit?** Recommended: **B**. Alternatives are A, C, or a mix (for example B everywhere and C for S5).
2. **Where do the ~8.6 s come from?** Recommended: **the end of each Scene** (no timing change). The alternative is to
   lengthen the Scenes (key gate, Passage keys move).
3. **Hinge side and swing.** Recommended: **left jamb, swinging in toward us, 100°**. The alternatives are the right
   jamb, or swinging away into the black, which needs the black plate moved back.
4. **S3's backdrop:** **cut a door-shaped hole**, or do S3 differently (for example C)?
5. **S1/S3 nested cuts:** may Look & camera **trim them** to end before the exit?

Draft tool (not run, apply-locked until `scene_exit_move_overrides.json` names who decided and `option: "B"`):
`Saved/CodexConductor/scene_exit_move.py`. The harness is `test_scene_exit_move.py` (57 pass, 0 fail, offline, real
door geometry) and the read-only runner is `scene_exit_move_dry_run.py`.
