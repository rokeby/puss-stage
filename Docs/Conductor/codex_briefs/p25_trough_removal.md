# P25: remove the P01 portal float trough and the lip lamp housings (Gary 8 Oct: "Remove them")
Context: the stage floor extends forward to x -480 (paper proscenium, Blender MCP Hyper3D, DerivedAssets/StageFront_PaperProscenium/
PAPER_PROSCENIUM_SPEC.md); tonight's ragged curtain bake uses colliders WITHOUT the trough + 16 lamp housings
(Saved/CodexSoftGoods/DropBake/ragged_prep/StageFrontColliders_2026-10-08_proscenium.json, "trough + 16 housings + old fascia dropped").
Facts: the trough is FInfinityStagePortalSettings.bFloatTrough (Plugins/InfinityStage/Source/InfinityStage/Public/
InfinityStageStructureActor.h:308; built at InfinityStageStructureActor.cpp:1653-1660). Precedent tool for a portal setting +
structure re-fit + level save: Saved/CodexStructure/portal_enable_apply.py (+ revert, counts guard COUNTS).
The 16 "lamp housings": IDENTIFY them offline from records/source (the collider set that listed them; Docs/ChaosClothCurtain.md
:117-146 "lamp-housing fixtures"; Saved/CodexStructure/p01_lip_floats_* was NEVER applied, no record) -> which actors/attachments
/ISM components they are, and whether they are Show attachments (remove via Show + materialize) or structure fixtures.
Job: one tool p01_lip_clear.py (DRY/APPLY/REVERT, confirm "<MODE> LIPCLEAR"): bFloatTrough=false on Structure 01's portal +
re-fit with the portal_enable count guard (only portal_piece_count may change, by exactly the trough's pieces), and removes/
disables the 16 housings by the mechanism you identify. Exact census, backups, read-back, marker. Harness +/- controls.
Report which identification is declaration-proven vs inferred.
