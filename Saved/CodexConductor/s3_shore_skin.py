"""S3 shore figures: pale / white / sallow / aged skin by CREATE-ONLY child material instances (Gary 6 Oct:
"In these metahumans, can we implement detailed skin - pale, white, sallow and aged").

Set-up (binary-proven from the .uasset name tables / tags, 6 Oct; .uasset files carry no line numbers):
  * Every figure is an Optimized/Medium assembly. Skin materials come from the MESH slot defaults, not from the
    Blueprint or the level (no MI_Body_Baked_VT / MI_Face_Skin reference in BP_Shore0N_*_Draped or in the umap):
      body  SKM_MHC_<id>_BodyMesh slot body_shader_shader -> <id>/Body/Materials/MI_Body_Baked_VT
            -> Common/Lookdev_UHM/Skin/Materials/Baked/MI_Head_Baked_LOD0_VT -> M_skin_unified_baked
      face  SKM_MHC_<id>_FaceMesh slot head_LOD3_shader_shader -> <id>/Face/Materials/MI_Face_Skin_Baked_LOD3_VT
            -> MI_Head_Baked_LOD2_VT -> LOD1_VT -> LOD0_VT -> M_skin_unified_baked
            slot head_LOD57_shader_shader -> MI_Face_Skin_Baked_LOD5to7_VT (parent: that figure's LOD3 MI)
  * The baked master exposes only GLOBAL post-bake adjustments (hue / saturation / value / multiply on base colour,
    roughness, specular, scatter distance, normal strength), the tiling micro-skin detail and fake SSS. There is NO
    melanin, redness, freckle, vein or age-spot parameter: those are baked into the albedo by MetaHuman texture
    synthesis (MetaHumanCharacterSkin.h accents/freckles) and can only change through the MHC asset + re-assembly.

What this tool does: per figure, a create-only child of each skin MI (body, face LOD3, face LOD5to7), parented to the
figure's CURRENT MI, with values computed RELATIVE to the parent's live values from three look knobs
(pallor P, sallow S, age A; table FIGURES). The children are assigned as OverrideMaterials on the Body / Face
component TEMPLATES of BP_Shore0N_*_Draped (target "bp", default) or on the placed level actors (target "level").
Existing assets are never edited; nothing is ever deleted (memory ue58-python-material-authoring).

Args s3_shore_skin_args.json:
  {"mode": "DRY"|"APPLY"|"REVERT"|"VERIFY", "confirm": "<MODE> S3SKIN",
   "target": "bp"|"level",                 # bp (default): 6 BP packages; level: the production umap only
   "figures": ["Shore01_M56", ...],        # default all six
   "look_version": "v1",                   # suffix of the child MI names; a re-tune = REVERT, then APPLY v2
   "strength": 1.0,                        # scales P, S, A together (0.25..1.5)
   "enable_post_bake_switch": true,        # set "Use Global Adjustments Post-Bake" on the child if a parent has it off
   "hue_shift_turns": null,                # OFF by default: the hue parameter's units are UNVERIFIED
   "save_map_if_reinstanced": false}       # bp target only: if BP compile dirties the map, also save it (backed up)
Modes:
  DRY     read-only: targets, slots, live parent values, the computed child values, gates, switch state, API
          availability, level instances, and EXACTLY which packages APPLY would save. Writes s3_shore_skin_dry.json.
  APPLY   guards (world, no PIE, clean census, record absent, no temp actors, no pre-existing overrides on the
          planned slots) -> exclusive record (fsync) -> Backups/PreS3ShoreSkin-<run>/ (the BP uassets + the umap)
          -> create children (or CHECK existing ones; a mismatch refuses) -> assign -> compile -> read back the
          template AND the placed instances -> census == planned packages -> save exactly those -> read back again.
  REVERT  restores the recorded override arrays, read back, census, save. Child MIs stay (create-only).
  VERIFY  read-only: assignments on templates + instances, child values against the record.
Markers: S3SKIN_START / S3SKIN_PLAN / S3SKIN_<MODE>_OK|run=.. / S3SKIN_FAILED|run=..
Importing without Unreal (offline harness test_s3_shore_skin_offline.py) runs nothing.
"""
import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None

