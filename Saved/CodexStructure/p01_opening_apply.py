"""Author the opening light and the P01 floats into the Show from the reviewed plan
(p01_opening_plan.json), materialize Passage 01, re-fit its structure so the new
lamps get housings, and save only the Show and the level.

RUN ONLY with Gary's yes in the Rig & atmosphere session, a conductor-granted
Show+level slot and a Backups/PreOpeningLight-* snapshot. Add-only: no existing
P01 light changes; every one is verified field-for-field before anything is
saved. p01_opening_revert.py removes exactly what this adds, by label.

GUIDs are read-only from Python, so, as for the P03 rig: append to a template
pair, replicate across the planned pairs (existing lights keep their GUIDs by
ordinal), restore each pair's own lights exactly, write its new lamps over the
new ordinals, and replicate back once to mint the template's.
"""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
PLAN = os.path.join(HERE, "p01_opening_plan.json")
RECORD = os.path.join(HERE, "p01_opening_revert_record.json")
NEW_SLOTS = ("Opening Light", "Float L", "Float R")
FINGERPRINT_FIELDS = ("type", "intensity_units", "intensity", "color", "use_temperature", "temperature_kelvin",
                      "attenuation_radius_cm", "inner_cone_angle_degrees", "outer_cone_angle_degrees",
                      "cast_shadows", "cast_volumetric_shadow", "volumetric_scattering_intensity",
                      "light_function_material")


def fail(message):
    raise RuntimeError(f"P01_OPENING_APPLY_FAILED|{message}")


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


def is_light(att):
    return att.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
content0, maps0 = dirty()
if content0 or maps0:
    fail(f"editor already dirty: {content0} {maps0}")

plan = json.load(open(PLAN, encoding="utf-8"))
rows_by_cue = {bay["cue"]: bay["lights"] for bay in plan["plan"] if bay["lights"]}
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
if not show:
    fail("Show did not load")


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


original = {}
for label in rows_by_cue:
    atts = lights_of(label)
    if any(not is_light(a) for a in atts):
        fail(f"{label} has non-light attachments; this script assumes lights only")
    if any(str(a.get_editor_property("label"))[len(label) + 1:] in NEW_SLOTS for a in atts):
        fail(f"{label} already carries opening/float lamps - run p01_opening_revert.py first")
    original[label] = atts
if len({len(v) for v in original.values()}) != 1:
    fail("planned pairs carry different light counts; ordinal GUID minting needs them equal")

# ---- Revert record: on disk, flushed and re-read before anything changes ----
record = {"written": datetime.datetime.now().isoformat(timespec="seconds"),
          "added_labels": [f"{label} {row['slot']}" for label, rows in rows_by_cue.items() for row in rows],
          "pairs": {label: [guid_str(a.get_editor_property("attachment_guid")) for a in atts]
                    for label, atts in original.items()}}
with open(RECORD, "w", encoding="utf-8") as fh:
    json.dump(record, fh, indent=1)
    fh.flush()
    os.fsync(fh.fileno())
reread = json.load(open(RECORD, encoding="utf-8"))
if len(reread["added_labels"]) != plan["lamps"] or sorted(reread["pairs"]) != sorted(rows_by_cue):
    fail("revert record did not read back complete")
unreal.log(f"P01_OPENING_REVERT_RECORD_OK|pairs={len(rows_by_cue)}|to_add={plan['lamps']}|path={RECORD}")


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


def rewrite_pair(label):
    lights = lights_of(label)
    base = original[label]
    rows = rows_by_cue[label]
    if len(lights) < len(base) + len(rows):
        fail(f"{label}: replicate produced {len(lights)} lights, need {len(base) + len(rows)}")
    out = list(base)
    for k, row in enumerate(rows):
        copy = lights[len(base) + k]
        minted = guid_str(copy.get_editor_property("attachment_guid"))
        fresh = make_lamp(label, row)
        for name in ("label", "kind", "anchor", "enabled", "relative_transform", "lighting"):
            copy.set_editor_property(name, fresh.get_editor_property(name))
        if guid_str(copy.get_editor_property("attachment_guid")) != minted:
            fail(f"{label}: minted GUID changed")
        out.append(copy)
    set_lights(label, out)


if globals().get("P01_DRY_RUN"):
    unreal.log(f"P01_OPENING_DRY_RUN_OK|pairs={len(rows_by_cue)}|to_add={plan['lamps']}|mutated=0")
    raise RuntimeError("P01_OPENING_DRY_RUN_COMPLETE")

# ---- Mutate -----------------------------------------------------------------
show.modify()
template = max(rows_by_cue, key=lambda label: len(rows_by_cue[label]))
max_new = len(rows_by_cue[template])
others = [label for label in rows_by_cue if label != template]
donor = next((label for label in others if len(rows_by_cue[label]) == max_new), None)
if donor is None:
    fail("no donor pair with a full set to mint the template's GUIDs")
set_lights(template, original[template] + [make_lamp(template, r) for r in rows_by_cue[template]])
show.replicate_light_attachments(
    fresh_cues()[index_of(template)].get_editor_property("cue_guid"),
    [fresh_cues()[index_of(label)].get_editor_property("cue_guid") for label in others])
for label in others:
    rewrite_pair(label)
show.replicate_light_attachments(
    fresh_cues()[index_of(donor)].get_editor_property("cue_guid"),
    [fresh_cues()[index_of(template)].get_editor_property("cue_guid")])
rewrite_pair(template)

# ---- Verify before any save ---------------------------------------------------
guids = set()
added = 0
for label in rows_by_cue:
    lights = lights_of(label)
    base = original[label]
    if [fingerprint(a) for a in lights[:len(base)]] != [fingerprint(a) for a in base]:
        fail(f"{label}: existing lights did not survive exactly")
    new = lights[len(base):]
    if [str(a.get_editor_property("label")) for a in new] != [f"{label} {r['slot']}" for r in rows_by_cue[label]]:
        fail(f"{label}: new lamps are not the planned ones")
    for att in lights:
        g = guid_str(att.get_editor_property("attachment_guid"))
        if set(g) <= {"0", "-"} or g in guids:
            fail(f"{label}: invalid or duplicate attachment GUID {g}")
        guids.add(g)
    added += len(new)
if added != plan["lamps"]:
    fail(f"added {added} lamps, plan has {plan['lamps']}")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
if not passage.materialize_passage():
    fail("Passage 01 did not materialize")
housings = 0
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        if not a.materialize_structure():
            fail("Structure 01 did not re-fit to the new lamps")
        housings = int(a.get_editor_property("fixture_body_count"))

content1, maps1 = dirty()
if set(content1) - {SHOW_PATH} or set(maps1) - {EXPECTED_WORLD}:
    fail(f"out-of-scope dirty before save: {content1} {maps1}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
unreal.log(f"P01_OPENING_APPLY_OK|added={added}|opening={plan['opening_cue']}|floats={plan['floats']}"
           f"|floats_dark={plan['floats_dark']}|housings={housings}|show_saved=1|level_saved=1"
           f"|dirty_after={len(content2)}+{len(maps2)}")
