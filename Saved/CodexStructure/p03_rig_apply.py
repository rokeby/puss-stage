"""Light Passage 03 from the upper rig. Approved by Gary on 26 Sep 2026: "2 feel
free to edit existing lights too". Run inside a conductor-granted Show+level
slot, after a Backups/PreP03Rig-* snapshot and a fresh run of
p03_rig_plan_readonly.py.

What changes, and why:
- ADD the planned rig (p03_rig_plan.json): forward pools onto the next pair's
  faces, grazing slashes, and back-lights thrown toward the approaching camera,
  the only direction forward-scattering haze shows a shaft in.
- REWORK every existing P03 light into quiet fill: one consistent level per
  slot (+-12%) instead of the 1-101 cd per-cue spread that read as patchy,
  shaped along the route by the plan's composed path envelope (35-100%, three
  irregular dark troughs) so the journey has arrivals, and shadows off, so the Passage net-reduces
  shadow casters against a VSM budget that already overflows. The rig carries
  the keys, the shadows and the parts of the wings.
- DRAMA (PIE and renders only; the editor always shows authored values):
  slashes and back-lights strike on approach, about a third of the pools
  slow-sweep.

Safety: the revert record is written, flushed, re-read and checked BEFORE the
first light is touched, and p03_rig_revert.py undoes this exactly. Everything is
verified before the Show and level are saved; nothing else is saved.

Why replicate: attachment GUIDs are read-only from Python and only the Show's
ReplicateLightAttachments mints them. The rig is appended to one template bay,
replicated across the rigged bays (existing lights keep their GUIDs by
ordinal), each bay's reworked lights are restored exactly and its own rig
written over the new ordinals, and a last replicate back mints the template's.
"""
import datetime
import json
import os
import random
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
PLAN = os.path.join(HERE, "p03_rig_plan.json")
RECORD = os.path.join(HERE, "p03_rig_revert_record.json")
LABEL = re.compile(r"^P03 Wing \d{3}$")
# Set True only when the conductor confirms a pre-existing map flag is its
# capture tool's spurious one; the level save below persists whatever it is.
ACCEPT_MAP_ALREADY_DIRTY = False

FILL_CD = {"Cross +Y": 8.0, "Cross -Y": 8.0, "Entry Fwd +Y": 6.0, "Entry Fwd -Y": 6.0,
           "Entry High +Y": 12.0, "Entry High -Y": 12.0, "Entry Top": 18.0, "Low +Y": 3.0, "Low -Y": 3.0}
FILL_JITTER = 0.12
FILL_SCATTER = 0.6
# Gary, 26 Sep: "attention to lighting path and wings". The fill is a floor under
# the composition, not a second key, and it breathes along the route: the plan's
# per-pair fill_envelope (35-100%, three composed dark troughs at irregular
# spacing, never repeating) sinks whole stretches toward dark so the next pool,
# or a crossing pair of back-light shafts, reads as an arrival.
RECORDED_FIELDS = ("intensity", "cast_shadows", "cast_volumetric_shadow", "volumetric_scattering_intensity")
FINGERPRINT_FIELDS = ("type", "intensity_units", "intensity", "color", "use_temperature", "temperature_kelvin",
                      "attenuation_radius_cm", "inner_cone_angle_degrees", "outer_cone_angle_degrees",
                      "cast_shadows", "cast_volumetric_shadow", "volumetric_scattering_intensity",
                      "light_function_material", "drama")


def fail(message):
    raise RuntimeError(f"P03_RIG_APPLY_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def guid_str(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def norm(v):
    """Comparable value: struct reprs carry memory addresses, so unpack them."""
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (unreal.Color,)):
        return [v.r, v.g, v.b, v.a]
    if isinstance(v, unreal.LinearColor):
        return [round(v.r, 4), round(v.g, 4), round(v.b, 4), round(v.a, 4)]
    if isinstance(v, unreal.Transform):
        r = v.rotation.rotator()
        return [round(c, 2) for c in (v.translation.x, v.translation.y, v.translation.z,
                                      r.roll, r.pitch, r.yaw, v.scale3d.x, v.scale3d.y, v.scale3d.z)]
    if isinstance(v, unreal.InfinityStageLightDrama):
        return [norm(v.get_editor_property(n)) for n in ("strike_on_approach", "strike_distance_cm",
                                                         "slow_move", "period_seconds")]
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