HERE = "E:/PussStage/Saved/CodexConductor/"
ARGS = HERE + "s3_shore_skin_args.json"
REC = HERE + "s3_shore_skin_record.json"
DRY_OUT = HERE + "s3_shore_skin_dry.json"
VERIFY_OUT = HERE + "s3_shore_skin_verify.json"
BACKUP_ROOT = "E:/PussStage/Backups/PreS3ShoreSkin-"
CONTENT = "E:/PussStage/Content/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = CONTENT + "InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
ROOT = "/Game/Metahuman/ShoreCast_20260910"
SKIN_DIR = ROOT + "/Skin"
CONFIRM_WORD = "S3SKIN"
WRITE_MODES = ("APPLY", "REVERT")
TOL = 1e-3
POST_BAKE_SWITCH = "Use Global Adjustments Post-Bake"
MICRO_SWITCH = "Use Micro Skin Details"

# -------------------------------------------------------------------------------------------------- the look
# P pallor (lighter, whiter), S sallow (yellow-grey, less red, less saturated), A age (dry, creased, crepey,
# less translucent). Brief (Docs/ShoreCast-20260910.md): five in their 50s, one woman ~25; all pale and gaunt.
# Variation is deliberate: 03 oldest + greyest, 05 most jaundiced, 04 whitest, 06 young (pale + sallow, little age).
FIGURES = {
    "Shore01_M56": {"P": 0.55, "S": 0.70, "A": 0.85},
    "Shore02_F52": {"P": 0.75, "S": 0.55, "A": 0.70},
    "Shore03_M59": {"P": 0.45, "S": 0.85, "A": 1.00},
    "Shore04_F55": {"P": 0.85, "S": 0.45, "A": 0.80},
    "Shore05_M53": {"P": 0.50, "S": 0.90, "A": 0.65},
    "Shore06_F25": {"P": 0.80, "S": 0.50, "A": 0.25},
}
# Parameter rules: name -> (kind, function of the knobs). "mul": child = parent * f; "add": child = parent + d;
# "tint": vector, child.rgb = parent.rgb * tint. Names are the master's own (binary-proven from
# M_skin_unified_baked.uasset / MF_skin_globalAdjustmentsPostBake.uasset; "Micro Skin Roughess" is spelled so).
RULES = {
    "Basecolor Global Value Post-Bake":          ("mul", lambda k: 1.0 + 0.08 * k["P"] - 0.03 * k["S"]),
    "Basecolor Global Saturation Post-Bake":     ("mul", lambda k: 1.0 - 0.30 * k["S"] - 0.10 * k["P"]),
    "Basecolor Global Multiply Post-Bake":       ("tint", lambda k: sallow_tint(k["S"])),
    "Roughness Global Multiply Post-Bake":       ("mul", lambda k: 1.0 + 0.10 * k["A"]),
    "Specular Global Multiply Post-Bake":        ("mul", lambda k: 1.0 - 0.15 * k["A"]),
    "Scatter Distance Global Multiply Post-Bake": ("mul", lambda k: 1.0 - 0.125 * (k["S"] + k["A"])),
    "Normal Global Strength Post-Bake":          ("mul", lambda k: 1.0 + 0.30 * k["A"]),
    "Micro Skin Normal Strength":                ("mul", lambda k: 1.0 + 0.75 * k["A"]),
    "Micro Skin Tiling":                         ("mul", lambda k: 1.0 + 0.20 * k["A"]),
    "Micro Skin Roughess":                       ("mul", lambda k: 1.0 + 0.10 * k["A"]),
    "Micro Skin Cavity Specular Multiply":       ("mul", lambda k: 1.0 - 0.20 * k["A"]),
    "Fake SSS Strength":                         ("mul", lambda k: 1.0 - 0.30 * k["S"]),
    "Material AO Power":                         ("mul", lambda k: 1.0 + 0.25 * k["A"]),
}
HUE_PARAM = "Basecolor Global Hue Post-Bake"   # only with args hue_shift_turns (units UNVERIFIED)
POST_BAKE_PARAMS = tuple(n for n in RULES if n.endswith("Post-Bake")) + (HUE_PARAM,)
CORE_PARAMS = ("Basecolor Global Saturation Post-Bake", "Basecolor Global Value Post-Bake",
               "Roughness Global Multiply Post-Bake")   # without these the tool does nothing useful: refuse
MUL_RANGE = (0.5, 2.0)
ADD_LIMIT = 0.1
TINT_RANGE = (0.75, 1.0)


class SkinError(ValueError):
    pass


