# P42 — P06 sunset, car and bee proportional retime

Offline delivery, 9 October 2026. No Unreal Editor, MCP, PIE, build, Blender, Show asset, level, or binary Content
package was opened or changed during this worktree run.

## Verdict

- **[declaration-proven] READY AS A GUARDED TOOL, NOT APPLIED.** `p06_retime.py` implements DRY/APPLY/REVERT with exact
  confirmations, live compiled-length gating, a reviewed DRY hash, narrow hashed backups, an exclusive pre-change
  record, exact dirty-package scope, named saves, numeric read-back, and run-id success markers.
  `Saved/CodexConductor/p06_retime.py:120-139,199-290,387-401,642-732`
- **[measured] OFFLINE HARNESS PASS.** Positive controls passed 5/5 and negative controls passed 9/9, 22 assertions in
  total. The negatives cover pre-P33 length, an unknown post-P33 length, sunset/car/bee drift, a future time-keyed FX
  field, a wrong confirmation, missing APPLY review hash, and protected-Choreo drift.
  `Saved/CodexConductor/test_p06_retime_offline.py:69-152`
- **[inferred] FORECAST ONLY.** P33's 110.561125 s selection rounds up to a whole 25 fps display frame, so the expected
  live compiled length is 110.600 s. If DRY reads that value, `k = 0.8777699405` and the new W&T `--slam-s`/horizon is
  **32.477488 s**. This is derived arithmetic, not a saved Unreal read-back.
  `Saved/CodexConductor/passages_to_music.py:8-12,126-131,473-476`;
  `Docs/Conductor/Previews/P42_P06_RETIME_TIMELINE_2026-10-09.svg:1-41`
- **[UNCLEAR — saved/live state not inspected].** This worktree contains applied sunset and bee records, but
  `place_p06_car_light_record.json` and `P06FX_20261008/p06_fx_set_record.json` are absent. The exact four paths were
  tested offline. APPLY deliberately refuses without the car record; an absent FX-set record is a safe no-op because
  there is then no recorded FX set to retime. Production/main may differ and DRY is the authority.
  `Saved/CodexConductor/p06_retime.py:67-71,211-219,587-591`

## Retiming contract

| Holder | Tier | Operation after live P33 length is read |
| --- | --- | --- |
| Sunset | **[declaration-proven]** | Scale only P06 `cycle_duration_seconds` by live `k`; preserve animation flag, rate and phase. This proportionally moves fade 21.851, horizon 37, dark 52.149 and the black sample at 90 s. `Saved/CodexConductor/p06_sunset.py:9-18,145-168,363-387`; `Saved/CodexConductor/p06_retime.py:221-235` |
| Car | **[declaration-proven]** | Scale all non-zero segment-relative temporal fields: delay, travel, fade-in and fade-out. This preserves the 68.55 s midpoint proportionally. `Saved/CodexConductor/place_p06_car_light.py:1-9,31-43`; `Saved/CodexConductor/p06_retime.py:147-153,236-247` |
| Bee glints | **[declaration-proven]** | Move only the three owned spawn-key pairs, resize their owned sections/sequence, rename their labels truthfully, and resize the one owned Choreo sub-section. Foreign Choreo tracks are snapshotted and must read back unchanged. `Saved/CodexConductor/Effects_20261007/p06_bee_glints.py:17-21,37-48,768-780`; `Saved/CodexConductor/p06_retime.py:155-172,471-565` |
| P06 FX set | **[declaration-proven]** | No retime. Fire/motes activation uses rendered-view radius; WingBurn, if present, uses camera-route distance. The live attachments are snapshotted and must remain numerically unchanged. `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageEffectTypes.h:87-96,139-153`; `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageEffectSource.cpp:182-190,509-527,602-625,695-731`; `Saved/CodexConductor/p06_retime.py:175-196,568-586` |
| Topple chains A/B | **[declaration-proven]** | Never targeted. Master and topple packages are excluded; the only Choreo mutation is the uniquely named bee sub-section, with all other Choreo tracks compared before/after. `Saved/CodexConductor/p06_retime.py:284-285,471-497,545-565,642-653` |

