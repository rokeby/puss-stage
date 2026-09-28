"""Author the curtain warmer from p01_warmer_plan.json: two crossing house spots
behind the stalls camera, and floats behind the curtain's new line (x 0), while
disabling the lone 4-degree Opening Light it replaces. Materialize P01, re-fit
its structure, save only the Show and the level. Gary approved the warmer write
(28 Sep, "Yes", Rig & atmosphere session); run inside the conductor's slot,
after a Backups/PreWarmer-* snapshot. p01_warmer_revert.py undoes it exactly.

GUIDs are read-only from Python and only ReplicateLightAttachments mints them,
fresh wherever a destination ordinal did not exist. The planned pairs no longer
carry equal light counts (Wing 001 holds the Opening Light), so instead of a
template pair this pads a SCRATCH source pair, one not in the plan, with blank
lamps, replicates it onto every planned pair, restores each pair's own lights
exactly with its new lamps written over the fresh ordinals beyond them, and
restores the scratch pair exactly. Every step is verified before any save.
"""
import datetime
import json
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
PLAN = os.path.join(HERE, "p01_warmer_plan.json")
RECORD = os.path.join(HERE, "p01_warmer_revert_record.json")
P01 = re.compile(r"^P01 Wing \d{3}$")
FINGERPRINT_FIELDS = ("type", "intensity_units", "intensity", "color", "use_temperature", "temperature_kelvin",
                      "attenuation_radius_cm", "inner_cone_angle_degrees", "outer_cone_angle_degrees",
                      "cast_shadows", "cast_volumetric_shadow", "volumetric_scattering_intensity",
                      "light_function_material")


def fail(message):
    raise RuntimeError(f"P01_WARMER_APPLY_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def guid_str(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def norm(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, unreal.Color):
        return [v.r, v.g, v.b, v.a]
    if isinstance(v, unreal.LinearColor):
        return [round(v.r, 4), round(v.g, 4), round(v.b, 4), round(v.a, 4)]
    if isinstance(v, unreal.Transform):
        r = v.rotation.rotator()
        return [round(c, 2) for c in (v.translation.x, v.translation.y, v.translation.z,
                                      r.roll, r.pitch, r.yaw, v.scale3d.x, v.scale3d.y, v.scale3d.z)]
    if isinstance(v, unreal.Object):
        return v.get_path_name()
    return str(v)


def fingerprint(att):
    L = att.get_editor_property("lighting")
    head = [guid_str(att.get_editor_property("attachment_guid")), str(att.get_editor_property("label")),
            str(att.get_editor_property("kind")), str(att.get_editor_property("anchor")),
            bool(att.get_editor_property("enabled")), norm(att.get_editor_property("relative_transform"))]
    return json.dumps(head + [norm(L.get_editor_property(n)) for n in FINGERPRINT_FIELDS])


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
content0, maps0 = dirty()
if content0 or maps0:
    fail(f"editor already dirty: {content0} {maps0}")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if any(a.get_actor_label().startswith("ZZ_") for a in sub.get_all_level_actors()):
    fail("stray ZZ_ actors in the level")

plan = json.load(open(PLAN, encoding="utf-8"))
rows_by_cue = {bay["cue"]: bay["lights"] for bay in plan["plan"] if bay["lights"]}
disable = set(plan.get("disable_labels", []))
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)


def fresh_cues():
    return list(show.get_editor_property("cues"))


def index_of(label):
    for i, c in enumerate(fresh_cues()):
        if str(c.get_editor_property("label")) == label:
            return i
    fail(f"{label} not in Show")


def lights_of(label):
    return list(fresh_cues()[index_of(label)].get_editor_property("wing_pair").get_editor_property("attachments"))


def set_lights(label, lights):
    cues = fresh_cues()
    i = index_of(label)
    cue = cues[i]
    pair = cue.get_editor_property("wing_pair")
    pair.set_editor_property("attachments", lights)
    cue.set_editor_property("wing_pair", pair)
    cues[i] = cue
    show.set_editor_property("cues", cues)