# --------------------------------------------------------------------------------------------- pure helpers
def sallow_tint(s):
    """Yellow-grey multiply: blue cut most, green a little, all channels dimmed slightly (grey)."""
    g = 1.0 - 0.02 * s
    return [round(1.0 * g, 4), round((1.0 - 0.035 * s) * g, 4), round((1.0 - 0.13 * s) * g, 4)]


def knobs_for(fig, strength=1.0):
    if fig not in FIGURES:
        raise SkinError("FIGURE|" + fig)
    if not 0.25 <= float(strength) <= 1.5:
        raise SkinError("STRENGTH|%s" % strength)
    return {k: min(1.0, float(v) * float(strength)) for k, v in FIGURES[fig].items()}


def bp_path(fig):
    return "%s/SceneCharacters/BP_%s_Draped" % (ROOT, fig)


def bp_file(fig):
    return CONTENT + bp_path(fig)[len("/Game/"):] + ".uasset"


def parent_paths(fig):
    """The figure's current skin MIs (binary-proven names, identical structure for all six)."""
    base = "%s/Assembled/%s/MHC_%s" % (ROOT, fig, fig)
    return {"body": [base + "/Body/Materials/MI_Body_Baked_VT"],
            "face": [base + "/Face/Materials/MI_Face_Skin_Baked_LOD3_VT",
                     base + "/Face/Materials/MI_Face_Skin_Baked_LOD5to7_VT"]}


def child_path(fig, parent, version):
    leaf = parent.rsplit("/", 1)[-1]
    leaf = leaf[3:] if leaf.startswith("MI_") else leaf
    if not version or not str(version).replace("_", "").isalnum():
        raise SkinError("LOOK_VERSION|%s" % version)
    return "%s/MI_S3Skin_%s_%s_%s" % (SKIN_DIR, fig, leaf, version)


def plan_values(knobs, scalars, vectors, hue_turns=None):
    """scalars {name: parent value}, vectors {name: [r,g,b,a]} = the parent's EFFECTIVE values (live read).
    Returns {"scalars", "vectors", "skipped", "problems"}; problems are gate failures (refuse)."""
    out = {"scalars": {}, "vectors": {}, "skipped": [], "problems": []}
    for name, (kind, fn) in RULES.items():
        if kind == "tint":
            if name in vectors:
                t = fn(knobs)
                p = [float(x) for x in vectors[name]]
                out["vectors"][name] = [round(p[0] * t[0], 5), round(p[1] * t[1], 5), round(p[2] * t[2], 5),
                                        p[3] if len(p) > 3 else 1.0]
                out["problems"] += tint_problems(name, t)
            elif name in scalars:
                out["skipped"].append("%s|IS_SCALAR: sallow tint unavailable, saturation/value only" % name)
            else:
                out["skipped"].append("%s|ABSENT" % name)
            continue
        if name not in scalars:
            out["skipped"].append("%s|ABSENT" % name)
            continue
        p = float(scalars[name])
        f = float(fn(knobs))
        if kind == "mul":
            if abs(p) < 1e-6:
                out["skipped"].append("%s|PARENT_ZERO: multiply semantics unclear" % name)
                continue
            if not (MUL_RANGE[0] <= f <= MUL_RANGE[1]) or not math.isfinite(f):
                out["problems"].append("FACTOR_RANGE|%s|%.4f" % (name, f))
                continue
            out["scalars"][name] = round(p * f, 5)
        else:
            if abs(f) > ADD_LIMIT or not math.isfinite(f):
                out["problems"].append("DELTA_RANGE|%s|%.4f" % (name, f))
                continue
            out["scalars"][name] = round(p + f, 5)
    if hue_turns is not None:
        if HUE_PARAM not in scalars:
            out["skipped"].append("%s|ABSENT" % HUE_PARAM)
        elif abs(float(hue_turns)) > 0.05:
            out["problems"].append("HUE_RANGE|%s" % hue_turns)
        else:
            out["scalars"][HUE_PARAM] = round(float(scalars[HUE_PARAM]) + float(hue_turns) * knobs["S"], 5)
    present = set(scalars) | set(vectors)
    missing_core = [n for n in CORE_PARAMS if n not in present]
    if missing_core:
        out["problems"].append("CORE_PARAMS_MISSING|%s" % missing_core)
    return out


def tint_problems(name, t):
    probs = []
    if any(not (TINT_RANGE[0] <= c <= TINT_RANGE[1]) for c in t):
        probs.append("TINT_RANGE|%s|%s" % (name, t))
    if not (t[0] >= t[1] >= t[2]):
        probs.append("TINT_NOT_SALLOW|%s|%s" % (name, t))   # sallow = R >= G >= B (yellow), never pink/blue
    return probs


