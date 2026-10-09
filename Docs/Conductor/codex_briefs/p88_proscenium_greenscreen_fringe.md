# P88 — Paper proscenium: remove the greenscreen fringe (Codex, offline)

Read `_house_rules.md`. Offline only. Gary 9 Oct: "the new front stage wings have a greenscreen fringe on them".
Assets: the paper proscenium placed 9 Oct (W&T: PAPERPROSC-20261009-002351, manifest `Saved/CodexFlatV3/paperprosc/`,
thick5 build; source images/alpha under DerivedAssets/FlatV3 / paperprosc). Dedupe: FlatV3 skin pipeline
(`Tools/FlatV3/`) may already have a despill/edge-erode step — reuse it.
Build: diagnose where the green comes from (unpremultiplied colour bleeding at alpha edges, mip bleeding, a green key
residue in the source), then an offline fix: despill (clamp G to max(R,B) near edges) + colour-dilate under alpha
(edge padding) + optional 1–2 px alpha erode, regenerating the affected textures as NEW files/version (never overwrite
the originals). Provide a DRY/IMPORT tool that reimports only those textures into NEW assets and swaps the MI texture
params (revertible). Before/after crops PNG for Gary. Memory: flatv3-skin-rebuild-rerolls-peel (don't re-run build_skin;
patch the band only). Tiered report; worktree only.
