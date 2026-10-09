# Codex job 70 — P40 component-count identity repair

Date: 2026-10-09. Offline only. Worktree base: `9d37c03e`. No commit created.

## Outcome

- **declaration-proven:** Every P40 component cardinality gate now collapses repeated discovery handles by full UObject path and refuses unless exactly one distinct path remains. This covers named Blueprint templates, outfit templates, preflight Body and Chaos cloth templates, spawned Body and cloth components, and placed-actor outfit components (`Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:147`, `:161`, `:641`, `:643`, `:847`, `:859`, `:919`).
- **declaration-proven:** Selection audits retain raw count, unique count, collapsed duplicate count, candidate paths, and selected path. Preflight and APPLY records therefore show why a repeated listing passed rather than hiding it (`p40_editor.py:147-172`, `:645-647`, `:864-866`).
- **declaration-proven:** The DRY preflight emits a final inventory of all remaining P40 `*_COUNT` gates, including the two argument-count gates in `p40_core.py`; the harness asserts that all seven component gates use `full_object_path` identity (`p40_editor.py:53-68`, `:682`; `test_p40.py:162-178`, `:496`).

## Regression proof

- **measured (offline):** `python Saved/CodexConductor/P40Shore05Settle_20261009/test_p40.py` passed **45/45**: positive **15/15**, negative/regression **30/30**, Unreal **0**, Blender **0**. The generated evidence is `Saved/CodexConductor/P40Shore05Settle_20261009/p40_harness_report.json`.
- **measured (offline):** The new Body regression proves all requested branches: the old raw `len(rows) == 1` logic refuses two listings; the new path-identity logic accepts two rows with the same full path; adding a second distinct Body path refuses with `unique=2` (`test_p40.py:139-159`).
- **measured (offline):** `python -m py_compile ...p40_editor.py ...test_p40.py` and `git diff --check` both exited 0.
- **user-reported measured elsewhere, not re-measured here:** live DRY `P40SHORE-20261009-105632` and the SHROUDBP probe showed duplicate `k2_gather_subobject_data_for_blueprint` rows. This worktree has no `Saved/Logs`, so those live logs were unavailable for independent citation.

## Remaining count gates (final self-check)

`EXTRA_COUNT`, `CANDIDATE_COUNT`, `CAMERA_TRANSFORM_CHANNELS_COUNT`, `TRANSFORM_CHANNELS_COUNT`, `CAMERA_BASE_SECTION_COUNT`, `TEMPLATE_COUNT`, `OUTFIT_TEMPLATE_COUNT`, `SHORT_PARENT_COUNT`, `PREFLIGHT_BODY_COMPONENT`, `PREFLIGHT_CLOTH_COMPONENT`, `BODY_COMPONENT`, `CLOTH_COMPONENT`, `ACTOR_OUTFIT_COMPONENT`, `ACTOR_COUNT`.

- **declaration-proven:** The seven component gates use full object path identity.
- **declaration-proven:** Shorts parents use deduplicated asset paths; transform channels use canonical channel names; the other gates retain their existing non-component semantics.
- **inferred / live acceptance pending:** A rerun of the conductor's live DRY should now pass the three Shore05 placement preflights if duplicate component listings were their only blockers. No Unreal, MCP, PIE, asset save, or rendered verification was run by this job.

## Conductor run

1. Review the uncommitted diff and the 45/45 harness report.
2. Run the existing P40 DRY command with a fresh run id; do not APPLY merely from this offline result.
3. Confirm the DRY report's `apply_preflight.blueprints[*].body_discovery` and `cloth_discovery`: duplicated listings should show `raw_hit_count=2`, `unique_candidate_count=1`, `duplicate_handles_collapsed=1`.
4. Require `apply_ready=true`, exact dirty-package census unchanged, and the normal P40 success marker before considering APPLY.

Open question: none in the offline patch. Live DRY remains the acceptance boundary.