## Expected 110.600 s forecast

**[inferred]** These are review values only. DRY recomputes them from the live compiled length and prints
`wt_slam_s` for W&T.

| Event | Old seconds | Forecast seconds |
| --- | ---: | ---: |
| Sunset fade begins | 21.851228 | 19.180351 |
| Horizon / W&T `--slam-s` | 37.000000 | **32.477488** |
| Effectively dark | 52.148772 | 45.774625 |
| Black sample | 90.000000 | 78.999295 |
| Car midpoint | 68.550000 | 60.171129 |
| Bee starts | 80 / 100 / 118 | 70.222 / 87.777 / 103.577 |

`Saved/CodexConductor/p06_retime.py:89-95,199-290,656-671`

## Package and recovery boundary

- **[declaration-proven]** APPLY and REVERT back up exactly four packages before mutation: Show, vertical-slice level,
  bee-glints sequence and P06 Choreo. They save exactly those packages and require a final `0+0` dirty census.
  `Saved/CodexConductor/p06_retime.py:284-285,387-401,642-653,675-732`
- **[declaration-proven]** The original sunset/car/bee records are read-only dependencies. The P42 record owns the
  compound reversal; therefore revert P42 before running any original tool's REVERT.
  `Saved/CodexConductor/p06_retime.py:587-591,675-732`
- **[declaration-proven]** No permanent deletion exists. REVERT archives the active P42 record with `os.replace`; it
  does not delete assets, bindings, tracks, records, or backups.
  `Saved/CodexConductor/p06_retime.py:706-732`

## Conductor run order

1. **[declaration-proven]** Apply P33 first and require its saved read-back marker. Do not run P42 if compiled P06 is
   still 126.001125 s; P42 reports `P33_NOT_APPLIED`.
   `Saved/CodexConductor/p06_retime.py:199-210`
2. **[declaration-proven]** Ensure the car placement has an applied record. Leave
   `Saved/CodexConductor/p06_retime_args.json` in DRY with `DRY P06 RETIME`, then execute
   `p06_retime_request.json`. Require `P06_RETIME_DRY_OK`, `apply_ready=1`, `mutated=0`, and record `wt_slam_s`.
   `Saved/CodexConductor/p06_retime_args.json:2-14`; `Saved/CodexConductor/p06_retime.py:656-673`
3. **[declaration-proven]** Review `p06_retime_dry.json` and the timeline preview. Copy its
   `plan.plan_sha256` into args, change mode/confirm to `APPLY` / `APPLY P06 RETIME`, then execute the same request.
   `Saved/CodexConductor/p06_retime.py:675-703`
4. **[declaration-proven]** Require `P06_RETIME_APPLY_OK`, four named packages, `fx=distance_view_unchanged`, and
   `dirty_after=0+0`. For reversal use `REVERT P06 RETIME`; require `P06_RETIME_REVERT_OK`.
   `Saved/CodexConductor/p06_retime.py:699-732`

## Acceptance boundary

- **[measured]** Python syntax, JSON parsing, SVG parsing and an explicit trailing-whitespace scan passed offline in
  this worktree.
- **[measured] COMMIT BLOCKED BY THE WORKTREE SANDBOX.** An explicit-path `git add` failed before staging because Git
  could not create `E:/PussStage/.git/worktrees/PussStage48/index.lock` (`Permission denied`). The deliverables remain
  complete and unstaged in this worktree; the conductor must stage and commit the seven named source/report files.
- **[UNCLEAR — prohibited by brief].** No saved Unreal read-back, runtime playback, rendered sunset/fire/motes/glints,
  audible car pass, or W&T/topple synchronization was tested. Those remain conductor/user acceptance after DRY/APPLY.