def switch_plan(switch_values, enable):
    """switch_values: {switch name: effective bool on the parent, or None if unreadable}.
    Returns (child switch overrides, problems)."""
    sets, probs = {}, []
    v = switch_values.get(POST_BAKE_SWITCH)
    if v is None:
        probs.append("POST_BAKE_SWITCH_UNREADABLE")
    elif not v:
        if enable:
            sets[POST_BAKE_SWITCH] = True
        else:
            probs.append("POST_BAKE_INERT|parent has %s off and enable_post_bake_switch is false" % POST_BAKE_SWITCH)
    return sets, probs


def plan_slots(slots, overrides, parent_to_child):
    """slots: [{index, name, material}] = the mesh's slot defaults; overrides: the component's current
    OverrideMaterials (paths or None). Override a slot iff its default is one of this figure's skin MIs.
    Returns (rows, new_override_array, problems)."""
    rows, probs = [], []
    arr = list(overrides)
    for s in slots:
        to = parent_to_child.get(s["material"])
        if to is None:
            continue
        cur = arr[s["index"]] if s["index"] < len(arr) else None
        if cur not in (None, to):
            probs.append("FOREIGN_OVERRIDE|slot %d %s|%s" % (s["index"], s["name"], cur))
            continue
        while len(arr) <= s["index"]:
            arr.append(None)
        arr[s["index"]] = to
        rows.append({"index": s["index"], "slot": s["name"], "from": s["material"], "to": to, "override_before": cur})
    if not rows:
        probs.append("NO_SKIN_SLOT")
    return rows, arr, probs


def planned_packages(target, figures, created):
    """Exactly what an APPLY may save: the created children + (bp) the BPs or (level) the map."""
    content = sorted(set(created) | ({bp_path(f) for f in figures} if target == "bp" else set()))
    maps = [WORLD] if target == "level" else []
    return {"content": content, "maps": maps}


def census_ok(dirty, planned, allow_map=False):
    maps = sorted(dirty["maps"])
    want_maps = sorted(planned["maps"])
    if allow_map and maps == [WORLD] and not want_maps:
        want_maps = [WORLD]
    return maps == want_maps and sorted(dirty["content"]) == sorted(planned["content"])


def check_mode(args, record_exists):
    mode = str(args.get("mode", "DRY")).upper()
    if mode not in ("DRY", "VERIFY") + WRITE_MODES:
        raise SkinError("MODE|" + mode)
    if mode in WRITE_MODES and args.get("confirm") != "%s %s" % (mode, CONFIRM_WORD):
        raise SkinError("CONFIRM_MISSING|want '%s %s'" % (mode, CONFIRM_WORD))
    if mode == "APPLY" and record_exists:
        raise SkinError("ALREADY_APPLIED|record exists")
    if mode == "REVERT" and not record_exists:
        raise SkinError("NO_RECORD")
    target = str(args.get("target", "bp")).lower()
    if target not in ("bp", "level"):
        raise SkinError("TARGET|" + target)
    figs = list(args.get("figures") or sorted(FIGURES))
    bad = [f for f in figs if f not in FIGURES]
    if bad or len(set(figs)) != len(figs):
        raise SkinError("FIGURES|%s" % figs)
    knobs_for(figs[0], args.get("strength", 1.0))  # validates strength
    child_path(figs[0], parent_paths(figs[0])["body"][0], args.get("look_version", "v1"))
    return mode, target, figs


