# P37 — P06 wing falls: more drama, settle dust, and a 12-wing right-side domino into a slam before the Void (Codex, offline)

Read `_house_rules.md` first; every rule applies (DRY/APPLY/REVERT, record before mutation, exact census, targeted saves,
read-back, run-id markers, proof tiers per claim, falsifiable harness with +/- controls). Nothing runs live; the conductor
runs editor steps.

## What Gary asked (9 Oct, his words, conductor session)
"the falling wings have happened, and they look good, they could be more dramatic, and there could be a little bit of
dust when they settle. I think we can plan a second bunch of falling wings much later on in that level on the right hand
side, potentially a series of wings that reaches from the last ... 12 wings dominoing all the way till the end, leading to
a real slam sound before we get into the void."  Passage confirmed: **P06** (his answer).

## Starting point (read the code, do not rewrite it)
`Saved/CodexFlatV3/topple/`: `topple_core.py`, `topple_chain.py` (N-slab solver), `make_keys.py` (`--n --side L|R
--slam-s --end braced|floor --candidate`), `topple_apply.py` (+ `test_topple_apply.py`), live state
`topple_originals_ACTIVE.json` + `topple_apply_TOPPLE-20261007-114412.json` (the APPLIED six-slab LEFT chain: creak
29.790 s, final impact 37.000 s, rest 38.180 s — `topple_plan.json:3482-3483,3551-3558`), mechanism sounds
`topple_mechanism_sounds_*.json`. P06 = 126.0011 s; sunset fully black by 90 s; bee glints 80/100/118 s; car 68.55 s;
P06 FX (motes Wing 052, Stylish Niagara fire Wing 049) applied 9 Oct (`Saved/CodexConductor/P06FX_20261008/`).
Read `Docs/Conductor/P06_FX_CUE_SHEET_2026-10-08.md` for the proven spine.

## The trap (name it in your report)
`topple_apply.py` is built around ONE active chain (`topple_originals_ACTIVE.json`, RECORD_EXISTS-style guards). A second
chain must not overwrite, revert or re-key the first. Chains need an id; REVERT of chain B must leave chain A
bit-identical (harness negative control: reverting B with A's record present must not touch A's keys).
Also: Passage keys are ABSOLUTE (memory: passage-keys-absolute) — a later passage relength moves sections, not keys.
Report what a P33 passages-to-music relength would do to both chains.

## Build
1. **Chain ids**: chain A = existing left six (adopt its record read-only, no re-apply). Chain B = new, `--side R --n 12`
   (fewer if fewer eligible right rows remain; report the count and why), ordered toward the passage END, final impact
   (the SLAM) at an args time default **122.0 s** (must leave >= 2 s before the P06 end; refuse if the solved chain
   cannot finish by `end - 2.0`). `--end floor` default for B (a real slam), with the intersection ack gate as today.
2. **More drama (both chains, args, defaults conservative)**: steeper late acceleration (gravity-like ease, no linear
   rotation), a small overshoot/bounce on landing (one, <= 3 deg), optional per-slab hesitation jitter (seeded, single
   draw per value — memory: random draw order). Chain A changes are a separate opt-in arg `restyle_chain_a` (default
   false) with its own record.
3. **Settle dust**: at each impact frame spawn/activate a short dust burst at the slab's leading edge on the floor:
   prefer an existing Niagara/Cascade smoke or dust asset in Content (inventory them; cite paths); else propose. Bursts
   are owned, tagged, activated by keys in the P06 sequence (never auto-activate), capped count, and cheap (no lights,
   no shadow casting). Scale the LAST impact of chain B up (the slam).
4. **Slam sound**: key a one-shot at chain B's final impact on the existing mechanism-sound path; pick from Content
   (inventory heavy wood/door slam candidates, cite paths) — Gary chooses; default = loudest existing candidate, args.
5. **DRY report**: per chain: rows, side, creak/impact/rest times, camera lead at the slam, dust burst list, sound pick,
   and a timeline PNG (both chains + sunset + bees + car + FX) like `p06_fx_preview.png`.
6. Harness: + controls for each guard, - controls (chain B over chain A rows refused; slam after end-2 refused; REVERT B
   leaves A identical; dust auto_activate true refused).

Deliver offline in your worktree; do not commit (sandbox can't) — the conductor reviews, copies and commits.
