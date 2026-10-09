# Codex job 94 — P03 to S3 blackout, effect gate, and post-crowd rise

Offline delivery only. Unreal and Blender were not opened. No Show, map, or
binary asset was changed in this worktree.

## Dedupe result

- **[measured, repository]** This is not a replacement fire tool. Commit
  `52fb36a3` already bound the fire visibility tracks to `bHidden`, removed four
  duplicate bindings, and applied P28 `fires_together`; the morning report says
  Fire B/C ignite at frame 230 with a 72-frame ramp and Fire A remains off
  (`Docs/Conductor/MORNING_REPORT_2026-10-09.md:11-12`).
- **[measured, repository]** P21C already created exactly 15 crowd copies; the
  applied record names all 15 (`Saved/CodexConductor/s3_crowd_structure_record.json:761-776`).
- **[declaration-proven]** The P21 authoring code gives those copies their first
  visible key at LS_Clams frame `360 + 22 = 382`
  (`Saved/CodexConductor/s3_crowd_structure.py:734-741,994-995`).
- **[inferred]** The narrow repair is therefore coordination of the existing
  hangar, crowd, and fire timelines, not another actor/fire/crowd system.

## Current timeline census

The root S3 sequence is 24 fps. `LS_S3_HangarRise` is 30 fps and occupies the
first 31 seconds, so child times below are converted to S3-root time.

| Authority / elements | Exact census | Current keys | Current visible consequence | Tier |
|---|---:|---|---|---|
| Hangar practicals | 14 intensity channels | child -176→124 (0→160), i.e. -5.867→4.133 s | Their authored linear ramp is already in progress at S3 frame 0 | measured keys + declaration-proven linear authoring; representative `Saved/CodexConductor/S3Diag/rise_now_sem.json:3323-3353`, authoring `Saved/CodexStructure/hangar_build.py:496` |
| Lattice glows | 24 intensity channels | child -176→124 (0→8) | Their authored linear ramp is already in progress at S3 frame 0 | measured keys + declaration-proven linear authoring; representative `Saved/CodexConductor/S3Diag/rise_now_sem.json:2399-2429`, authoring `Saved/CodexStructure/hangar_build.py:496` |
| Strike lights | 6 intensity channels | child 0,300,306; dark→full at 10.0→10.2 s | Full before crowd copies appear | measured offline; representative `Saved/CodexConductor/S3Diag/rise_now_sem.json:1032-1064` |
| Uplights | 3 intensity channels | first 10.0→10.2 s; later rows stagger through 10.5 s | Full before crowd copies appear | measured offline; first row `Saved/CodexConductor/S3Diag/rise_now_sem.json:1211-1243` |
| Daylight | 2 intensity channels | child 0,300,306; dark→full at 10.0→10.2 s | Full before crowd copies appear | measured offline; representative `Saved/CodexConductor/S3Diag/rise_now_sem.json:1510-1542` |
| Fire B/C actor visibility | 2 `bHidden` visibility channels | shown at root 230 = 9.583 s | Fire-bearing actors can render before crowd arrival | measured upstream PIE + read-back, `MORNING_REPORT_2026-10-09.md:11-12` |
| Ghost flame actor visibility | 1 `bHidden` visibility channel | shown at root 183 = 7.625 s | Torch/fire particle actor appears still earlier | measured upstream PIE, `MORNING_REPORT_2026-10-09.md:11` |
| Fire B/C light | 2 intensity channels | common ignition 230; 72-frame ramp ends 302 = 12.583 s | Fire illumination completes 2.417 s before crowd copies | measured applied args, `Saved/CodexConductor/S3Polish_20261009/s3_polish_args.json:12-13` |
| Ghost light | 1 intensity channel | dark at 183; first lit key 195 = 8.125 s, then flicker | Its separate light can illuminate before the flame actor gate is sufficient | measured saved record, `Saved/CodexConductor/s3_fires_record.json:8-24` |
| Crowd keys/rims | 6 intensity channels | dark through 360; rise 360→408 = 15.0→17.0 s | Rise begins on the same frame the copies appear, leaving no settle interval | declaration-proven applied authoring, `Saved/CodexConductor/s3_crowd_lights.py:29-38` |
| WaveV3/flame rects | 10 intensity channels | dark through 360; rise 360→384 = 15.0→16.0 s | A second light family also rises on the copy reveal frame | declaration-proven applied authoring, `Saved/CodexConductor/s3_rect_on_at.py:1-7` |
| Crowd-copy presence | 15 possessable visibility channels (not spawn tracks) | LS_Clams 382 = root 360 = 15.0 s | Copies appear after all listed lighting/fire starts | declaration-proven authoring `Saved/CodexConductor/s3_crowd_structure.py:981-995` + measured applied record, citations above |