# ------------------------------------------------------------------------------------------------- unreal glue
def _path(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def _require(cond, msg):
    if not cond:
        raise SkinError(msg)


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _mesh_of(comp):
    for getter in ("get_skeletal_mesh_asset",):
        if hasattr(comp, getter):
            m = getattr(comp, getter)()
            if m is not None:
                return m
    for prop in ("skeletal_mesh_asset", "skeletal_mesh"):
        try:
            m = comp.get_editor_property(prop)
            if m is not None:
                return m
        except Exception:  # noqa: BLE001 - property name differs by version
            pass
    return None


def _slots(mesh):
    out = []
    for i, sm in enumerate(mesh.get_editor_property("materials") or []):
        out.append({"index": i, "name": str(sm.get_editor_property("material_slot_name")),
                    "material": _path(sm.get_editor_property("material_interface"))})
    return out


def _overrides(comp):
    return [_path(m) for m in (comp.get_editor_property("override_materials") or [])]


def _bp_templates(fig):
    """{"Body": template, "Face": template} on the BP's SCS (pattern: create_shore_draped_cast_components.py)."""
    bp = unreal.load_asset(bp_path(fig))
    _require(bp is not None, "BP_MISSING|" + bp_path(fig))
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    out = {}
    for h in sub.k2_gather_subobject_data_for_blueprint(bp):
        d = lib.get_data(h)
        name = str(lib.get_variable_name(d))
        if name in ("Body", "Face"):
            out[name] = lib.get_object_for_blueprint(d, bp)
    _require(set(out) == {"Body", "Face"}, "BP_COMPONENTS|%s|%s" % (fig, sorted(out)))
    return bp, out


def _level_actors(figs):
    """{fig: actor} for the placed BP instances in the open world; exactly one each."""
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    out, fails = {}, []
    for f in figs:
        cls = "BP_%s_Draped_C" % f
        hits = [a for a in actors if a.get_class().get_name() == cls]
        if len(hits) != 1:
            fails.append("INSTANCE_COUNT|%s|%d" % (f, len(hits)))
        else:
            out[f] = hits[0]
    _require(not fails, ";".join(fails))
    return out


def _actor_comp(actor, name):
    hits = [c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == name]
    _require(len(hits) == 1, "INSTANCE_COMPONENT|%s|%s|%d" % (actor.get_actor_label(), name, len(hits)))
    return hits[0]


def _mi_values(mi):
    mel = unreal.MaterialEditingLibrary
    sn = [str(n) for n in mel.get_scalar_parameter_names(mi)]
    vn = [str(n) for n in mel.get_vector_parameter_names(mi)]
    scal = {n: float(mel.get_material_instance_scalar_parameter_value(mi, n)) for n in sn}
    vec = {}
    for n in vn:
        c = mel.get_material_instance_vector_parameter_value(mi, n)
        vec[n] = [float(c.r), float(c.g), float(c.b), float(c.a)]
    sw = {}
    for n in (POST_BAKE_SWITCH, MICRO_SWITCH):
        try:
            sw[n] = bool(mel.get_material_instance_static_switch_parameter_value(mi, n))
        except Exception:  # noqa: BLE001 - API absent or not a switch: report as unreadable
            sw[n] = None
    return scal, vec, sw


def _set_switch(mi, name, value):
    mel = unreal.MaterialEditingLibrary
    _require(hasattr(mel, "set_material_instance_static_switch_parameter_value"), "SWITCH_SETTER_ABSENT")
    try:
        mel.set_material_instance_static_switch_parameter_value(mi, name, bool(value))
    except TypeError:
        mel.set_material_instance_static_switch_parameter_value(
            mi, name, bool(value), unreal.MaterialParameterAssociation.GLOBAL_PARAMETER)


def _check_child(mi, parent_path, want):
    _require(_path(mi.get_editor_property("parent")) == parent_path, "CHILD_PARENT|%s" % _path(mi))
    scal, vec, sw = _mi_values(mi)
    bad = {}
    for k, v in want["scalars"].items():
        if abs(scal.get(k, 1e30) - float(v)) > TOL:
            bad[k] = (scal.get(k), v)
    for k, v in want["vectors"].items():
        g = vec.get(k)
        if g is None or any(abs(g[i] - float(v[i])) > TOL for i in range(3)):
            bad[k] = (g, v)
    for k, v in want["switches"].items():
        if sw.get(k) is not bool(v):
            bad[k] = (sw.get(k), v)
    _require(not bad, "CHILD_READBACK|%s|%s" % (_path(mi), json.dumps(bad, default=str)))
    return True


def _make_child(path, parent, want):
    """CREATE-ONLY. An existing child is CHECKED (never edited); a mismatch refuses."""
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    parent_path = _path(parent)
    if eal.does_asset_exist(path):
        _check_child(unreal.load_asset(path), parent_path, want)
        return unreal.load_asset(path), False
    mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        path.rsplit("/", 1)[-1], SKIN_DIR, unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew())
    _require(mi is not None, "CHILD_CREATE_FAILED|" + path)
    mel.set_material_instance_parent(mi, parent)
    for k, v in want["switches"].items():
        _set_switch(mi, k, v)
    for k, v in want["scalars"].items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in want["vectors"].items():
        mel.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*[float(x) for x in v[:4]]))
    mel.update_material_instance(mi)
    _check_child(mi, parent_path, want)          # setter return values lie: judge by read-back only
    return mi, True


