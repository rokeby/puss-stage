# Lighting scores P01–P06: plan (4 Oct, offline build, ready to dry-run)

**Built tonight, offline. No Unreal or MCP calls were made.** Files are in `Saved/CodexConductor/`:
`lighting_scores.json` (the data), `lighting_scores_apply.py` (one passage per run: DRY, APPLY or REVERT),
`test_lighting_scores_apply.py` (the harness, 54/54 checks pass), and `lighting_scores_run.py` with
`_run_args.json` and `_run_request.json`. Nothing has been committed.

**How sure each claim is.** Every claim is tagged. *measured* means a run or file read tonight.
*declaration-proven* means a header or source line says it. *inferred* means a design proposal or arithmetic
on a model. **No row below has been seen rendered.**

## How it works

- **Looks are presets over one kit; a passage is a score of looks over its bays** (the conductor's design).
  - **declaration-proven:** the base looks MOODY, INDUSTRIAL and THEATRICAL are read at run time from the P04
    prototype's `lighting_looks.json`.
  - **declaration-proven:** passage variants such as `P05_COOL_THEATRICAL` and `P06_FAILING_GOLD` are overrides
    on top of a base look, defined in `lighting_scores.json`.
  - **declaration-proven:** there are two local looks. `GAP` (a glimmer practical plus a dead lamp body) is the
    dark between pools. `VOID` (a dead body only) is complete dark.
  - **inferred:** with these, every bay keeps a practical.
- **Bays are found by GUID, never by label.**
  - **declaration-proven:** a bay is a WingPair *ordinal* inside the passage's PassageSettings first..last range.
    It is resolved to a CueGuid twice: once by the Show's own `GetWingPairCueGuidsInPassage`
    (`InfinityStageShowAsset.cpp:496-521`) and once by an independent walk. The two must agree.
  - **declaration-proven:** if the bay count drifts, the tool stops with `BAY_COUNT_DRIFT`, and the score has to
    be re-cycled.
  - **declaration-proven:** P04 bays 1–6 are pinned to the GUIDs in the prototype's revert record.
- **The P04 tool is imported, not copied.**
  - **measured:** `lighting_looks_apply.py` ends in `if unreal is not None: main()`, so a plain import inside
    Unreal would *run* the P04 tool. The harness proved this hazard with an armed copy.
  - **declaration-proven:** the loader parses the file, refuses any other top-level side effect, strips the guard
    and checks the name and parameters of 32 functions.
  - **measured:** a changed signature stops the run with `P04_TOOL_API_DRIFT`. The file grew from 1,886 to
    about 2,200 lines while I worked (the tune-4 edits), so expect the API check to be the first thing to trip.
- **Safety: the P04 tool's rules, generalised.** **declaration-proven** (`lighting_scores_apply.py`):
  - All existing lights in a target bay are disabled, except named **retained** lamps (the blink spots and P03's
    gobo slashes).
  - Shadow budget: casters *after* ≤ casters *before*, per passage. The kit swaps casters; it never adds them.
  - Outside-target hash, exact revert, and in-memory rollback if anything fails.
  - Backups go to `Backups/PreLightingScoresP0N-*`. Only this passage is materialized, and only the Show and the
    level are saved.
  - A full field read-back, plus a value check against the plan (to catch setters that lie).
  - An interlock refuses APPLY if any other active `*record*.json` under `Saved/Codex*` names a target cue,
    unless you acknowledge it.
  - Every run must be followed by **both** `run_saved_master_test_request.json` and
    `run_scene_cut_test_request.json`.
- **P04 prototype bays 1–6.** **declaration-proven:**
  - Prototype applied (its record says `saved_readback_verified` and its labels are in exactly those 6 cues):
    the tool skips them and leaves them to `lighting_looks_apply.py`.
  - Prototype absent: the tool refuses, unless you pass `AUTHOR_FALLBACK`.
  - A mixed state (for example, halfway through a tune-4 revert and re-apply): the tool refuses.
  - **measured:** the record is present and says `saved_readback_verified` (run 20261003-201156).

## The scores

Each code is the look plus its level × 10 (no digit means 1.0). `-` is a GAP, `x` is a VOID, `P` is a prototype
bay. Base looks: M = MOODY, I = INDUSTRIAL, T = THEATRICAL. Each row is generated from the validated data.
**Every score is inferred: a proposal for Gary.**

| Passage, mood | Bays 1→N, in groups of 10 |
|---|---|
| **P01** dark walk-in, hallway ping-on, warm pools. W = warm theatrical, c = candle moody | `x - W7 W4 W6 W7 W4 - W7 W6 \| W4 W7 W7 c8 W6 c8 - W6 c7 W7 \| c8 W6 c8 - W6 c7 W7 c8 W6 c8 \| - W6 c7 W7 c8 W6 c8 - W6 c7 \| W5 W8 W8 - W8 W7 W9 W8` |
| **P02** industrial night. L = sodium plus one gel pop (magenta, acid green or oxblood), y = mystic run to the shrine | `I6 L9 - I8 L9 I5 - L8 I7 I6 \| L9 - I8 L9 I5 - L8 I7 I6 y8 \| y9 - y` |
| **P03** stiff bright, then stones and pyres growing. S = stiff, F = pyre | `S S7 - S9 S6 S8 S8 F5 S7 - \| F6 S8 F7 F8 - S7 F8 F9 - F10 \| F` |
| **P04** the prototype, then the cold ruin. B = cold breakage beam | `P P P P P P - M8 M8 - \| B I6 - x B M8 M7 T9 - B9 \| M8` |
| **P05** cool/neutral, clouds up-lit, sky back-lit, shadowless. C = cool theatrical, p = soft pool | a 7-bay phrase `C8 C6m p8 C4 - C8m p6m` ×12, then the crush `C4 - p5 - C4 - p4 - x` |
| **P06** grand gold, then failing, then VOID. G = grand, f = failing | `G G8 G10 G8 G - G G8 G10 G8 \| G - f9 f9 f9 f8 … f1 f0 x` |

- **P01, the hallway ping-on.** **inferred:** bays 3–12 strike at 650 cm plus 450 cm per bay, up to 4,700 cm,
  with a 40 cm ramp and 0.45 stutter. The cascade runs ahead of the camera at about 4× its speed. It uses Light
  Drama strike-on-approach, which the talk prep recommended for the first trial, rather than the Master-track
  draft in `p01_hallway_pingon.py`.
- **P06, the failure.** **measured, by the harness on the data:**
  - The failure has a fixed order. TOP_R goes first, then BEAM, TOP_L, the fill, the key, and finally the clamp
    practical.
  - Stutter rises from 0.10 to 0.85.
  - The after-pass changes from HOLD to DECAY to EXTINGUISH, so lamps snuff behind the camera.
  - The colour creeps to monochrome, then to sick green.
  - Output per bay (candelas and lumens) never rises from bay 13 to bay 55, and is zero at bay 55.
- **Pools and gaps rule.** **declaration-proven:** no more than 6 lit bays run in a row. The P01 cascade and the
  P06 failure are exempt. WASH and SPOT are refused in every score.

## Counts and shadow budget

**inferred.** These numbers come from the tool's own planner run on a census **reconstructed** from the 29 Sep
survey, not on the live Show. The "before" figures are the talk-prep reconstruction (P01 99, P02 70, P03 54,
P04 43, P05 2, P06 111). Tomorrow's DRY is the measurement.

| Passage | Bays scored | Kit attachments (lights + practical bodies) | Existing lights disabled | Retained lamps | Casters before → after |
|---|---:|---:|---:|---|---:|
| P01 | 48 | 378 (283 + 95) | 529 | Wing 041 `Entry High -Y` blink | 99 → 81 |
| P02 | 23 | 179 (133 + 46) | 115 | 1 blink spot | 70 → 37 |
| P03 | 21 | 169 (127 + 42) | 228 | 14 `Rig Slash` + 1 blink | 54 → 49 |
| P04 | 15 (bays 1–6 skipped) | 103 (74 + 29) | 135 | 1 blink spot | 43 → 33 |
| P05 | 93 | 724 (539 + 185) | 837 | 2 blink spots (the whole P05 budget) | 2 → 2 |
| P06 | 55 | 353 (249 + 104) | 495 | 1 blink spot (Wing 044) | 111 → 77 |

**inferred:** every passage ends with fewer enabled lights than it has today, and the kit lamps are distance-keyed,
so they are off until they strike.

## What Gary should judge first

1. **P05**, on one DRY and then one APPLY. It is his clearest note ("not so warm, the cloud colours are strong")
   and the riskiest scale: 93 bays and the label-reuse trap. Judge whether the up-lit clouds and the back-lit sky
   read.
2. **P06**, the failure arc. Bays 13–55 are the most novel idea. Judge the pace of the failure: should it start
   later, or fail in fewer, harder steps?
3. **P01**, the ping-on cascade speed and the dark walk-in.
4. P02 and P03 after that. P02's ordinals are not yet matched to the redo's plant and fence order.

## Run order tomorrow (each step is one passage)

1. **PIE must be off.** Never end anyone's PIE.
2. **Each DRY:** set `lighting_scores_run_args.json` to `{"mode":"DRY","passage":"P05"}`, run
   `lighting_scores_run_request.json`, then read `lighting_scores_report_P05.json` and the log marker
   `LIGHTING_SCORES_DRY_OK|run=…`.
3. **Each APPLY:** set `"confirm":"APPLY P05"` in the args file, run the request, then run both test requests.
4. **Pin the base looks.** Once tune 4 lands, set `base_looks_sha256_pin` to the hash the DRY prints. Tonight's
   hash is `fc8460c0…6421` (measured).

## Open questions (for Gary or the conductor)

1. **P01 mouth lights.** The P01 house warmers (`House L`/`R`, shadow casters) are disabled to make the walk-in
   dark. Is that his call to make? **inferred**
2. **P01 ping-on.** Using Light Drama makes the Master-track draft in `p01_hallway_pingon.py` redundant for P01.
   Retire it? **inferred**
3. **P03 gobos.** No gobo light-function asset exists (**measured**: `Content/` has only `MI_LF_Flicker_*`). The
   "gobo breakups" are therefore the retained Rig Slash spots plus the timber blink gobo. Is that enough?
4. **Retained-lamp labels.** The labels I matched on (`… Blink Spot`, `… Rig Slash`, `… Entry High -Y`) are
   **inferred** from the replication label rule (`InfinityStageShowAsset.cpp:633-642`) and the survey. The DRY
   stops with `RETAIN_COUNT` if any count is wrong.
5. **Bay counts.** These are the 29 Sep counts (**measured**, in the survey). If P02's redo changed its count, the
   DRY stops with `BAY_COUNT_DRIFT`.
6. **Other tools' records.** FlatV3 swap-kit or fence records that name these cues will block APPLY until they
   are acknowledged. Who owns those cues tomorrow?
