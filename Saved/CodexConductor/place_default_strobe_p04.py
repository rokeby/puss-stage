"""Gary 5 Oct: place ONE default strobe (1 s, point light, preset subtle ghost) in P04 for him to try and move.

Spawns AInfinityStageStrobeLight + a bounded PostProcessVolume (cueing spec SPEC_STROBE_2026-10-05.md 'Preset ghost
volume'), composed against the LIVE P04 Passage actor transform, backs up the level first, saves ONLY the level, reads back.
Refuses on PIE, a dirty census, or if a strobe with the same label already exists.
"""
import datetime
import json
import os
import shutil

import unreal

RUN = datetime.datetime.now().strftime("STROBE-%Y%m%d-%H%M%S")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LABEL = "P04 Strobe (default, Gary to place)"
PPV_LABEL = "P04 Strobe Ghost Volume (PPV_StrobeGhost_Subtle)"
LOCAL = unreal.Vector(2000.0, 650.0, 60.0)   # along P04's route, house-right, just above the floor [inf: route along local +X]


def stop(msg):
    unreal.log_error("STROBE_PLACE_STOPPED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if ed.get_game_world() is not None:
    stop("PIE_ACTIVE")
if census() != {"content": [], "maps": []}:
    stop("DIRTY_BEFORE|" + json.dumps(census()))
cls = getattr(unreal, "InfinityStageStrobeLight", None)
if cls is None:
    stop("STROBE_CLASS_MISSING")
actors = actors_sub.get_all_level_actors()
if any(str(a.get_actor_label()) in (LABEL, PPV_LABEL) for a in actors):
    stop("ALREADY_PLACED")
p04 = [a for a in actors if a.get_class().get_name() == "InfinityStagePassageActor"
       and str(a.get_actor_label()).startswith("Passage 04")]
if len(p04) != 1:
    stop("P04_ACTOR_COUNT|%d" % len(p04))
xf = p04[0].get_actor_transform()
loc = unreal.MathLibrary.transform_location(xf, LOCAL)
backup = "E:/PussStage/Backups/PreDefaultStrobe-" + RUN
os.makedirs(backup)
shutil.copy2(UMAP, backup)

ppv = actors_sub.spawn_actor_from_class(unreal.PostProcessVolume, loc, unreal.Rotator(0, 0, 0))
ppv.set_actor_label(PPV_LABEL)
ppv.set_actor_scale3d(unreal.Vector(12.0, 12.0, 6.0))      # 1200 x 1200 x 600 cm box (default brush 100 cm)
ppv.set_editor_property("unbound", False)
ppv.set_editor_property("blend_radius", 300.0)
ppv.set_editor_property("priority", 10.0)
ppv.set_editor_property("blend_weight", 0.0)
s = ppv.get_editor_property("settings")
for name, value in (("bloom_intensity", 2.0), ("bloom_threshold", 0.5), ("auto_exposure_bias", 0.4),
                    ("motion_blur_amount", 0.9), ("motion_blur_max", 8.0)):
    s.set_editor_property("override_" + name, True)
    s.set_editor_property(name, value)
s.set_editor_property("override_scene_color_tint", True)
s.set_editor_property("scene_color_tint", unreal.LinearColor(1.0, 1.0, 1.04, 1.0))
ppv.set_editor_property("settings", s)

strobe = actors_sub.spawn_actor_from_class(cls, loc, unreal.Rotator(0, 0, 0))
strobe.set_actor_label(LABEL)
wanted = {"period_seconds": 1.0, "flash_seconds": 0.04, "decay_seconds": 0.33, "ghost_seconds": 0.33,
          "ghost_max_weight": 1.0}
applied = {}
for k, v in wanted.items():
    try:
        strobe.set_editor_property(k, v)
        applied[k] = float(strobe.get_editor_property(k))
    except Exception as exc:  # noqa: BLE001 -- report the real property names, never guess silently
        applied[k] = "ERR %s" % exc
try:
    strobe.set_editor_property("ghost_volume", ppv)
    applied["ghost_volume"] = str(strobe.get_editor_property("ghost_volume").get_actor_label())
except Exception as exc:  # noqa: BLE001
    applied["ghost_volume"] = "ERR %s" % exc
bad = {k: v for k, v in applied.items() if isinstance(v, str) and v.startswith("ERR")}
if bad:
    stop("PROPERTY_NAMES|" + json.dumps(bad) + "|NOTHING SAVED; Don't-Save restart")
dirty = census()
if dirty["content"] or dirty["maps"] != [WORLD]:
    stop("DIRTY_SCOPE|" + json.dumps(dirty))
if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
    stop("SAVE_FAILED")
if census() != {"content": [], "maps": []}:
    stop("POST_SAVE_DIRTY|" + json.dumps(census()))
rec = {"run": RUN, "backup": backup, "strobe": LABEL, "ppv": PPV_LABEL, "location": [loc.x, loc.y, loc.z], "applied": applied}
with open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexConductor", "place_default_strobe_p04_record.json"), "w", encoding="utf-8") as h:
    json.dump(rec, h, indent=1)
unreal.log("STROBE_PLACED_OK|run=%s|loc=%.0f,%.0f,%.0f|applied=%s|backup=%s"
           % (RUN, loc.x, loc.y, loc.z, json.dumps(applied), backup))