def gather(figs, args):
    """Live plan for every figure: slots, parents, children values, switches, templates, instances."""
    strength = float(args.get("strength", 1.0))
    version = args.get("look_version", "v1")
    hue = args.get("hue_shift_turns")
    enable = bool(args.get("enable_post_bake_switch", True))
    plan, problems = {}, []
    for f in figs:
        k = knobs_for(f, strength)
        bp, tmpl = _bp_templates(f)
        fp = {"knobs": k, "bp": bp_path(f), "children": {}, "components": {}}
        p2c = {}
        for part, parents in parent_paths(f).items():
            for pp in parents:
                parent = unreal.load_asset(pp)
                if parent is None:
                    problems.append("PARENT_MISSING|" + pp)
                    continue
                scal, vec, sw = _mi_values(parent)
                vals = plan_values(k, scal, vec, hue)
                sets, sprob = switch_plan(sw, enable)
                touched = [n for n in list(vals["scalars"]) + list(vals["vectors"]) if n in POST_BAKE_PARAMS]
                if not touched:
                    sets, sprob = {}, []
                cp = child_path(f, pp, version)
                fp["children"][cp] = {"part": part, "parent": pp, "scalars": vals["scalars"],
                                      "vectors": vals["vectors"], "switches": sets, "skipped": vals["skipped"],
                                      "parent_scalars": {n: scal[n] for n in vals["scalars"] if n in scal},
                                      "parent_vectors": {n: vec[n] for n in vals["vectors"] if n in vec},
                                      "parent_switches": sw}
                problems += ["%s|%s" % (cp, p) for p in vals["problems"] + sprob]
                p2c[pp] = cp
        for name, comp in tmpl.items():
            mesh = _mesh_of(comp)
            if mesh is None:
                problems.append("TEMPLATE_MESH|%s|%s" % (f, name))
                continue
            rows, arr, sprob = plan_slots(_slots(mesh), _overrides(comp), p2c)
            fp["components"][name] = {"mesh": _path(mesh), "rows": rows, "override_before": _overrides(comp),
                                      "override_after": arr}
            problems += ["%s|%s|%s" % (f, name, p) for p in sprob]
        plan[f] = fp
    return plan, problems


def _instances_report(figs, plan):
    """Placed actors: their Body/Face instance overrides must be empty (an instance delta would mask the BP)."""
    out, probs = {}, []
    for f, a in _level_actors(figs).items():
        row = {"label": str(a.get_actor_label()), "object_path": a.get_path_name(), "components": {}}
        for name in ("Body", "Face"):
            c = _actor_comp(a, name)
            n = int(c.get_num_materials())
            row["components"][name] = {"overrides": _overrides(c),
                                       "materials": [_path(c.get_material(i)) for i in range(n)]}
            tmpl_before = plan[f]["components"].get(name, {}).get("override_before", [])
            if [x for x in _overrides(c) if x] and _overrides(c) != tmpl_before:
                probs.append("INSTANCE_OVERRIDE|%s|%s|%s" % (f, name, _overrides(c)))
        out[f] = row
    return out, probs


def _assign(target, f, plan_f, key, actor=None):
    """key 'override_after' (APPLY) or 'override_before' (REVERT)."""
    if target == "bp":
        bp, tmpl = _bp_templates(f)
        bp.modify()
        for name, comp_plan in plan_f["components"].items():
            comp = tmpl[name]
            comp.modify()
            mats = [unreal.load_asset(p) if p else None for p in comp_plan[key]]
            comp.set_editor_property("override_materials", mats)
        _require(unreal.BlueprintEditorLibrary.compile_blueprint(bp) is not False, "COMPILE|" + f)
    else:
        for name, comp_plan in plan_f["components"].items():
            comp = _actor_comp(actor, name)
            comp.modify()
            mats = [unreal.load_asset(p) if p else None for p in comp_plan[key]]
            comp.set_editor_property("override_materials", mats)