# ---- Preconditions ---------------------------------------------------------
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
content0, maps0 = dirty()
if content0:
    fail(f"content already dirty: {content0}")
if maps0 and not ACCEPT_MAP_ALREADY_DIRTY:
    fail(f"level already dirty: {maps0} - confirm the cause with the conductor first")

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


p03 = [str(c.get_editor_property("label")) for c in fresh_cues() if LABEL.match(str(c.get_editor_property("label")))]
if not p03:
    fail("no P03 cues")
missing = [label for label in rows_by_cue if label not in p03]
if missing:
    fail(f"plan cues missing from Show: {missing}")
original = {}
for label in p03:
    atts = lights_of(label)
    if any(not is_light(a) for a in atts):
        fail(f"{label} has non-light attachments; this script assumes lights only")
    if any(str(a.get_editor_property("label")).startswith(f"{label} Rig ") for a in atts):
        fail(f"{label} already carries rig lamps - run p03_rig_revert.py first")
    original[label] = atts
base_counts = {len(original[label]) for label in rows_by_cue}
if len(base_counts) != 1:
    fail(f"rigged bays carry different light counts {base_counts}; ordinal GUID minting needs them equal")
existing_lights = sum(len(v) for v in original.values())
casters_before = sum(1 for label in p03 for a in original[label]
                     if a.get_editor_property("enabled")
                     and a.get_editor_property("lighting").get_editor_property("cast_shadows"))

# ---- Revert record: on disk, flushed and re-read before anything changes ----
record = {
    "written": datetime.datetime.now().isoformat(timespec="seconds"),
    "existing_lights": existing_lights,
    "cues": [{"label": label, "lights": [
        {"guid": guid_str(a.get_editor_property("attachment_guid")), "label": str(a.get_editor_property("label")),
         "fields": {n: a.get_editor_property("lighting").get_editor_property(n) for n in RECORDED_FIELDS}}
        for a in original[label]]} for label in p03],
}
with open(RECORD, "w", encoding="utf-8") as fh:
    json.dump(record, fh, indent=1)
    fh.flush()
    os.fsync(fh.fileno())
reread = json.load(open(RECORD, encoding="utf-8"))
if reread["existing_lights"] != existing_lights or len(reread["cues"]) != len(p03) or \
        sum(len(c["lights"]) for c in reread["cues"]) != existing_lights:
    fail("revert record did not read back complete")
unreal.log(f"P03_RIG_REVERT_RECORD_OK|cues={len(p03)}|lights={existing_lights}|path={RECORD}")

# ---- Build the new light lists (still nothing written to the Show) ---------
# The path envelope comes from the plan, which owns it for every P03 pair.
route_order = [bay["cue"] for bay in sorted(plan["plan"], key=lambda b: b["route_x"])]
envelope = {bay["cue"]: float(bay["fill_envelope"]) for bay in plan["plan"]}
if sorted(envelope) != sorted(p03):
    fail(f"plan envelope covers {len(envelope)} pairs, the Show has {len(p03)} P03 pairs - re-run the plan")


def rework(label, att):
    slot = str(att.get_editor_property("label"))[len(label) + 1:]
    if slot not in FILL_CD:
        return att
    L = att.get_editor_property("lighting")
    # Fill levels are candelas; a light in other units keeps its brightness and
    # only loses its shadow.
    if L.get_editor_property("intensity_units") == unreal.InfinityStageLightIntensityUnits.CANDELAS:
        L.set_editor_property("intensity", FILL_CD[slot] * envelope[label] * random.Random(
            guid_str(att.get_editor_property("attachment_guid"))).uniform(1.0 - FILL_JITTER, 1.0 + FILL_JITTER))
    L.set_editor_property("cast_shadows", False)
    L.set_editor_property("cast_volumetric_shadow", False)
    L.set_editor_property("volumetric_scattering_intensity", FILL_SCATTER)
    att.set_editor_property("lighting", L)
    return att


