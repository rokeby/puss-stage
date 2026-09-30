# Pre-registration: does REST_SWITCH_AMOUNT move pile fold size? (30 Sep, 09:10, before the 0.4/0.6/0.8 strips land)

Soft goods, at the Conductor's request. Written and committed BEFORE sw_ps_a04_g07, sw_ps_a06_g07 and sw_ps_a08_g07
report. At the time of writing only sw_ps_a10_g07 had landed (fold size 1.304 m = 1.58x the flat control sw_b5_g0's
0.825 m).

## The confound

The flat-rest hem-guide strip (sw_b5_g07) also gave fold size 1.6x (1.316 m). So the smoother pile may come from the
GUIDE, not from how far the rest shape switches.

## What each outcome will mean, decided now

Fold size of each amount, as a ratio to sw_b5_g0 (0.825 m):

1. **All four within 1.42–1.74 (±10% of 1.58).** The amount does NOT move fold size. Either the guide dominates, or
   the knob is not doing what its name says. Knob check: the unguided full switch (sw_b5_pswitch) gave 2.05x, and
   coarse pleated rest (amount 0) against coarse full switch gave 0.44 vs 0.65 m. If the four also agree on layers and
   depth, the knob is suspect. If those spread while fold size does not, the guide dominates fold size.
2. **Monotonic spread of at least 0.3 in ratio, lower amount giving smaller folds** (e.g. 0.4 at 1.3x or below, 1.0 at
   1.58x). The amount is a real lever, and the confound is dissolved for this range.
3. **Non-monotonic, or spread under 0.3 but outside band 1.** Inconclusive. Report it as that; do not pick the best
   number and call it a trend.

Also checked by eye at amount 0.4: some REGULAR pleat memory in the pile would confirm the knob works, and would also
be the rejected "corrugated rows" risk. That is reported whatever the numbers say.

## Is 1.58x a real fail? The arithmetic, not a look

The stalls camera: 14 m, pitched +14 deg, 15 mm on a 23.76 x 13.365 mm filmback, so 79 deg across at 1920 px (24
px/deg) and 48 deg high at 1080 px (22.5 px/deg). The pile on the floor at the lip sits about 6 deg below horizontal,
inside the frame's lower edge at -10 deg, so it IS in the stalls view as a band about 45 px tall.

Fold size is area / crease length. It is not literally a spacing, but it scales with the spacing between creases:
- control, 0.83 m at 14 m ≈ 3.4 deg ≈ 80 px;
- guided, 1.30 m ≈ 5.3 deg ≈ 130 px.

That difference is tens of pixels, far above the 1-2 px level where the stillness limit lives. **So 1.58x is a
RESOLVABLE difference in how crumpled the heap reads from the stalls.** The arithmetic cannot say it passes; it can
only say the difference is visible. Whether his approved image survives a coarser crumple is then a LOOK question for
Gary, answered with the two piles side by side from the stalls camera, not by the number. The 25% fold-size tolerance
remains provisional and has no derivation. It is flagged as such in the acceptance report.

## Addendum (09:15, still before the 0.4/0.6/0.8 strips land): the noise floor, and the contingent next sweep

**Mechanism correction.** The hem guide is released WITH the heading (pin stiffness keyed to 0 at the release frame),
so it cannot constrain the FALL. It only shapes the cloth's state at the moment of release: how ordered the columns
are, and how still. Any effect of the guide on the pile runs through that initial state.

**The unmeasured noise floor comes first.** Every pile comparison today is one run against one run. A falling cloth is
chaotic, so a different pleat seed alone may move fold size by an unknown amount. Until that spread is measured, a
1.58x difference cannot be fully attributed to the recipe, and the 25% tolerance cannot be justified. Test:
sw_ps_a10_g07 repeated with CURTAIN_SEED + 1 (the pleat gains change; nothing else does), same timeline.
- If the two fold sizes differ by less than 10%, the 1.58x is the recipe.
- If they differ by 25% or more, the pile metrics are too noisy to gate on as single runs, and the comparison must be
  an ensemble, or a look.

**Contingent next sweep, if outcome 1 holds (all amounts ~1.6x):** GUIDE STRENGTH, at a fixed amount: weights 0.7, 0.4
and 0.2, watching fold size AND stillness together.
- If fold size falls as the guide weakens while stillness holds under 2 mm, there is a window.
- If stillness degrades in lockstep, this cloth cannot have both, and that is the finding for Gary. It is not a reason
  for more bakes.

## Result (09:20). Written after the numbers, against the criteria above.

| amount | fold size ratio | height | depth | width | layers | still mm/frame | hang |
|---|---|---|---|---|---|---|---|
| 0.4 | 1.51 | 0.81 | 1.17 | 0.87 | 0.97 | 0.41 | pass |
| 0.6 | **1.12** | 0.94 | 1.11 | 0.85 | 0.99 | 0.41 | pass |
| 0.8 | **1.08** | 0.91 | 0.99 | 0.94 | 1.06 | 0.41 | pass |
| 1.0 | 1.58 | 0.91 | 1.16 | 1.11 | 0.82 | 0.41 | pass |

**Pre-registered verdict: outcome 3, INCONCLUSIVE.** The spread is U-shaped (coarse at both ends, fine in the middle):
neither outcome 1 (flat near 1.6) nor outcome 2 (monotonic). It is NOT reported as "a lever".

**Separately, the acceptance test:** 0.6 and 0.8 pass the provisional 25% pile criterion on all five numbers, as
single runs. 0.4 and 1.0 fail on fold size. Whether that pass is the recipe or a lucky draw depends on the seed
repeat (sw_ps_a10_g07_s2):
- if it lands near 1.58 (within 10%), single runs are trustworthy and 0.6 or 0.8 is the amount;
- if it lands near 1.1, the U is noise, and the pile is a look call for Gary.
Stillness (0.41) and hang (perfect) are identical at every amount, as they must be: the amount acts only after release.

## Separate observation (09:35): the CHARACTER of the two failures. Not a reinterpretation; the verdict stays inconclusive.

Suggested by the Conductor as a test that noise cannot pass: if the U shape is two mechanisms, the failing ends
should look different in KIND. The zoomed 3/4 renders (zoom_piles_a04_a06_a10.png, compare_switch_amounts_piles.png):
- **0.4:** a flattish sheet whose top carries faint REGULAR parallel ripples. That is pleat memory surviving as gentle
  waves, too shallow to count as creases (dihedral under 45 deg), which is why the metric scores it coarse.
- **1.0:** a SMOOTH sheet with one large fold turned over at the end: the unfolding "thrown sheet".
- **0.6:** overlapping LAYERED folds, the most heap-like of the three.

The ends do differ in kind (regular ripples against smooth sheeting), which favours the two-mechanism reading over
noise. **Confidence: modest.** These are partial crops of Workbench renders judged by one eye. It is independent of the
seed repeat, which remains the quantitative test.

**On 0.6 being baked (final9/10/11): it was a GUESS that held, not a derived choice.** It was launched at 06:35 as the
middle of the range, before any strip reported. If the seed repeat confirms that single runs are trustworthy, 0.6
passes as a single run; it was still not selected by evidence. Anyone reading "0.6 is the amount" later should know that.
