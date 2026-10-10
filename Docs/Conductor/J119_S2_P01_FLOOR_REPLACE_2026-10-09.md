# Job 119 — replace the S2 hangar floor with P01-derived actors

Date: 9 October 2026. Status: **offline deliverable complete; Unreal DRY/APPLY/read-back and rendered acceptance pending**.

## Acceptance boundary

- **declaration-proven:** J118 names the persistent source as `Passage 01 - Opening Floor` and the targets as `S2 Hangar Floor 1-3` plus `S2 Hangar Apron` (`Saved/CodexConductor/J118S2FloorReflection_20261009/j118_floor_reflection_probe.py:16-19`). Job 119 uses exactly those labels and the vertical-slice persistent map (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py:24-27`).
- **measured (Gary, recorded by the conductor):** a P01 floor manually dragged into S2 reflected correctly; J118's PPV fix is superseded (`Docs/Conductor/J118_S2_FLOOR_REFLECTION_2026-10-09.md:103`). This job does not use or edit a PPV.
- **declaration-proven:** DRY/APPLY are plan-digest gated; APPLY also requires an explicit texel-density uncertainty acknowledgement (`j119_s2_p01_floor_replace.py:360-379`).
- **declaration-proven:** APPLY duplicates the P01 actor, fits it to each target, attaches it to the unchanged original actor, and moves only the old mesh component below stage (`j119_s2_p01_floor_replace.py:386-407`). It never deletes an original S2 actor.
- **declaration-proven:** the sequence audit scans LevelSequence assets and resolved actor, component and ancestor bindings (`j119_s2_p01_floor_replace.py:190-226`). Actor/ancestor transform and `bHidden` tracks are preserved through attachment; any relevant component-bound track blocks APPLY (`j119_s2_p01_floor_replace.py:78-92,374-375`).
- **inferred:** attachment/component visibility propagation will make actor-level `bHidden` sections govern each replacement. This is the intended UE hierarchy behavior, but it is not measured in this offline job; the stills plan explicitly tests every S2 visibility section and hangar-motion phase (`j119_s2_p01_floor_replace.py:304-310`).
- **inferred:** using the same P01 mesh and effective material preserves the desired mapping density. Scale can affect mesh-UV density unless the live material is world mapped. APPLY therefore requires acknowledgement and stills; it does not pretend property equality is rendered proof (`j119_s2_p01_floor_replace.py:302-303,378-379`).

## Mutation, save and revert contract

- **declaration-proven:** APPLY and REVERT require an initially clean editor, write a durable record and `Backups/PreJ119S2P01Floor-*` backup before mutation, allow only the persistent map to dirty, use `save_current_level`, and require a zero final census (`j119_s2_p01_floor_replace.py:241-274,381-385,420-437`).
- **declaration-proven:** Klara packages are a recorded forbidden set and are never named for save (`j119_s2_p01_floor_replace.py:29-30,301`).
- **declaration-proven:** post-save read-back requires the four exact tagged actor paths in the persistent map. The open map is deliberately not reloaded (`j119_s2_p01_floor_replace.py:423-436`).
- **declaration-proven:** REVERT accepts only the recorded/tagged replacement set, verifies the below-stage component transforms have not drifted, restores the old component locations, destroys only the owned duplicates, saves only the persistent map, and archives the record (`j119_s2_p01_floor_replace.py:330-355`).
- **not measured:** no Unreal API, MCP, PIE, package save, sequence resolution, live transform, collision, or rendered reflection was exercised; the brief required offline-only work.

## Run order

1. Run the checked-in DRY request and require `J119_S2_P01_FLOOR_REPLACE_DRY_OK`, four replacements, unchanged census, zero component-binding blockers, and review every unclear sequence row.
2. Review fitted transforms, scale ratios, actor ownership, sequence audit and stills plan in `j119_dry_<run>.json`.
3. Copy `plan_sha256` into args. Set `ack_texel_density_inferred=true` only after accepting the stills gate. Set `ack_sequence_scan_unclear=true` only after manually resolving every listed uncertainty.
4. Set `mode=APPLY`, `confirm=APPLY J119S2P01FLOOR`, and run once. Require APPLY marker, `created=4`, persistent map as sole save, `klara_saved=0`, zero final census, and `readback=1`.
5. Capture the five groups in `stills_plan`: matched P01/S2 grazing views, all four boundaries, every visibility section, hangar motion start/mid/end, and collision across joins. **Rendered acceptance is Gary's.**
6. If rejected, use `mode=REVERT`, `confirm=REVERT J119S2P01FLOOR`; require the REVERT marker and zero final census.

## Offline harness

- **measured:** `python Saved/CodexConductor/J119S2P01FloorReplace_20261009/test_j119_offline.py` passed **13/13**, with **8 positive and 8 negative controls** (`test_j119_offline.py:18-119`; `harness_result.json`).
- **measured:** `python -m py_compile` passed for the tool and harness.
- **declaration-proven:** static controls assert targeted save/backup, no `Save All`, persistent-only/Klara exclusions, correct guarded Saved route, `bHidden` rather than inert `bHiddenInGame`, and destruction restricted to recorded owned duplicates (`test_j119_offline.py:76-108`).

The remaining decision is live and visible: whether the P01 material's mapping keeps matching texel density after each exact-footprint fit. The tool exposes the scale ratios and refuses silent acceptance of that uncertainty.
