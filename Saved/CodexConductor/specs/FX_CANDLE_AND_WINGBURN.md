# First effects: S6 candle + a WingBurn test on a P06 V3 wing (Gary, 2 Oct night, his own words in the Conductor 4 session:
# "candle and wingburn are nicely discrete effects let's put them on soon"; S6 sketch: a CANDLE, "realistic flame and
# candlelight if possible", fog haloing its light: Docs/Scene6BeatSheet_2026-10-02.md).
Read first: Docs/EffectsSourcesDesign.md IN FULL (the built system: source kinds incl. Fire with a linked flicker light,
WingBurn driven by camera travel, the custom-data handshake with Wing materiality, how sources are authored as Show data and
materialized: hook B), the InfinityStage Effects source/headers it cites, Docs/WingMateriality.md (burn path),
Docs/FlatV3Status.md (P06 rows; V3 materials), memory rules in AGENTS.md (proof tiers; Show is the authority).
## A. S6 candle (test placement; Gary adjusts look and position in PIE)
- Prefer the built Fire source kind with its linked light (no new C++). Flame: a small realistic candle flame (Niagara: an
  engine template or a simple sprite/mesh flame with flicker; ~2-3 cm wide, ~4 cm tall) on a simple candle mesh (wax
  cylinder ~2 cm diameter x 10 cm). Light: a warm point light ~1900 K, low intensity, flicker small and organic, soft
  shadows on; attenuation suited to a dark void (~6-8 m), and the hangar fog should halo it (report whether volumetric
  scattering is on for that light).
- Where: S6 landed hangar centre at table height (~110 cm), authored the way the system authors sources (Show data / the
  S6 scene), not a loose level actor, unless the design doc says scene props are level actors (cite it).
- Visible from S6's arrival onward for now (timing to the beats comes later).
## B. WingBurn test on ONE P06 V3 wing
- First, read-only: do the P06 V3 Front/Flap materials (MI parents) support the burn custom data (BurnProgress slot 0, ignition
  UV 1-2) that WingBurn writes? Cite the material graph or the MI parent. If NOT supported: STOP part B and report what's
  needed (Wing materiality's master vs the V3 master).
- If supported: author ONE WingBurn source on P06 position 32 (the last V3 position; a TEST, since the narrative burn belongs to
  beats 4+), default ignition (0.5, 1.0), BurnStartAheadCm/BurnSpanCm from the design defaults; reversible.
## THIS PASS: offline only. Write the tools (Saved/CodexConductor/fx_candle_s6.py and fx_wingburn_test.py, each DRY/APPLY/
REVERT with backups of the Show/level/assets they touch, census, read-back, SavedMasterMatchesShow after), plus offline
harnesses. No Unreal now (the editor is busy). Final message: the design facts you relied on (file:line), the tools, the open
questions, tagged per AGENTS.md. Commit nothing.