def _readback(target, figs, plan, key):
    """Template (bp) override arrays, and on the PLACED instances the material each skin slot resolves to."""
    bad = []
    for f in figs:
        if target == "bp":
            _, tmpl = _bp_templates(f)
            for name, cp in plan[f]["components"].items():
                if _overrides(tmpl[name]) != cp[key]:
                    bad.append("TEMPLATE|%s|%s|%s" % (f, name, _overrides(tmpl[name])))
    for f, a in _level_actors(figs).items():
        for name, cp in plan[f]["components"].items():
            c = _actor_comp(a, name)
            for r in cp["rows"]:
                want = r["to"] if key == "override_after" else (r["override_before"] or r["from"])
                got = _path(c.get_material(r["index"]))
                if got != want:
                    bad.append("INSTANCE|%s|%s|slot %d|%s!=%s" % (f, name, r["index"], got, want))
    _require(not bad, "READBACK|%s" % bad[:8])


def _temp_actor_guard():
    acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    bad = [str(a.get_actor_label()) for a in acts
           if str(a.get_actor_label()).startswith("ZZ_") or "TEMP" in str(a.get_actor_label()).upper()]
    _require(not bad, "TEMP_ACTORS_PRESENT|%s" % bad[:5])


def _save(ed, planned, allow_map):
    _temp_actor_guard()
    dirty = _census()
    if not census_ok(dirty, planned, allow_map):
        raise SkinError("DIRTY_SCOPE|%s|planned=%s" % (json.dumps(dirty), json.dumps(planned)))
    for p in planned["content"]:
        _require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), "SAVE_ASSET_FAILED|" + p)
    if dirty["maps"]:
        _require(unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD), "SAVE_MAP_FAILED")
    _require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|" + json.dumps(_census()))
    return dirty


def _backup(run, figs):
    d = BACKUP_ROOT + run
    os.makedirs(d)
    rows = []
    for src in [bp_file(f) for f in figs] + [UMAP]:
        dst = os.path.join(d, os.path.basename(src))
        shutil.copy2(src, dst)
        _require(_sha256(src) == _sha256(dst), "BACKUP_HASH|" + src)
        rows.append({"src": src, "dst": dst, "bytes": os.path.getsize(dst)})
    return d, rows


def run_dry(run, args, target, figs):
    plan, problems = gather(figs, args)
    inst, iprob = _instances_report(figs, plan)
    created = [cp for f in figs for cp in plan[f]["children"]]
    eal = unreal.EditorAssetLibrary
    exists = {cp: eal.does_asset_exist(cp) for cp in created}
    mel = unreal.MaterialEditingLibrary
    api = {n: hasattr(mel, n) for n in ("get_material_instance_static_switch_parameter_value",
                                        "set_material_instance_static_switch_parameter_value",
                                        "get_vector_parameter_names", "set_material_instance_vector_parameter_value")}
    census = _census()
    out = {"run": run, "target": target, "figures": figs, "plan": plan, "problems": problems + iprob,
           "instances": inst, "children_exist": exists, "api": api, "census": census,
           "apply_would_refuse_dirty": census != {"content": [], "maps": []},
           "apply_would_save": planned_packages(target, figs, [c for c in created if not exists[c]]),
           "apply_backs_up": [bp_file(f) for f in figs] + [UMAP]}
    _write(DRY_OUT, out)
    table = {f: {"knobs": plan[f]["knobs"],
                 "body": next((c["scalars"], c["vectors"], c["switches"]) for c in plan[f]["children"].values()
                              if c["part"] == "body")} for f in figs}
    unreal.log("S3SKIN_PLAN|run=%s|%s" % (run, json.dumps({"problems": out["problems"], "api": api,
                                                            "would_save": out["apply_would_save"],
                                                            "table": table}, default=str)))
    if out["problems"]:
        unreal.log_warning("S3SKIN_DRY_PROBLEMS|run=%s|%d (APPLY would refuse)|%s" % (
            run, len(out["problems"]), out["problems"][:6]))
    return {"figures": len(figs), "children": len(created), "problems": len(out["problems"]), "out": DRY_OUT}