**[measured, offline]** Exact nested-hangar light total is 49 = 14 + 24 + 6
+ 3 + 2. The root-arrival census adds 19 lights = 3 ghost/fire + 6 crowd +
10 WaveV3/flame rects. The delivered DRY re-counts every live binding and refuses on any
drift. **[inferred]** The timing order directly explains Gary's observation:
the dim rig is already rising at entry, strike/daylight/fire are established by
12.6 s, and the 15 copies do not appear until 15 s.

## Delivered behavior

- **[declaration-proven]** Default plan: crowd copies become visible at root
  frame 360; maintain total S3-side darkness for a 12-frame settle pad; start all
  enumerated hangar lights plus Ghost/B/C fire visibility at frame 372 (15.5 s);
  reach the authored light levels over 72 frames at frame 444 (18.5 s)
  (`Saved/CodexConductor/P94S3Arrival_20261009/p94_s3_arrival.py:43-61`).
- **[declaration-proven]** `APPLY` retimes the 49 existing hangar channels,
  three fire-actor visibility tracks, three ghost/fire light tracks, six crowd
  lights, and ten WaveV3/flame rect lights. The WaveV3 one-second rise is
  stretched to the same three-second envelope. It does not create actors or
  bindings. It also
  repairs only the 15 P21 visibility tracks whose property is still unset,
  binding them as (`bHidden`, `bHidden`) without inverting their already-visible
  polarity (`Saved/CodexConductor/P94S3Arrival_20261009/p94_s3_arrival.py:390-568,674-722`).
- **[declaration-proven]** A fire visibility track hides the whole P_Fire actor,
  so its flame and particle smoke cannot float early. DRY separately inventories
  S3/P03-labelled smoke, haze, and fog actors; APPLY refuses any unacknowledged
  candidate rather than guessing its ownership
  (`Saved/CodexConductor/P94S3Arrival_20261009/p94_s3_arrival.py:445-581,675-678`).
- **[inferred]** The 12-frame settle pad and 3-second rise are conservative
  defaults, not creative acceptance. Gary can change both in `p94_args.json`.

## Safety, records, saves, and read-back

- **[declaration-proven]** All three modes require exact confirmation, the
  vertical-slice world, no PIE/SIE, closed Sequencer, and a zero dirty-package
  census. APPLY writes `p94_record.json` and
  `Backups/PreP94S3Arrival-<run>` before its first mutation
  (`Saved/CodexConductor/P94S3Arrival_20261009/p94_s3_arrival.py:278-299,586-598,674-686`).
- **[declaration-proven]** The only possible save scope is the dirty subset of
  `LS_DevScene_03`, `LS_S3_HangarRise`, and `LS_Clams`. The exact dirty census
  must equal that subset; no map is saved. Post-save census must be zero
  (`Saved/CodexConductor/P94S3Arrival_20261009/p94_s3_arrival.py:633-645`).
- **[declaration-proven]** Read-back resolves bindings by one cached
  `GuidLibrary.conv_guid_to_string` value, verifies every key frame and property,
  and writes SHA-256 values to the record. REVERT restores recorded frames,
  values, and property/path, then archives the record
  (`Saved/CodexConductor/P94S3Arrival_20261009/p94_s3_arrival.py:197-199,647-672,724-751`).
- **[inferred]** Saved read-back proves authored state, not the rendered result.
  Use `STILLS_PLAN.md`; the short scrub clip is mandatory because stills cannot
  disprove a one-frame pop or particle pre-roll
  (`Saved/CodexConductor/P94S3Arrival_20261009/STILLS_PLAN.md:1-24`).

## Conductor run order

1. Copy this worktree's `Saved/CodexConductor/P94S3Arrival_20261009` folder to
   the active `E:/PussStage/Saved/CodexConductor/` path if it is not already
   present.
2. Run `test_p94.py` offline. Expected: `22/22`.
3. With a clean editor and correct map, run shipped DRY. Read the JSON plan and
   resolve every `effect_census.unexpected` item by ownership; add only reviewed
   exact labels to `allowed_unmanaged_effect_labels`.
4. Change args to APPLY, set a fresh run id and `APPLY P94S3ARRIVAL`; run once.
5. Require `P94_S3_ARRIVAL_APPLY_OK`, zero dirty packages, the recorded package
   SHAs, and the read-back timeline.
6. Execute the stills/clip plan. If rejected, use REVERT with a fresh run id and
   `REVERT P94S3ARRIVAL`.

## Verification reached

- **[measured, offline]** Harness: 22 positive/negative cases passed, 0 failed
  (`Saved/CodexConductor/P94S3Arrival_20261009/harness_result.json:1-95`).
- **[measured, offline]** No Unreal, PIE, MCP, Blender, asset save, or rendered
  review occurred.
- **[inferred]** Live DRY may find newly changed bindings or unmanaged effects;
  its refusal is the intended handoff boundary, not permission to broaden scope.