# Fresh copies from the Show, so the snapshot in `original` is never mutated.
reworked = {label: [rework(label, a) for a in lights_of(label)] for label in p03}
fill_changed = sum(1 for label in p03 for a in original[label]
                   if str(a.get_editor_property("label"))[len(label) + 1:] in FILL_CD)


def make_rig_light(label, row):
    att = unreal.InfinityCueAttachment()
    att.set_editor_property("label", unreal.Text(f"{label} {row['slot']}"))
    att.set_editor_property("kind", unreal.InfinityAttachmentKind.LIGHT)
    att.set_editor_property("anchor", unreal.InfinityAttachmentAnchor.STATION)
    o = row["offset"]
    att.set_editor_property("relative_transform", unreal.Transform(
        location=unreal.Vector(*o["loc"]),
        rotation=unreal.Rotator(roll=o["roll"], pitch=o["pitch"], yaw=o["yaw"])))
    L = unreal.InfinityStageLightSettings()
    L.set_editor_property("type", unreal.InfinityStageLightType.SPOT)
    L.set_editor_property("intensity_units", unreal.InfinityStageLightIntensityUnits.CANDELAS)
    L.set_editor_property("intensity", float(row["intensity_cd"]))
    L.set_editor_property("use_temperature", True)
    L.set_editor_property("temperature_kelvin", float(row["kelvin"]))
    L.set_editor_property("attenuation_radius_cm", float(row["throw_cm"]) * 1.6)
    L.set_editor_property("inner_cone_angle_degrees", float(row["inner"]))
    L.set_editor_property("outer_cone_angle_degrees", float(row["outer"]))
    L.set_editor_property("cast_shadows", True)
    L.set_editor_property("cast_volumetric_shadow", bool(row["cast_volumetric_shadow"]))
    L.set_editor_property("volumetric_scattering_intensity", float(row["volumetric_scattering"]))
    drama = L.get_editor_property("drama")
    slot = row["slot"]
    if slot in ("Rig Slash", "Rig Back"):
        back = slot == "Rig Back"
        drama.set_editor_property("strike_on_approach", True)
        drama.set_editor_property("strike_distance_cm", 3500.0 if back else 2200.0)
        drama.set_editor_property("strike_ramp_cm", 300.0 if back else 200.0)
        drama.set_editor_property("ignition_stutter", 0.5 if back else 0.7)
        drama.set_editor_property("after_pass", unreal.InfinityLightAfterPass.HOLD)
    elif random.Random(f"{label}|{slot}|sweep").random() < 1.0 / 3.0:
        drama.set_editor_property("slow_move", True)
        drama.set_editor_property("pan_amplitude_degrees", 5.0)
        drama.set_editor_property("tilt_amplitude_degrees", 2.5)
        drama.set_editor_property("period_seconds", random.Random(f"{label}|{slot}|period").uniform(12.0, 22.0))
        drama.set_editor_property("phase_from_identity", True)
    L.set_editor_property("drama", drama)
    att.set_editor_property("lighting", L)
    return att


def rewrite_bay(label):
    """After a replicate: this bay's reworked lights back exactly, then its own
    rig over the new ordinals, keeping the GUIDs replicate minted there."""
    lights = lights_of(label)
    base = reworked[label]
    rows = rows_by_cue.get(label, [])
    if len(lights) < len(base) + len(rows):
        fail(f"{label}: replicate produced {len(lights)} lights, need {len(base) + len(rows)}")
    out = list(base)
    for k, row in enumerate(rows):
        copy = lights[len(base) + k]
        minted = guid_str(copy.get_editor_property("attachment_guid"))
        fresh = make_rig_light(label, row)
        for name in ("label", "kind", "anchor", "relative_transform", "lighting"):
            copy.set_editor_property(name, fresh.get_editor_property(name))
        copy.set_editor_property("enabled", True)
        if guid_str(copy.get_editor_property("attachment_guid")) != minted:
            fail(f"{label}: minted GUID changed")
        out.append(copy)
    set_lights(label, out)