def make_lamp(label, row):
    att = unreal.InfinityCueAttachment()
    att.set_editor_property("label", unreal.Text(f"{label} {row['slot']}"))
    att.set_editor_property("kind", unreal.InfinityAttachmentKind.LIGHT)
    att.set_editor_property("anchor", unreal.InfinityAttachmentAnchor.STATION)
    att.set_editor_property("enabled", bool(row["enabled"]))
    o = row["offset"]
    att.set_editor_property("relative_transform", unreal.Transform(
        location=unreal.Vector(*o["loc"]), rotation=unreal.Rotator(roll=o["roll"], pitch=o["pitch"], yaw=o["yaw"])))
    L = unreal.InfinityStageLightSettings()
    L.set_editor_property("type", unreal.InfinityStageLightType.SPOT)
    L.set_editor_property("intensity_units", unreal.InfinityStageLightIntensityUnits.CANDELAS)
    L.set_editor_property("intensity", float(row["intensity_cd"]))
    L.set_editor_property("use_temperature", True)
    L.set_editor_property("temperature_kelvin", float(row["kelvin"]))
    L.set_editor_property("attenuation_radius_cm", float(row["radius_cm"]))
    L.set_editor_property("inner_cone_angle_degrees", float(row["inner"]))
    L.set_editor_property("outer_cone_angle_degrees", float(row["outer"]))
    L.set_editor_property("cast_shadows", bool(row["cast_shadows"]))
    L.set_editor_property("cast_volumetric_shadow", bool(row["cast_volumetric_shadow"]))
    L.set_editor_property("volumetric_scattering_intensity", float(row["volumetric_scattering"]))
    att.set_editor_property("lighting", L)   # no light function, no drama: steady by design
    return att


def is_light(att):
    return att.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT


# ---- Guards -------------------------------------------------------------------
original = {}
for label, rows in rows_by_cue.items():
    atts = lights_of(label)
    if any(not is_light(a) for a in atts):
        fail(f"{label} has non-light attachments")
    existing = {str(a.get_editor_property("label")) for a in atts}
    clash = [f"{label} {r['slot']}" for r in rows if f"{label} {r['slot']}" in existing]
    if clash:
        fail(f"already present, run p01_warmer_revert.py first: {clash}")
    original[label] = atts
found = {str(a.get_editor_property("label")) for atts in original.values() for a in atts} & disable
if found != disable:
    fail(f"lamps to disable not found in the planned pairs: {sorted(disable - found)}")
p01_labels = [str(c.get_editor_property("label")) for c in fresh_cues() if P01.match(str(c.get_editor_property("label")))]
scratch = next((label for label in reversed(p01_labels) if label not in rows_by_cue), None)
if scratch is None:
    fail("no P01 pair outside the plan to use as the scratch source")
scratch_original = lights_of(scratch)
if any(not is_light(a) for a in scratch_original):
    fail(f"scratch {scratch} has non-light attachments")
needed = max(len(original[label]) + len(rows) for label, rows in rows_by_cue.items())
padding = max(0, needed - len(scratch_original))

# ---- Revert record: on disk, flushed and re-read before anything changes ----
record = {"written": datetime.datetime.now().isoformat(timespec="seconds"),
          "added_labels": [f"{label} {r['slot']}" for label, rows in rows_by_cue.items() for r in rows],
          "disabled_labels": sorted(disable),
          "pairs": {label: [guid_str(a.get_editor_property("attachment_guid")) for a in atts]
                    for label, atts in original.items()},
          "scratch": scratch}
with open(RECORD, "w", encoding="utf-8") as fh:
    json.dump(record, fh, indent=1)
    fh.flush()
    os.fsync(fh.fileno())
reread = json.load(open(RECORD, encoding="utf-8"))
if len(reread["added_labels"]) != plan["lamps"] or reread["disabled_labels"] != sorted(disable):
    fail("revert record did not read back complete")
unreal.log(f"P01_WARMER_REVERT_RECORD_OK|pairs={len(rows_by_cue)}|to_add={plan['lamps']}|to_disable={len(disable)}"
           f"|scratch={scratch}|padding={padding}")

