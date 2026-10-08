# P18: Sky policy, editor auto-hide + show-side "no external sky" per Scene (Gary 8 Oct, own words)
Gary: "the skylight [should] be off for all scenes because there is simply no reason for an external skylight when ... all of Clara's scenes are basically in black box spaces or in the dark. Or else if she needs a specific skylight for a particular scene, then bring it in. But at the moment, in the editor, I'm seeing a ... default skylight, which I don't really want because it prevents me from being able to see the lighting in the scenes and passages."
Standing rule (Gary, earlier): the sky/skylight is ALWAYS off except in S06's sunset (which we key ourselves; actually P06's sunset, read Saved/CodexConductor/p06_sunset_record.json).
Measured tonight (conductor, PIE tap, pie_sky_tap.py):
- In Play, S1 has her L_Animals DirectionalLight at 17.37 and SkyLight at 0.8;
- S4 has her L_KK_children DirectionalLight at 4.88 and SkyLight at 1.0;
- every other Passage/Scene has no lit sky or sun.
- In the editor, every sky is hidden ONLY by the transient Saved/CodexConductor/editor_sky_toggle.py, which resets on every editor start or level reload. That's why Gary keeps seeing a sky.
Job:
1. **Editor auto-hide.** Make the editor hide external sky/skylight/atmosphere/cloud/sky-sphere and Klara's streamed-level suns automatically. Fire on editor start, on map open, and whenever a streamed level loads (the editor loads Klara's levels on demand). Keep it TRANSIENT (set_is_temporarily_hidden_in_editor), with zero package dirt and PIE unaffected.
   - Options: project Python startup (Content/Python/init_unreal.py, or the PythonScriptPlugin StartupScripts setting) registering delegates; or an editor-only C++ subsystem as a HELD patch.
   - Prefer Python if the delegates exist in 5.8 headers (cite them). Include an off switch (env var or a file flag).
   - Do NOT edit Config/*.ini directly: deliver the ini line as a held patch file in Scripts/patches/.
2. **Show-side sky policy for Play.** A DRY/APPLY/REVERT tool that, per Scene, forces her level's SkyLight (and optionally her sun) OFF during that Scene, without ever saving her levels (memory: never save Klara's streamed levels). Options: a visibility/intensity track in our LS_DevScene_0N copy bound to her actor, or a Show attachment/flag. Pick the one with precedent in Saved/CodexConductor/KlaraIngest (klara_reveal.py handles her lights).
   - Default plan: S4 skylight+sun OFF.
   - S1: OFF for the skylight only, sun kept, flagged "Gary to decide": S1 is a daylight scene and her sun is its key light; Gary said 7 Oct her daylight cinematic reads right.
   - Before/after luma needs a PIE probe; the conductor runs it.
3. A short message draft for Klara (Gary sends it), asking whether any of her scenes needs its own skylight.
Deliver Docs/Conductor/P18_SKY_POLICY_2026-10-08.md.
