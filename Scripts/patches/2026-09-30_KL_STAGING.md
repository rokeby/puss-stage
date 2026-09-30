# Patches K and L: two-stage apply (30 Sep 2026)

Look & camera. Patches K (`2026-09-30_K_passage_keys_follow_section.patch`) and L
(`2026-09-30_L_retained_exit_leaves_no_gap.patch`) each put their test in a NEW
file, separate from the fix, so the tests can be compiled and run BEFORE the
fixes.

**Why stage it:** "each test is red without its fix" is inferred from reading
the code; nothing has compiled. K's test measures an inference nobody here can
read (that UE 5.8's `MoveSection` carries channel keys; the engine .cpp is not
shipped). A red after the fix is only interpretable if the test was seen red,
for the right reason, before it.

Apply from the committed blobs (the repo stores LF; working copies are CRLF):

```bash
git show HEAD:Scripts/patches/2026-09-30_K_passage_keys_follow_section.patch > "$TMP/K.patch"
git show HEAD:Scripts/patches/2026-09-30_L_retained_exit_leaves_no_gap.patch > "$TMP/L.patch"
```

**Stage 1: tests only.** Build, then run the three tests. Expect RED, and read
WHICH assertions fail (they should be the ones named below, not a fixture fault).

```bash
git apply --include='*/InfinityStagePassageKeyCarryTests.cpp' --include='*/InfinityStageHandoffGapTests.cpp' "$TMP/K.patch" "$TMP/L.patch"
```

- `InfinityStage.Editor.PassageKeysFollowSection`: expected red on "key N stays at
  the same section-relative frame" for the later Passage (keys left 24000 early).
  The Passage-moved and earlier-Passage assertions should pass.
- `InfinityStage.Editor.RetainedExitLeavesNoGap`: expected red on "cuts cover the
  whole Scene" and "the retained Exit starts where the designed shot ends" (Exit at
  216000, gap 120000–216000).
- `InfinityStage.Editor.ExitHoldSurvivesLengthening`: expected red on "the Exit is
  still a 24000-frame hold at the new end" (Exit at 240000 via the SetStartFrame
  clamp). Coverage should pass.

**Stage 2: fixes.** Build, then run the same three tests plus the full suite.
Expect GREEN.

```bash
git apply --exclude='*/InfinityStagePassageKeyCarryTests.cpp' --exclude='*/InfinityStageHandoffGapTests.cpp' "$TMP/K.patch" "$TMP/L.patch"
```

**Reading the results:**
- **Stage 1 red as expected, stage 2 green:** the fix is what changed it.
- **K red after stage 2, with the same assertions as stage 1:** `MoveSection` does
  not carry keys in 5.8. Replace K's `MoveSection` call with a per-channel key offset
  over the section's channel proxy.
- **Any stage-1 red on a different assertion, or a stage-1 green:** the test is not
  measuring what it claims. Fix the test before trusting stage 2.

Verified 30 Sep: both stages pass `git apply --check` on HEAD, and each selects
exactly its two files. Patch C (celestial) touches neither, so it applies in
either stage.