def run_apply(run, args, target, figs, ed):
    _temp_actor_guard()
    plan, problems = gather(figs, args)
    _, iprob = _instances_report(figs, plan)
    _require(not (problems + iprob), "PLAN_PROBLEMS|%s" % (problems + iprob)[:8])
    record = {"run": run, "world": WORLD, "target": target, "figures": figs, "args": args, "plan": plan,
              "saved": False, "created": []}
    _write(REC, record, exclusive=True)
    record["backup"], record["backup_files"] = _backup(run, figs)
    _write(REC, record)
    for f in figs:
        for cp, c in plan[f]["children"].items():
            _, made = _make_child(cp, unreal.load_asset(c["parent"]), c)
            if made:
                record["created"].append(cp)
    _write(REC, record)
    actors = _level_actors(figs) if target == "level" else {}
    for f in figs:
        _assign(target, f, plan[f], "override_after", actors.get(f))
    _readback(target, figs, plan, "override_after")
    planned = planned_packages(target, figs, record["created"])
    record["planned_packages"] = planned
    record["saved_packages"] = _save(ed, planned, bool(args.get("save_map_if_reinstanced")) and target == "bp")
    record["saved"] = True
    _write(REC, record)
    _readback(target, figs, plan, "override_after")         # again, after the save
    for f in figs:
        for cp, c in plan[f]["children"].items():
            _check_child(unreal.load_asset(cp), c["parent"], c)
    return {"figures": len(figs), "created": len(record["created"]), "saved": record["saved_packages"],
            "backup": record["backup"]}


def run_revert(run, args, ed):
    with open(REC, encoding="utf-8") as h:
        record = json.load(h)
    _require(record.get("world") == WORLD and record.get("saved"), "RECORD_INVALID")
    target, figs, plan = record["target"], record["figures"], record["plan"]
    _temp_actor_guard()
    _readback(target, figs, plan, "override_after")         # refuse if anything changed since APPLY
    _backup(run, figs)
    actors = _level_actors(figs) if target == "level" else {}
    for f in figs:
        _assign(target, f, plan[f], "override_before", actors.get(f))
    _readback(target, figs, plan, "override_before")
    saved = _save(ed, planned_packages(target, figs, []), bool(args.get("save_map_if_reinstanced")) and target == "bp")
    os.replace(REC, REC + ".reverted-" + run)
    return {"figures": len(figs), "saved": saved, "children_kept": record.get("created", [])}


def run_verify(run):
    _require(os.path.exists(REC), "NO_RECORD")
    record = json.load(open(REC, encoding="utf-8"))
    fails = []
    try:
        _readback(record["target"], record["figures"], record["plan"], "override_after")
    except SkinError as exc:
        fails.append(str(exc))
    for f in record["figures"]:
        for cp, c in record["plan"][f]["children"].items():
            try:
                _check_child(unreal.load_asset(cp), c["parent"], c)
            except Exception as exc:  # noqa: BLE001
                fails.append(str(exc))
    out = {"run": run, "census": _census(), "fails": fails}
    _write(VERIFY_OUT, out)
    _require(not fails, "VERIFY|%s|out=%s" % (fails[:5], VERIFY_OUT))
    return {"figures": len(record["figures"]), "out": VERIFY_OUT}


def main():
    run = datetime.datetime.now().strftime("S3SKIN-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        with open(ARGS, encoding="utf-8") as h:
            args = json.load(h)
        mode, target, figs = check_mode(args, os.path.exists(REC))
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = ed.get_editor_world()
        _require(world is not None and world.get_outermost().get_name() == WORLD, "WRONG_WORLD")
        _require(ed.get_game_world() is None, "PIE_ACTIVE")
        unreal.log("S3SKIN_START|run=%s|mode=%s|target=%s|figures=%s" % (run, mode, target, figs))
        if mode == "DRY":
            result = run_dry(run, args, target, figs)
        elif mode == "VERIFY":
            result = run_verify(run)
        else:
            c0 = _census()
            _require(c0 == {"content": [], "maps": []}, "DIRTY_BEFORE|" + json.dumps(c0))
            if mode == "APPLY":
                try:
                    result = run_apply(run, args, target, figs, ed)
                except Exception:
                    if os.path.exists(REC) and not json.load(open(REC, encoding="utf-8")).get("saved"):
                        os.replace(REC, REC + ".failed-" + run)
                    raise
            else:
                result = run_revert(run, args, ed)
        unreal.log("S3SKIN_%s_OK|run=%s|%s" % (mode, run, json.dumps(result, default=str)))
    except Exception as exc:
        census = {}
        try:
            census = _census()
        except Exception:  # noqa: BLE001
            pass
        unreal.log_error("S3SKIN_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            run, mode, str(exc).replace("\n", " "), json.dumps(census),
            "NOTHING SAVED unless an _OK marker printed; if anything is dirty: Don't-Save restart"
            if mode in WRITE_MODES else "read-only mode mutated nothing"))
        raise


if unreal is not None:
    main()
