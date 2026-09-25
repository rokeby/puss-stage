"""Thin the medium right down and make beams come from a few strong fixtures rather
than every light glowing. Applies to editor and PIE worlds. No save."""
import json, os, re, unreal
EXPECTED_WORLD = "L_InfinityStage_V1VerticalSlice"
DENSITY    = float(os.environ.get("PUSS_FOG_DENSITY", "0.022"))
FALLOFF    = float(os.environ.get("PUSS_FOG_FALLOFF", "0.12"))
EXTINCTION = float(os.environ.get("PUSS_FOG_EXTINCTION", "0.9"))
BASE_SCATTER  = float(os.environ.get("PUSS_SCATTER_BASE", "0.6"))
BEAM_SCATTER  = float(os.environ.get("PUSS_SCATTER_BEAM", "9.0"))
BEAM_EVERY    = int(os.environ.get("PUSS_BEAM_EVERY", "4"))      # one beam bay in N
BEAM_SLOTS    = {"Cross +Y", "Cross -Y"}
ROW = re.compile(r"^P(\d{2}) Wing (\d{3}) (.+)$")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
ew = ed.get_editor_world(); assert ew and EXPECTED_WORLD in ew.get_path_name(), "wrong project"
worlds = [("editor", ew)] + ([("pie", ed.get_game_world())] if ed.get_game_world() else [])
report = {}
for tag, w in worlds:
    for f in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ExponentialHeightFog):
        if not f.get_actor_label().startswith("Infinity Stage"): continue
        c = f.get_component_by_class(unreal.ExponentialHeightFogComponent); f.modify()
        c.set_editor_property("enable_volumetric_fog", True)
        c.set_editor_property("fog_density", DENSITY)
        c.set_editor_property("fog_height_falloff", FALLOFF)
        c.set_editor_property("volumetric_fog_extinction_scale", EXTINCTION)
    base = beams = 0
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Light):
        m = ROW.match(a.get_actor_label())
        if not m: continue
        lc = a.get_component_by_class(unreal.LightComponent)
        if not lc: continue
        ordinal, slot = int(m.group(2)), m.group(3)
        # A shaft every Nth bay, from the two cross spots only: rhythm, not soup.
        is_beam = (ordinal % BEAM_EVERY == 1) and (slot in BEAM_SLOTS)
        lc.set_editor_property("volumetric_scattering_intensity", BEAM_SCATTER if is_beam else BASE_SCATTER)
        lc.set_editor_property("cast_volumetric_shadow", bool(is_beam))
        beams += int(is_beam); base += int(not is_beam)
    report[tag] = {"beam_lights": beams, "base_lights": base}
json.dump({"density": DENSITY, "falloff": FALLOFF, "extinction": EXTINCTION,
           "base_scatter": BASE_SCATTER, "beam_scatter": BEAM_SCATTER, "beam_every": BEAM_EVERY, "worlds": report},
          open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "haze_beams.json"), "w"), indent=1)
unreal.log(f"HAZE_BEAMS|density={DENSITY}|falloff={FALLOFF}|ext={EXTINCTION}|base={BASE_SCATTER}|beam={BEAM_SCATTER}|every={BEAM_EVERY}|{report}|saved=0")