if globals().get("P01_WARMER_DRY_RUN"):
    unreal.log(f"P01_WARMER_DRY_RUN_OK|pairs={len(rows_by_cue)}|to_add={plan['lamps']}|mutated=0")
    raise RuntimeError("P01_WARMER_DRY_RUN_COMPLETE")

# ---- Mutate -----------------------------------------------------------------
show.modify()
blank = {"slot": "Scratch", "enabled": False, "offset": {"loc": [0, 0, 0], "pitch": 0, "yaw": 0, "roll": 0},
         "intensity_cd": 0.0, "kelvin": 2800, "radius_cm": 100.0, "inner": 1.0, "outer": 2.0,
         "cast_shadows": False, "cast_volumetric_shadow": False, "volumetric_scattering": 0.0}
set_lights(scratch, list(scratch_original) + [make_lamp(scratch, blank) for _ in range(padding)])
show.replicate_light_attachments(
    fresh_cues()[index_of(scratch)].get_editor_property("cue_guid"),
    [fresh_cues()[index_of(label)].get_editor_property("cue_guid") for label in rows_by_cue])
set_lights(scratch, scratch_original)
for label, rows in rows_by_cue.items():
    lights = lights_of(label)
    base = original[label]
    if len(lights) < len(base) + len(rows):
        fail(f"{label}: replicate produced {len(lights)} lights, need {len(base) + len(rows)}")
    out = []
    for att in base:
        if str(att.get_editor_property("label")) in disable:
            att.set_editor_property("enabled", False)
        out.append(att)
    for k, row in enumerate(rows):
        vessel = lights[len(base) + k]      # a fresh ordinal: replicate minted this GUID
        minted = guid_str(vessel.get_editor_property("attachment_guid"))
        fresh = make_lamp(label, row)
        for name in ("label", "kind", "anchor", "enabled", "relative_transform", "lighting"):
            vessel.set_editor_property(name, fresh.get_editor_property(name))
        if guid_str(vessel.get_editor_property("attachment_guid")) != minted:
            fail(f"{label}: minted GUID changed")
        out.append(vessel)
    set_lights(label, out)

# ---- Verify before any save ---------------------------------------------------
if [fingerprint(a) for a in lights_of(scratch)] != [fingerprint(a) for a in scratch_original]:
    fail(f"scratch {scratch} was not restored exactly")
guids = set()
added = 0
for label in p01_labels:
    for att in lights_of(label):
        g = guid_str(att.get_editor_property("attachment_guid"))
        if set(g) <= {"0", "-"} or g in guids:
            fail(f"{label}: invalid or duplicate attachment GUID {g}")
        guids.add(g)
for label, rows in rows_by_cue.items():
    lights = lights_of(label)
    base = original[label]
    if [fingerprint(a) for a in lights[:len(base)]] != [fingerprint(a) for a in base]:
        fail(f"{label}: existing lights did not survive exactly")
    if [str(a.get_editor_property("label")) for a in lights[len(base):]] != [f"{label} {r['slot']}" for r in rows]:
        fail(f"{label}: new lamps are not the planned ones")
    added += len(lights) - len(base)
if added != plan["lamps"]:
    fail(f"added {added} lamps, plan has {plan['lamps']}")
disabled_now = [str(a.get_editor_property("label")) for label in rows_by_cue for a in lights_of(label)
                if str(a.get_editor_property("label")) in disable and not a.get_editor_property("enabled")]
if sorted(disabled_now) != sorted(disable):
    fail(f"disable did not land: {disabled_now}")

passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
if not passage.materialize_passage():
    fail("Passage 01 did not materialize")
housings = 0
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        if not a.materialize_structure():
            fail("Structure 01 did not re-fit")
        housings = int(a.get_editor_property("fixture_body_count"))

content1, maps1 = dirty()
if set(content1) - {SHOW_PATH} or set(maps1) - {EXPECTED_WORLD}:
    fail(f"out-of-scope dirty before save: {content1} {maps1}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
unreal.log(f"P01_WARMER_APPLY_OK|added={added}|disabled={len(disabled_now)}|scratch={scratch}|housings={housings}"
           f"|show_saved=1|level_saved=1|dirty_after={len(content2)}+{len(maps2)}")
