# P44 — S1 darkness before the strike (F4), the 3:44 rig fade (F5), and I1/I3/I4/I5 shadow transitions (Codex, offline)

Read `_house_rules.md`. Offline only.
- F4 (Gary 8 Oct): "Before Klara's light strike we slowly zoom into a dimly lit version of her stage … the stage lighting
  should be TOTAL DARKNESS; only the very dim rig lights may appear." Codex job 26 (vis_fix rollout, `VIS_FIX_RUNBOOK.md`,
  S1 args) is the visibility path; read memory ue58-visibility-track-binding (bind bHidden; bHiddenInGame inert).
- F5 (Gary 8 Oct): at S1 3:44 "rig lights turn off… jolted into disappearance… shouldn't snap" -> 1–2 s fade.
  Codex job 29 (`S1RigFade_20261009`) found the switch-offs at ~11 s into S1, NOT 3:44 — resolve: map Gary's "3:44"
  (Master clock? S1 clock? recording clock?) to frames using the Master section table, cite evidence, and retarget.
- Interactions I1/I3/I4/I5: apply the I2 shadow-curtain transition pattern (I2Order_20261008 + interaction_shadow_transition
  P9) to the other four: dark → curtain present → light strikes onto curtain → shadow → curtain drop. Use existing gobo
  assets as stand-ins (gobo run 007 is I2's; others use the current best). DRY lists per-interaction what exists/missing.
Deliver: a probe (read-only) + DRY/APPLY/REVERT per item, harness +/- controls, tiered report, in your worktree.
