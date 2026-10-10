# Job 118 — P01 vs S2 hangar-floor reflection

Date: 9 October 2026. Status: **offline deliverable complete; live measurement pending**.

## Acceptance boundary

- **declaration-proven:** the delivered probe is read-only, refuses PIE/SIE and the wrong world, makes no
  Unreal save or mutation call, and requires dirty-package census before == after
  (`Saved/CodexConductor/J118S2FloorReflection_20261009/j118_floor_reflection_probe.py:271-286,336-367`).
- **declaration-proven:** its scope is P01 plus `S2 Hangar Floor 1-3` and `S2 Hangar Apron`; it also
  classifies persistent, Klara-streamed, and other-streamed PPVs
  (`j118_floor_reflection_probe.py:16-25,230-246`).
- **declaration-proven:** project defaults specify `r.ReflectionMethod=1` and Lumen hardware ray tracing
  (`Config/DefaultEngine.ini:14-21`).
- **measured (historical, not refreshed in this job):** the existing S2 material tool records that its four
  slabs were changed from the walnut MI to `/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet`
  (`Saved/CodexConductor/s2_floor_darkwet.py:1-13,38-61`). Gary's observation is that the saved look is
  nevertheless non-reflective.
- **inferred:** the cause is not established until `J118_S2_FLOOR_REFLECTION_PROBE_OK` and its JSON are read.
  Property read-back will still not be rendered acceptance.

## What the probe measures

### Tier 1 — effective floor material

For every static-mesh component on all five floor actors it reports mesh slot, component override,
effective render material, whether that material is an existing MID, and inherited/local rough/spec/wet
parameters. It reads serialized MI arrays rather than `MaterialEditingLibrary` getters, because those getters
have dirtied instances in this project (`Docs/CodexUnrealMCPRunbook.md:211-215`; probe:88-181).

Where UE 5.8 does not expose section-info remapping, the report says `UNCLEAR`/slot-index fallback; it does not
pretend slot index proves section index.

### Tier 2 — PPVs affecting each floor

For each unbound PPV or PPV containing a floor centre/sample corner, in the persistent map and Klara's loaded
streams, it reports level ownership, enabled/unbound, priority, blend weight/radius, containment method, and
override+value pairs for ReflectionMethod, Lumen quality/max roughness/screen traces, SSR
intensity/quality/max roughness, auto-exposure, and local-exposure contrast (probe:27-46,193-246).

### Tier 3 — S2 lighting/reflection environment and defaults

It reports nearby S2 local lights, all relevant skylights/directional lights, reflection captures, their level
owners and principal properties, plus RendererSettings and live reflection/hardware-RT cvars
(probe:248-335). No level is loaded or unloaded.

## Likely causes, ranked before the live result

1. **inferred — PPV precedence/override difference.** A Klara-streamed unbound or high-priority PPV can override
   reflection quality, max roughness, SSR or exposure at S2 while P01 sees a different stack. **Exact scoped
   fix:** use the held `j118_ppv_fix.py`: duplicate a Gary-selected *persistent* P01 PPV, bound it to the union
   of S2 Floor 1-3 + Apron (default 5 m XY padding, 2 m below, 45 m above), set priority to the highest S2
   contributor + 1, and save only the persistent map. Never edit/save Klara packages
   (`j118_ppv_fix.py:160-202,303-361`).
2. **inferred — the effective surface is not actually the same.** A section remap, component override, or
   existing MID may differ even when slot 0 prints `MI_Floor_DarkWet`. **Exact scoped fix:** after the probe
   names the mismatching actor/component/section, change only that persistent-level component override to the
   P01 effective interface; if it is a MID, remove only that override or copy the proved rough/spec/wet values.
   Record the component path and old interface; save only the persistent map. Do not edit the MI asset globally.
3. **inferred — S2 has no bright environment to reflect, or exposure suppresses it.** The same BRDF can look
   matte beneath flat/low-contrast lighting. **Exact scoped fix:** compare the measured S2 skylight and persistent
   S2 hangar lights with P01; adjust only named persistent S2 lights (or Show-owned S2 attachments through the
   Show+materialize route), one field at a time. Do not alter streamed Klara lights; require before/after stills.
4. **inferred — local reflection-capture coverage/fallback differs.** **Exact scoped fix:** if the probe proves
   Lumen is disabled/falling back and S2 lacks a covering capture, add one persistent-level capture bounded to
   the hangar, or reposition only an existing persistent S2 capture; save only the persistent map. Do not add a
   capture merely because Lumen reflections are visually weak.
5. **inferred, lowest — global reflection default/runtime cvar drift.** The declared project default is Lumen,
   and a global default alone cannot explain two simultaneously loaded locations. **Exact scoped fix:** no asset
   change unless live RendererSettings/cvar disagrees with config. If it does, first identify the console/profile
   source; restore `r.ReflectionMethod=1` at that source and re-probe, rather than masking it with level edits.

If a bounded volume visibly bleeds outside the hangar, the exact alternative is a **persistent-level** PPV with
a Master Sequence BlendWeight track: 0 before S2, 1 only across S2, 0 after. That would dirty/save the persistent
map and Master Sequence only and must be a separate reviewed tool. It must never possess or save a Klara-level PPV.

## Held fix: DRY / APPLY / REVERT

`j118_ppv_fix.py` defaults to DRY. It selects only a persistent P01-containing template, writes a durable record
and `Backups/PreJ118S2PPV-<run>` before mutation, duplicates into the persistent level, verifies bounds/settings,
permits only the persistent map dirty, and narrowly saves that map. REVERT backs up again, removes only the
tagged recorded actor, and saves only that map (`j118_ppv_fix.py:205-260,265-361`).

The copied P01 settings remain Gary's values; the tool invents no reflection/exposure look values. APPLY requires
`APPLY J118S2PPV`; REVERT requires `REVERT J118S2PPV`.

## Run order

1. Submit `j118_floor_reflection_probe_request.json` with `ExecuteProjectPythonFile`.
2. Require success marker, `saved=0`, and census equality; read `j118_probe_<run>.json`.
3. Put the chosen persistent P01 PPV label in `j118_ppv_fix_args.json`; run DRY and review the exact plan.
4. Gary approves APPLY; change mode+confirm and run once.
5. Require APPLY marker, zero final census, persistent map as sole saved package, and `klara_saved=0`.
6. Take matched P01/S2 stills. **Rendered acceptance is Gary's.** Use REVERT if rejected.

## Offline verification

- **measured:** `python test_j118_offline.py` — 13/13 passed, 8 positive and 8 negative controls.
- **measured:** both Python deliverables compile with system Python.
- **not measured:** Unreal API execution, live property values, saved read-back, and rendered result; offline-only
  brief forbade Unreal/MCP/PIE.

> **Conductor 10 Oct:** Gary dragged a P01 floor into S2 and it reflected correctly, which rules out PPV precedence. Use only the PROBE (it compares mesh, material and MID). The held PPV fix is superseded; do not apply it.