# ---- Mutate -----------------------------------------------------------------
if globals().get("P03_DRY_RUN"):
    # Rehearsal (p03_rig_apply_dryrun.py): every guard passed, the new lists
    # were built and the revert record verified; stop before the first write.
    rig_rows = sum(len(r) for r in rows_by_cue.values())
    unreal.log(f"P03_RIG_DRY_RUN_OK|cues={len(p03)}|existing_lights={existing_lights}|fill_to_rework={fill_changed}"
               f"|rig_to_add={rig_rows}|p03_shadow_casters_now={casters_before}"
               f"|path_envelope={','.join(f'{envelope[l]:.2f}' for l in route_order)}|mutated=0")
    raise RuntimeError("P03_RIG_DRY_RUN_COMPLETE")
show.modify()
template = max(rows_by_cue, key=lambda label: len(rows_by_cue[label]))
max_rig = len(rows_by_cue[template])
others = [label for label in rows_by_cue if label != template]
donor = next((label for label in others if len(rows_by_cue[label]) == max_rig), None)
if donor is None:
    fail("no donor bay with a full rig to mint the template's GUIDs")
set_lights(template, reworked[template] + [make_rig_light(template, r) for r in rows_by_cue[template]])
show.replicate_light_attachments(
    fresh_cues()[index_of(template)].get_editor_property("cue_guid"),
    [fresh_cues()[index_of(label)].get_editor_property("cue_guid") for label in others])
for label in others:
    rewrite_bay(label)
show.replicate_light_attachments(
    fresh_cues()[index_of(donor)].get_editor_property("cue_guid"),
    [fresh_cues()[index_of(template)].get_editor_property("cue_guid")])
rewrite_bay(template)
for label in p03:
    if label not in rows_by_cue:
        set_lights(label, reworked[label])

# ---- Verify before any save ---------------------------------------------------
guids = set()
rig_added = strikes = sweeps = casters_after = 0
for label in p03:
    lights = lights_of(label)
    base = reworked[label]
    if [fingerprint(a) for a in lights[:len(base)]] != [fingerprint(a) for a in base]:
        fail(f"{label}: reworked lights did not land exactly")
    rig = lights[len(base):]
    if len(rig) != len(rows_by_cue.get(label, [])):
        fail(f"{label}: {len(rig)} rig lamps, plan has {len(rows_by_cue.get(label, []))}")
    for att in lights:
        g = att.get_editor_property("attachment_guid")
        if set(guid_str(g)) <= {"0", "-"} or guid_str(g) in guids:
            fail(f"{label}: invalid or duplicate attachment GUID {guid_str(g)}")
        guids.add(guid_str(g))
        L = att.get_editor_property("lighting")
        if att.get_editor_property("enabled") and L.get_editor_property("cast_shadows"):
            casters_after += 1
        d = L.get_editor_property("drama")
        strikes += int(bool(d.get_editor_property("strike_on_approach")))
        sweeps += int(bool(d.get_editor_property("slow_move")))
    rig_added += len(rig)
if rig_added != plan["lamps"]:
    fail(f"added {rig_added} rig lamps, plan has {plan['lamps']}")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 03"))
if not passage.materialize_passage():
    fail("Passage 03 did not materialize")
housings = 0
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        if not a.materialize_structure():
            fail("Structure 03 did not re-fit to the new rig")
        housings = int(a.get_editor_property("fixture_body_count"))

content1, maps1 = dirty()
if set(content1) - {SHOW_PATH} or set(maps1) - {EXPECTED_WORLD}:
    fail(f"out-of-scope dirty before save: {content1} {maps1}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
unreal.log(f"P03_RIG_APPLY_OK|fill_reworked={fill_changed}|rig_added={rig_added}|strike={strikes}|sweep={sweeps}"
           f"|p03_shadow_casters={casters_before}->{casters_after}|housings={housings}|template={template}|donor={donor}"
           f"|show_saved=1|level_saved=1|dirty_after={len(content2)}+{len(maps2)}")
