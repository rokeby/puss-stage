# Codex job 93 — P03 wing interleave + dark-wet floor

Offline delivery only. No Unreal, MCP, PIE, Blender, package save, or render was run in this worktree.

## Dedupe and exact census

- **Measured (saved-record reconstruction, not current-live):** Gary asks for the three old square P03 wings to be
  interleaved with the green wings and for the shiny floor (`Docs/Conductor/GARY_PIE_NOTES_2026-10-09_evening.md:15`).
  The latest applicable materialized-cue record contains exactly **21** P03 WingPair rows: the first three are the
  paired V2 `SunWashedAdministration`, `YellowCurtainThreshold`, and `GlassBlockClassroom` meshes
  (`Saved/CodexConductor/Effects_20261007/fx_smoke_place_report_APPLY_20261007-103503.json:1816-1832`), followed by
  18 rows through Wing 021 (`Saved/CodexConductor/Effects_20261007/fx_smoke_place_report_APPLY_20261007-103503.json:1834-1940`). The independent audit
  also identifies Wing 003, 002 and 001 L/R as the six low-density V2 sides (`Saved/CodexFlatV3/p02p03_audit/AUDIT.md:23-31`).
- **Measured (deterministic plan over that saved census):** proposed cue-label order is
  `001, 004, 005, 006, 007, 008, 009, 003, 010, 011, 012, 013, 014, 015, 002, 016, 017, 018, 019, 020, 021`.
  Labels are not renumbered: cue GUID is identity, so the wing pair and its mechanism/attachments move together.
- **Measured (saved-record reconstruction, not current-live):** the P03 floor record names exactly one slab,
  `Passage 03 - Floor`, with one material slot containing the walnut instance
  (`Saved/CodexConductor/p03_floor_record.json:15-40`).
- **Declaration-proven:** repository/commit search found relayout and dark-wet precedents but no existing E11/Job 93
  tool. P06's landed precedent writes a reordered cue list, materializes one passage, backs up Show+level, and performs
  targeted saves (`Saved/CodexFlatV3/p06relayout/relayout_apply.py:402-437,508-529`).
- **UNCLEAR until live DRY:** the editor's current 21-row order, meshes, exact dirty-package census, P03 actor count,
  materialized count, and floor material. Both DRYs refuse mutation and produce the current exact census/read-back.

## Delivered behavior

- **Declaration-proven:** WINGS keeps all 21 cue GUIDs and places the three legacy pairs at one-based ordinals
  **1, 8, 15**, leaving six newer rows between each and six after the last. It copies interval/gap values by ordinal,
  so the compiled station/timing slots remain unchanged; whole cue objects carry panels, mechanisms and attachments.
  Classification requires the expected labels, stable GUIDs via `GuidLibrary.conv_guid_to_string`, and both legacy mesh
  roots. Enum strings are normalized from UE 5.8's `<E.V: n>` form
  (`Saved/CodexConductor/P93_P03InterleaveFloor_20261009/p93_core.py:7-14,48-126`).
- **Declaration-proven:** FLOOR changes only material slot 0 on exactly one `Passage 03 - Floor` StaticMeshComponent to
  `/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet`; transform is accessor-read and hash-guarded
  (`Saved/CodexConductor/P93_P03InterleaveFloor_20261009/p93_live.py:211-238,377-447`).
- **Declaration-proven:** APPLY/REVERT require hash-bound confirmations, clean start, sha256-verified pre-change
  backups, exact dirty scope, named saves only, post-save read-back, clean final census, run-id success markers, and
  persistent records. WINGS saves Show+level and materializes only P03; FLOOR saves level only. REVERT is field-scoped
  and preserves later non-owned cue edits. Records are retained; nothing is deleted
  (`Saved/CodexConductor/P93_P03InterleaveFloor_20261009/p93_live.py:240-270,285-375`).
- **Measured (offline):** `python test_p93_offline.py` passes **23/23**, 0 failures/errors, with positive and negative
  controls (`Saved/CodexConductor/P93_P03InterleaveFloor_20261009/offline_harness_report.json:1-7`). Syntax compilation also passes.
- **Inferred / visual choice:** ordinals 1/8/15 are the most even distribution that keeps the first legacy pair at the
  mouth and gives 6/6/6 newer rows between/behind. Gary must accept the rendered rhythm; see
  `Saved/CodexConductor/P93_P03InterleaveFloor_20261009/p03_interleave_preview.svg:1-32` (diagram, not a render).

## Ordered conductor run

1. Run `python Saved/CodexConductor/P93_P03InterleaveFloor_20261009/test_p93_offline.py`.
2. Copy `p93_args.example.json` to `p93_args.json`; execute `p93_request.json` with WINGS DRY. Require
   `P93_P03_WINGS_DRY_OK`, exact `21/3/18`, zero dirty packages, and review the JSON/token plus SVG.
3. Set WINGS APPLY and `APPLY P93WINGS <token>`; execute once. Require `P93_P03_WINGS_APPLY_OK`, materialized=21,
   saved=show,level, dirty_after=0+0.
4. Run FLOOR DRY. Require `P93_P03_FLOOR_DRY_OK`, actors/components/slots=`1/1/1`, walnut source or already-target.
5. If not already target, run FLOOR APPLY with `APPLY P93FLOOR <token>`. Require `P93_P03_FLOOR_APPLY_OK`,
   saved=level, dirty_after=0+0.
6. Only after the clean saved read-back, start one conductor-owned PIE and capture the stills below. End PIE from the
   same conductor session. Commit tools plus generated DRY/APPLY records after review.

REVERT is the same request with `REVERT P93WINGS <apply-run-id>` or `REVERT P93FLOOR <apply-run-id>`; revert the floor
and wings independently as needed.

## Stills plan and acceptance

- **Measured stills requested; not captured here:** fixed Master camera/exposure/FOV, before and after at P03 5%, 33%,
  66%, and 90%. Contact sheet must show legacy squares separated in depth, no missing/duplicated pair, and no obvious
  attachment/mechanism discontinuity.
- **Measured stills requested; not captured here:** matching low grazing floor shots at P03 entry and midpoint, plus
  P01 and P02 reference shots under comparable lighting. Accept only if P03 visibly reads dark/wet and continuous;
  material-path read-back alone is not visual acceptance.
- **UNCLEAR / Gary:** whether ordinals 1/8/15 create the intended rhythm and whether the dark-wet response is strong
  enough under P03 lighting. The tools deliberately expose no aesthetic scalar and apply no lighting change.
