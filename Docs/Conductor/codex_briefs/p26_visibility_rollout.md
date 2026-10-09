# P26: fix inert visibility tracks in S1/S4/S6/S3 + correct the tools that create them
Measured tonight: Python-added visibility tracks bound to "bHiddenInGame" with True=hidden do NOTHING (house rule 9; S2 fixed by
Saved/CodexConductor/KlaraIngest/s2_vis_fix.py, S2VISFIX-20261008-1; generic tool KlaraIngest/vis_fix.py (735ab31, NOT run),
census Saved/CodexConductor/probe_vis_census.json: LS_DevScene_01 34, LS_DevScene_04 33, LS_DevScene_06 120, LS_DevScene_03 13
(S3 Hangar Float Hold), all "bHiddenInGame"). Tracks with property "None" are a separate group, believed working (inferred).
Job (offline, worktree):
1. Review/extend vis_fix.py into a per-scene runbook: args per scene (sequence, file, tag), DRY lists every track it will flip
   with its binding + range; APPLY flips property -> bHidden and inverts defaults+keys; REVERT exact. Harness +/- controls
   (bHidden tracks untouched; None-property untouched; mixed bindings).
2. A PIE verification probe (PIE-only, no saves, slate tick, scrub + read actor 'hidden') per scene: for each fixed binding,
   sample one frame inside and one outside its section and assert hidden/visible as intended. Output JSON + marker.
3. Patch the CREATOR tools so they cannot re-create the bug: klara_hookin.py (_add_vis_binding ~:1860), klara_hookin_s6.py
   (~:1209), klara_reveal.py (~:3194), klara_void_s6.py (~:1194), s4_hangar_hold.py (~:1130), p18_sky_policy.py (~:288),
   all under Saved/CodexConductor (KlaraIngest/ for the klara ones): bind ("bHidden","bHidden") and store VISIBLE semantics
   (default = not hidden). Run each tool's existing offline harness; report pass counts before/after.
Do not change any behaviour except the bound property and the channel polarity.
