# P8: S4 entry v5, finish the tooling (Gary 8 Oct: "v5")
Context: the live S4 (LS_DevScene_04) still runs the v4 Klara reveal. Measured tonight (Docs/Conductor/CONDUCTOR5_LOG_2026-10-08.md, section "S4 entry check"):
- Her L_KK_children actors appear at S4 +4.4 s.
- Until the cut at Scene frame 405 (16.2 s @25) the children sit lit in BIND POSE and the pigeon is frozen.
- The pendulum tick is now off (KLARAPENDULUM-20261008-041003; leave it alone).
Gary chose the v5 entry of 7 Oct: arrive in the dark with no strikes, and her characters PRE-ROLL over the glide, then a hard cut into her first shot.
The tools exist but were never run to APPLY:
- Saved/CodexConductor/KlaraIngest/klara_reveal.py (v5 mode, args klara_reveal_s4v5_args.json);
- klara_preroll_s4.py, whose DRY tonight refuses only REVEAL_NOT_V5;
- klara_s4v5_preview.py.
Read Docs/Conductor/S4_ENTRY_V5_BUILD_2026-10-07.md and S4_ENTRY_INVESTIGATION_2026-10-07.md. The 7 Oct log says: "v5 DRY needs the S4 backcloth/cache hold first; cache hold NOT implemented (headers give no clean last-frame hold; PIEPROBE mode added)".
Job:
1. Find exactly what blocks a v5 DRY → APPLY, and implement the missing backcloth/cache hold, or propose a design that avoids needing it (for example: the glide ends where the backcloth is out of frame; or the backcloth GeometryCache section is extended or held via an additional section at its last frame). Cite headers under D:\Unreal Engine\UE_5.8.
2. Use the S1 pre-roll as precedent: Saved/CodexConductor/KlaraPrerollS1_20261008/klara_preroll_s1.py, applied live tonight (KLARAPREROLLS1_APPLY_OK). It needed live fixes; read its "8 Oct live fixes" notes and port any that apply to klara_preroll_s4.py (section-off-frame tick math, probe gating inside the segment, loop alignment). In S4 the pigeon and children must be MOVING during every lit frame before the cut.
3. Write an ordered runbook for the conductor: REVERT v4 → v5 DRY → preview stills → APPLY → pre-roll DRY/APPLY → tests → PIE probe. Include each confirm string and expected marker.
4. Harness with negative and positive controls.
Do not touch klara_pendulum_s4.py or its record. Klara's levels must never be saved.
