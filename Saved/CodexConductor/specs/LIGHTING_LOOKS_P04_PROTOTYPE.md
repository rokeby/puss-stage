# Lighting looks prototype: P04, 6 bays (Gary, 3 Oct, his own words in the Conductor 4 session: "go ahead with this, full
# steam ahead" on the conductor's design: one instrument kit per wing bay, a vocabulary of looks as presets, looks keyed by
# camera distance; "varied sense of lighting ... from dark and moody to more theatrical (but rarely washed out lit)").
## Design (from the conductor's message; keep it)
Kit per bay: 2 TOP lights (rig above the pair, down), 2 LOW SIDE lights (trees on the fence walls, 0.5-1.6 m high, raking
across the flats; the ONLY shadow casters), 0-1 BEAM (behind the side wall, through a gap, back-lit for haze), 0-2 PRACTICALS
(bare bulb / work lamp / tube, visible, small, motivated), shared gobo where one exists.
Looks (presets over the same kit): MOODY (one side light 20-30%, alternate bays dark, practicals brightest, key:fill ~16:1,
cool ambient vs warm bulbs); INDUSTRIAL (sodium ~2000 K side light, a flickering tube, one beam); THEATRICAL (top + side
balanced, warm, gobos, ~4:1); plus SPOT and WASH defined but not used in this prototype.
## Read first
Docs/Conductor/LIGHTING_TALK_PREP_2026-10-03.md (if it exists yet; it inventories today's rig), how lights are authored on
Show cues (light attachments per wing pair; Plugins/InfinityStage/Source structs), Saved/CodexConductor/p01_warmer_apply.py
(attachment editing + GUID minting via replicate_light_attachments with a scratch pair: memory), how light intensity can be
KEYED over time/distance (existing light keys on passage sections or the Master; the hangar rise light channels are a reference
for keyed intensity), memory notes: puss-lighting-authoring-lessons (Show is truth; colour rectangles = VSM overflow; shafts need
back-light), puss-level-saved-landed-frame-trap, puss-light-replication-scope.
## Build (offline this pass)
1. A looks data file Saved/CodexConductor/lighting_looks.json (instrument recipes per look: intensity, colour temp/RGB,
   attenuation, cone, flicker) and a per-bay plan for P04 bays 1-6 (cue identity by index+GUID read fresh): bays 1-2 MOODY,
   3-4 INDUSTRIAL, 5-6 THEATRICAL, each look ramping in over ~1.5 m of camera travel as the camera approaches that bay.
2. Tool Saved/CodexConductor/lighting_looks_apply.py (DRY/APPLY/REVERT): adds the kit to those 6 bays as Show light
   attachments (keeping today's lights in those bays OFF or dimmed per look, recorded so REVERT restores exactly), keys the
   intensities by distance through the system's existing keying route (cite it; if no distance keying exists, key by Master
   time computed from the passage's distance/time anchors), materializes P04 only, narrow saves (Show + level), read-back,
   SavedMasterMatchesShow; the shadow-caster count for P04 before/after reported (budget: <= today's).
3. Harness with +/- controls (look recipes applied per bay; nothing outside bays 1-6 touched; shadow casters <= budget; revert
   exact). Run it. No Unreal this pass; commit nothing. Final message SHORT: the mechanism chosen (cited), fixture counts,
   shadow budget, open questions; tags per AGENTS.md.
## Next pass (editor, after Wings and Textures release): DRY/APPLY, then a PIE recording of P04 bays 1-6 (video, the window
## method of specs/PIE_TRANSITIONS_RECORDING.md, labels on) for Gary.
