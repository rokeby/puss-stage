"""FX SMOKE PLACE: DRY / APPLY / REVERT. Smoke-pot Effect sources as Show attachments (Gary 7 Oct, own words:
"Smoke plumes"; smoke in P03 asked 7 Oct). OFFLINE-WRITTEN 7 Oct, never run in Unreal.

WHAT. For each chosen bay (a Wing Pair cue of a Passage) one Show attachment: kind EFFECT, type SMOKE, anchor STATION
(fixed at the pair's station, so the wings slide past it), label "FX SMOKE Pnn Bxx L|R". The pot stands at the wing
line just off the walkway, BEHIND the flat (offstage of its inner edge and along_cm downstream of it), aimed inward,
so the plume rises behind the wing and drifts into the corridor.

ROUTE (precedent + declarations):
  - Attachments, materialize, narrow save, saved-master test: fx_candle_s6.py (live DRY/APPLY/REVERT 3-5 Oct)
    [precedent]; helpers _fx_authoring_common.py / _infinity_attachment_state.py, reused unchanged.
  - Identity: UInfinityStageEffectLibrary::AddEffectAttachment (InfinityStageEffectLibrary.h:34-41; impl .cpp:76-110
    mints FGuid::NewGuid, Kind=Effect, MakeDefaultEffectSettings(Type)) [declaration-proven]; the symbol name is in
    the installed UnrealEditor-InfinityStage.dll (6 Oct 22:40) [binary-proven]. It has NEVER run live (its only caller,
    fx_wingburn_test.py:369, never ran) [measured: no run record]. The candle used scratch-pair light replication
    only because it needed a linked LIGHT guid; a smoke pot has no light. So every returned guid is asserted fresh,
    non-zero and present in the Show after the call (memory: return values lie).
  - Class: actor_class is left EMPTY. The Passage spawns AInfinityStageEffectSource::ResolveDefaultClass for an
    Effect with no class (InfinityStagePassageActor.cpp:925-928), which loads /Game/Scenes/Effects/BP_Effect_SmokePot
    when the package exists (InfinityStageEffectSource.cpp:52-53, :117-133) [declaration-proven]. That BP was created
    by fx_effect_bps.py (FXBP-20261007-021606: PlumeFX = Cascade Humo_Par, auto_activate False) [measured record].
    APPLY refuses unless the BP loads, is an Effect Source subclass and carries PlumeFX with the expected template;
    after materialize every spawned actor is read back by its identity tag (PassageActor.cpp:968-972) and must be a
    BP_Effect_SmokePot_C whose PlumeFX template is the expected one.
  - Activation: the source activates/deactivates every UFXSystemComponent by distance to the rendered view
    (EffectSource.cpp:509-549, Tick :705); UParticleSystemComponent derives UFXSystemComponent
    (Engine/Classes/Particles/ParticleSystemComponent.h:491) [declaration-proven]. Whether Cascade RENDERS in 5.8 is
    UNPROVEN: p04_rain_pie_bench.py (alt = Humo_Par) measures it. User.Pump has no effect on Cascade templates
    [inferred], so the plume runs continuously while the camera is within active_radius_cm.
  - Medium: feeds_local_medium False by default (Smoke default would add an LFV at density 0.25,
    EffectLibrary.cpp:39-45; Gary called P03 "ridiculously foggy").

PAIR-SPACE GEOMETRY (all [inferred] unless marked):
  - Station anchor = pair root (PassageActor.cpp:1919-1921) [declaration-proven].
  - Pair-space Y is lateral, LEFT panels y<0, RIGHT y>0 (lighting_scores_apply.py:1093-1095 "measured from the live
    P02 record") [precedent]; P04 Wing 001: left panel y -972.6, right +932.1, x 0 (lighting_looks_top_probe.json)
    [measured]. Every run re-checks the sign per bay and refuses a panel that straddles y=0.
  - The flat's inner edge = min over its mesh bound corners of |y| in pair space (corners through the panel's
    local_transform, so scale, mirror and yaw are honoured) [computed live per bay in DRY; no hard-coded width].
  - Pair +X = the camera's direction of travel, so +along_cm is "behind the flat" as the camera approaches
    [inferred from P04 stills: camera x grows with Passage fraction at yaw 0, p04_rain_bench.py:118-121; NOT checked
    per Passage]. If the stills show pots in front of the flats, set along_cm negative.
  - z = z_cm over the pair root; the pair root is the floor [inferred: p03_atmos.py:70 uses panel base z as floor].

ARGS fx_smoke_place_args.json (every key optional except confirm for APPLY/REVERT):
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> FXSMOKE",
   "passages": {"P03": {"bays": [8, 13, 18]}, "P01": {"count": 3}, "P04": {"count": 3}},
        bays = 1-based ordinals in show.get_wing_pair_cue_guids_in_passage order; count = evenly spaced instead;
        optional "sides": "alternate" | "L" | "R" | ["L","R",...]  (default alternate, starting L)
   "offstage_cm": 40, "along_cm": 80, "z_cm": 0, "active_radius_cm": 2500, "output": 0.5,
   "feeds_local_medium": false, "expected_template": "/Game/Japanese_Alley/VFX/Humo_Par",
   "revert_accept_drift": false}   (true: REVERT removes our pots even if Gary moved/tuned them; the drift is reported)
Markers: FXSMOKE_DRY_OK|run=.. / FXSMOKE_APPLY_OK|run=.. / FXSMOKE_REVERT_OK|run=..; stops FXSMOKE_STOPPED|run=..|..
Record fx_smoke_place_record.json is written (exclusive) BEFORE the first Show change and after every added guid.
Reports fx_smoke_place_report_<MODE>_<run>.json. Backups Backups/PreFxSmoke[Revert]-<run>/ (Show + level).
"""
from __future__ import annotations

import importlib.util
import json
import math
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(HERE)


def _load(name):
    path = os.path.join(CORE, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load("_fx_authoring_common")
S = _load("_infinity_attachment_state")

ARGS = os.path.join(HERE, "fx_smoke_place_args.json")
RECORD = os.path.join(HERE, "fx_smoke_place_record.json")
SMOKE_BP = "/Game/Scenes/Effects/BP_Effect_SmokePot"
SMOKE_CLASS_NAME = "BP_Effect_SmokePot_C"
PLUME_COMPONENT = "PlumeFX"
DEFAULT_TEMPLATE = "/Game/Japanese_Alley/VFX/Humo_Par"
LABEL_PREFIX = "FX SMOKE "
CONFIRM_TAIL = "FXSMOKE"
TAG_PREFIX = "InfinityStage.Attachment."          # InfinityStagePassageActor.cpp:968-972
MAX_PER_PASSAGE = 4
MAX_TOTAL = 12
DEFAULTS = {
    "mode": "DRY",
    # P03: Gary asked for smoke in P03 (7 Oct); B08/B13/B18 are its Breath-flicker beam bays
    # (p03_atmos.py:26, lighting_scores_record_P03.json) so the plume crosses a beam [precedent].
    # P01/P04: evenly spaced until Gary picks bays [inferred defaults, Gary-tunable].
    "passages": {"P03": {"bays": [8, 13, 18]}, "P01": {"count": 3}, "P04": {"count": 3}},
    "offstage_cm": 40.0,
    "along_cm": 80.0,
    "z_cm": 0.0,
    "active_radius_cm": 2500.0,
    "output": 0.5,
    "feeds_local_medium": False,
    "expected_template": DEFAULT_TEMPLATE,
    "revert_accept_drift": False,
}


class SmokeError(C.FxToolError):
    pass


def require(cond, msg):
    if not cond:
        raise SmokeError(str(msg))


# ------------------------------------------------------------------ pure (offline-tested)
def passage_number(key):
    text = str(key).strip().upper()
    require(len(text) == 3 and text[0] == "P" and text[1:].isdigit() and 1 <= int(text[1:]) <= 6,
            "PASSAGE_KEY|%r" % (key,))
    return int(text[1:])


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def check_args(raw):
    a = json.loads(json.dumps(DEFAULTS))
    raw = dict(raw or {})
    unknown = sorted(set(raw) - set(DEFAULTS) - {"confirm"})
    require(not unknown, "UNKNOWN_ARGS|%s" % unknown)
    a.update(raw)
    a["mode"] = str(a["mode"]).upper()
    require(a["mode"] in ("DRY", "APPLY", "REVERT"), "MODE|%s" % a["mode"])
    if a["mode"] != "DRY":
        require(a.get("confirm") == "%s %s" % (a["mode"], CONFIRM_TAIL),
                "CONFIRM_MISSING|want '%s %s'" % (a["mode"], CONFIRM_TAIL))
    require(isinstance(a["passages"], dict) and a["passages"], "PASSAGES_EMPTY")
    total = 0
    norm = {}
    for key, spec in a["passages"].items():
        n = passage_number(key)
        require(isinstance(spec, dict), "PASSAGE_SPEC|%s" % key)
        require(set(spec) <= {"bays", "count", "sides"}, "PASSAGE_SPEC_KEYS|%s|%s" % (key, sorted(spec)))
        require(("bays" in spec) != ("count" in spec), "BAYS_XOR_COUNT|%s" % key)
        if "bays" in spec:
            bays = spec["bays"]
            require(isinstance(bays, list) and bays and all(isinstance(b, int) and not isinstance(b, bool) and b >= 1
                                                            for b in bays) and len(set(bays)) == len(bays),
                    "BAYS|%s|%r" % (key, bays))
            k = len(bays)
        else:
            k = spec["count"]
            require(isinstance(k, int) and not isinstance(k, bool) and k >= 1, "COUNT|%s|%r" % (key, k))
        require(k <= MAX_PER_PASSAGE, "TOO_MANY_IN_PASSAGE|%s|%d>%d" % (key, k, MAX_PER_PASSAGE))
        sides = spec.get("sides", "alternate")
        require(sides in ("alternate", "L", "R") or (isinstance(sides, list) and len(sides) == k
                                                     and all(s in ("L", "R") for s in sides)),
                "SIDES|%s|%r" % (key, sides))
        total += k
        norm["P%02d" % n] = dict(spec, sides=sides)
    require(total <= MAX_TOTAL, "TOO_MANY_TOTAL|%d>%d" % (total, MAX_TOTAL))
    a["passages"] = norm
    for k in ("offstage_cm", "along_cm", "z_cm", "active_radius_cm", "output"):
        require(_num(a[k]), "NUM|%s|%r" % (k, a[k]))
    require(0.0 <= float(a["offstage_cm"]) <= 400.0, "OFFSTAGE_RANGE|%r" % a["offstage_cm"])
    require(abs(float(a["along_cm"])) <= 500.0, "ALONG_RANGE|%r" % a["along_cm"])
    require(-100.0 <= float(a["z_cm"]) <= 400.0, "Z_RANGE|%r" % a["z_cm"])
    require(100.0 <= float(a["active_radius_cm"]) <= 10000.0, "RADIUS_RANGE|%r" % a["active_radius_cm"])
    require(0.0 <= float(a["output"]) <= 1.0, "OUTPUT_RANGE|%r" % a["output"])
    require(isinstance(a["feeds_local_medium"], bool), "FEEDS_LOCAL_MEDIUM_BOOL")
    require(isinstance(a["revert_accept_drift"], bool), "REVERT_ACCEPT_DRIFT_BOOL")
    require(str(a["expected_template"]).startswith("/Game/"), "TEMPLATE_PATH")
    return a


def spread_ordinals(n_bays, count):
    """count evenly spaced 1-based ordinals over n_bays (bay centres of count equal slices)."""
    require(1 <= count <= n_bays, "COUNT_EXCEEDS_BAYS|%d>%d" % (count, n_bays))
    out = [int(math.floor((i + 0.5) * n_bays / float(count))) + 1 for i in range(count)]
    require(len(set(out)) == len(out), "SPREAD_COLLIDES")
    return out


def side_list(sides, k):
    if sides == "alternate":
        return ["L" if i % 2 == 0 else "R" for i in range(k)]
    if sides in ("L", "R"):
        return [sides] * k
    return list(sides)


def inner_edge(corners_pair, sign):
    """Distance from the centre line (y=0) to the flat's inner edge on its side. corners_pair: [[x,y,z]...] of the
    panel mesh bound box in pair space; sign -1 = LEFT (y<0), +1 = RIGHT. Refuses a panel that reaches y<=0 on its
    own side (straddles the centre, or the side convention is not what we assume)."""
    require(len(corners_pair) == 8, "CORNERS|%d" % len(corners_pair))
    d = min(float(sign) * float(c[1]) for c in corners_pair)
    require(d > 0.0, "PANEL_STRADDLES_CENTRE|sign=%d|min=%.1f" % (sign, d))
    return d


def pot_transform(panel_x, edge_cm, sign, a):
    """Pair-space location + yaw for one pot: offstage of the inner edge, along_cm downstream, aimed inward."""
    y = float(sign) * (float(edge_cm) + float(a["offstage_cm"]))
    yaw = 90.0 if sign < 0 else -90.0          # +X of the source points to the centre line
    return {"location": [float(panel_x) + float(a["along_cm"]), y, float(a["z_cm"])], "yaw": yaw}


def label_for(pkey, ordinal, side):
    return "%s%s B%02d %s" % (LABEL_PREFIX, pkey, int(ordinal), side)


def plan_rows(a, live):
    """live: {"P03": {"passage_guid": .., "bays": [{"ordinal", "cue_guid", "label",
    "L": {"x", "corners"}, "R": {...}}, ...]}, ...} -> placement rows (pure)."""
    rows = []
    for pkey in sorted(a["passages"]):
        spec = a["passages"][pkey]
        require(pkey in live, "PASSAGE_NOT_LIVE|%s" % pkey)
        bays = live[pkey]["bays"]
        require(bays, "PASSAGE_HAS_NO_BAYS|%s" % pkey)
        ords = list(spec["bays"]) if "bays" in spec else spread_ordinals(len(bays), int(spec["count"]))
        missing = [o for o in ords if o > len(bays)]
        require(not missing, "BAY_OUT_OF_RANGE|%s|%s>%d" % (pkey, missing, len(bays)))
        for o, side in zip(ords, side_list(spec["sides"], len(ords))):
            bay = bays[o - 1]
            require(int(bay["ordinal"]) == o, "ORDINAL_MISMATCH|%s|%d" % (pkey, o))
            sign = -1 if side == "L" else 1
            panel = bay[side]
            edge = inner_edge(panel["corners"], sign)
            t = pot_transform(panel["x"], edge, sign, a)
            rows.append({"passage": pkey, "ordinal": o, "side": side, "cue_guid": bay["cue_guid"],
                         "cue_label": bay["label"], "inner_edge_cm": round(edge, 3),
                         "location": [round(v, 3) for v in t["location"]], "yaw": t["yaw"],
                         "label": label_for(pkey, o, side)})
    labels = [r["label"] for r in rows]
    require(len(set(labels)) == len(labels), "DUPLICATE_LABELS")
    return rows


def leftovers(existing_labels):
    return sorted(x for x in existing_labels if str(x).startswith(LABEL_PREFIX))


def drift_paths(expected, live):
    return [d["path"] for d in S.state_differences(expected, live)]


def revert_gate(record, live_states, accept_drift):
    """record: applied record; live_states: {guid: state or None}. -> (ok, problems, drift)."""
    problems, drift = [], {}
    require(record.get("status") == "applied", "REVERT_RECORD_NOT_APPLIED|%s" % record.get("status"))
    for row in record["added"]:
        g = row["guid"]
        live = live_states.get(g)
        if live is None:
            problems.append("MISSING|%s|%s" % (g, row["label"]))
            continue
        paths = drift_paths(row["expected"], live)
        if paths:
            drift[g] = paths
            identity = [p for p in paths if p.split(".")[0] in ("guid", "kind", "label")]
            if identity or not accept_drift:
                problems.append("DRIFT|%s|%s" % (g, paths[:6]))
    return (not problems), problems, drift


# ------------------------------------------------------------------ Unreal
def _enum(enum_type, *names):
    return C.enum_member(enum_type, *names)


def _cue_index(show, guid_text):
    hits = [i for i, c in enumerate(show.get_editor_property("cues"))
            if C.guid_text(c.get_editor_property("cue_guid")) == guid_text]
    require(len(hits) == 1, "CUE_INDEX|%s|%d" % (guid_text, len(hits)))
    return hits[0]


def _pair(show, index):
    cue = list(show.get_editor_property("cues"))[index]
    return cue, cue.get_editor_property("wing_pair")


def _set_pair_attachments(show, index, attachments):
    """fx_candle_s6.py:202-207 (+ _set_cue :195-199): struct copies written back cue -> cues -> Show."""
    cues = list(show.get_editor_property("cues"))
    cue = cues[index]
    pair = cue.get_editor_property("wing_pair")
    pair.set_editor_property("attachments", list(attachments))
    cue.set_editor_property("wing_pair", pair)
    cues[index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _all_labels(show):
    out = []
    for cue in show.get_editor_property("cues"):
        for item in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            out.append(str(item.get_editor_property("label")))
    return out


def _all_guids(show):
    return {C.guid_text(item.get_editor_property("attachment_guid"))
            for cue in show.get_editor_property("cues")
            for item in cue.get_editor_property("wing_pair").get_editor_property("attachments")}


def _panel_live(panel):
    t = panel.get_editor_property("local_transform")
    mesh = panel.get_editor_property("mesh")
    if mesh is not None and not hasattr(mesh, "get_bounds"):
        # a soft pointer surfaced as a path rather than the object: load it (read-only)
        mesh = unreal.load_asset(C.asset_id(mesh))
    require(mesh is not None and hasattr(mesh, "get_bounds"), "PANEL_MESH_UNREADABLE|%r" % (mesh,))
    b = mesh.get_bounds()
    o, e = b.origin, b.box_extent
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = unreal.MathLibrary.transform_location(
                    t, unreal.Vector(o.x + sx * e.x, o.y + sy * e.y, o.z + sz * e.z))
                corners.append([float(p.x), float(p.y), float(p.z)])
    return {"x": float(t.translation.x), "corners": corners, "mesh": C.asset_id(mesh)}


def _live(show, passages):
    rows = {}
    settings = {str(s.get_editor_property("label")): s for s in show.get_editor_property("passage_settings")}
    for pkey in passages:
        label = "Passage %d" % passage_number(pkey)
        require(label in settings, "PASSAGE_SETTINGS_MISSING|%s" % label)
        pguid = settings[label].get_editor_property("passage_guid")
        bays = []
        for o, g in enumerate(show.get_wing_pair_cue_guids_in_passage(pguid), start=1):
            gt = C.guid_text(g)
            idx = _cue_index(show, gt)
            cue, pair = _pair(show, idx)
            bays.append({"ordinal": o, "cue_guid": gt, "label": str(cue.get_editor_property("label")),
                         "L": _panel_live(pair.get_editor_property("left")),
                         "R": _panel_live(pair.get_editor_property("right"))})
        rows[pkey] = {"passage_guid": C.guid_text(pguid), "label": label, "bays": bays}
    return rows


def _bp_gate(expected_template):
    """fx_candle_s6.py:498-537 pattern: the class must exist, be an Effect Source and carry PlumeFX(template)."""
    require(unreal.EditorAssetLibrary.does_asset_exist(SMOKE_BP), "SMOKE_BP_MISSING|%s" % SMOKE_BP)
    cls = unreal.EditorAssetLibrary.load_blueprint_class(SMOKE_BP)
    require(cls is not None, "SMOKE_CLASS_LOAD")
    require(isinstance(unreal.get_default_object(cls), unreal.InfinityStageEffectSource), "SMOKE_NOT_EFFECT_SOURCE")
    bp = unreal.EditorAssetLibrary.load_asset(SMOKE_BP)
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    found = None
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = lib.get_data(h)
        if str(lib.get_variable_name(data)) == PLUME_COMPONENT:
            found = lib.get_object_for_blueprint(data, bp) or lib.get_associated_object(data)
    require(isinstance(found, unreal.ParticleSystemComponent), "SMOKE_BP_NO_PLUMEFX")
    template = C.asset_id(found.get_editor_property("template"))
    require(template == expected_template, "SMOKE_TEMPLATE|%s|want %s" % (template, expected_template))
    return {"bp": SMOKE_BP, "plume_template": template}


def _make_transform(row):
    return unreal.Transform(location=unreal.Vector(*row["location"]),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(row["yaw"])),
                            scale=unreal.Vector(1.0, 1.0, 1.0))


def _add_one(show, row, a, preexisting):
    smoke = _enum(unreal.InfinityStageEffectType, "SMOKE")
    station = _enum(unreal.InfinityAttachmentAnchor, "STATION")
    cue_guid = list(show.get_editor_property("cues"))[_cue_index(show, row["cue_guid"])].get_editor_property("cue_guid")
    guid = unreal.InfinityStageEffectLibrary.add_effect_attachment(
        show, cue_guid, smoke, station, _make_transform(row), row["label"])
    gt = C.guid_text(guid)
    compact = "".join(ch for ch in gt if ch in "0123456789ABCDEF")
    require(len(compact) == 32 and compact.strip("0"), "ADD_INVALID_GUID|%s" % gt)
    require(gt not in preexisting, "ADD_GUID_NOT_FRESH|%s" % gt)
    index = _cue_index(show, row["cue_guid"])
    unused_cue, pair = _pair(show, index)
    items = list(pair.get_editor_property("attachments"))
    hits = [i for i, it in enumerate(items) if C.guid_text(it.get_editor_property("attachment_guid")) == gt]
    require(len(hits) == 1, "ADD_NOT_IN_SHOW|%s|%d" % (gt, len(hits)))
    item = items[hits[0]]
    settings = item.get_editor_property("effect")
    require(settings.get_editor_property("type") == smoke, "ADD_TYPE_NOT_SMOKE")
    settings.set_editor_property("output", float(a["output"]))
    settings.set_editor_property("active_radius_cm", float(a["active_radius_cm"]))
    settings.set_editor_property("feeds_local_medium", bool(a["feeds_local_medium"]))
    item.set_editor_property("effect", settings)
    item.set_editor_property("enabled", True)
    items[hits[0]] = item
    _set_pair_attachments(show, index, items)
    state = _state_of(show, row["cue_guid"], gt)
    require(state is not None, "ADD_READBACK_MISSING|%s" % gt)
    eff = state["effect"]
    require(abs(eff["active_radius_cm"] - float(a["active_radius_cm"])) < 1e-3
            and eff["feeds_local_medium"] == bool(a["feeds_local_medium"])
            and abs(eff["output"] - float(a["output"])) < 1e-4 and state["enabled"] is True
            and state["label"] == row["label"] and "STATION" in state["anchor"].upper()
            and "/Game/" not in str(state["actor_class"]),
            "ADD_READBACK_MISMATCH|%s|%s" % (gt, json.dumps(state, default=str)[:400]))
    loc = state["relative_transform"]["location"]
    require(max(abs(p - q) for p, q in zip(loc, row["location"])) < 0.01, "ADD_LOCATION_MISMATCH|%s|%s" % (gt, loc))
    return gt, state


def _state_of(show, cue_guid_text, att_guid_text):
    unused_cue, pair = _pair(show, _cue_index(show, cue_guid_text))
    for it in pair.get_editor_property("attachments"):
        if C.guid_text(it.get_editor_property("attachment_guid")) == att_guid_text:
            return S.attachment_state(it, C.guid_text)
    return None


def _remove(show, cue_guid_text, guid_texts):
    index = _cue_index(show, cue_guid_text)
    unused_cue, pair = _pair(show, index)
    items = list(pair.get_editor_property("attachments"))
    keep = [it for it in items if C.guid_text(it.get_editor_property("attachment_guid")) not in set(guid_texts)]
    require(len(items) - len(keep) == len(set(guid_texts)), "REMOVE_COUNT|%s" % cue_guid_text)
    _set_pair_attachments(show, index, keep)


def _spawned(rows_by_guid):
    """Spawned actors by identity tag -> {guid: {"class", "templates", "location"}}."""
    out = {}
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in sub.get_all_level_actors():
        for tag in actor.tags:
            text = str(tag)
            if not text.startswith(TAG_PREFIX):
                continue
            pair = text[len(TAG_PREFIX):].split("|")
            if len(pair) != 2 or pair[1].upper() not in rows_by_guid:
                continue
            comps = actor.get_components_by_class(unreal.ParticleSystemComponent)
            loc = actor.get_actor_location()
            out.setdefault(pair[1].upper(), []).append({
                "class": actor.get_class().get_name(),
                "templates": {str(c.get_name()): C.asset_id(c.get_editor_property("template")) for c in comps},
                "location": [float(loc.x), float(loc.y), float(loc.z)]})
    return out


def _check_spawned(spawned, guids, expected_template):
    for g in guids:
        hits = spawned.get(g, [])
        require(len(hits) == 1, "SPAWNED_COUNT|%s|%d" % (g, len(hits)))
        require(hits[0]["class"] == SMOKE_CLASS_NAME, "SPAWNED_CLASS|%s|%s (greybox fallback?)" % (g, hits[0]["class"]))
        require(hits[0]["templates"].get(PLUME_COMPONENT) == expected_template,
                "SPAWNED_PLUME|%s|%s" % (g, hits[0]["templates"]))


def _materialize(show, pkeys):
    for pkey in sorted(pkeys):
        actor = C.find_passage_actor(unreal, show, passage_number(pkey))
        require(actor.materialize_passage(), "MATERIALIZE_FAILED|%s" % pkey)


def _write_report(mode, run, report):
    path = os.path.join(HERE, "fx_smoke_place_report_%s_%s.json" % (mode, run))
    C.write_json(path, report)
    return path


def main():
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    run = C.stamp_now()
    a = check_args(json.load(open(ARGS, encoding="utf-8")) if os.path.exists(ARGS) else {})
    report = {"run": run, "mode": a["mode"], "args": a, "ok": False}
    phase = {"saved": False, "record_written": False}
    try:
        unused_editor, world = C.editor_context(unreal)
        report["dirty_before"] = C.require_clean(unreal, "PRE")
        show = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        require(show is not None, "SHOW_LOAD_FAILED")
        expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}

        if a["mode"] == "REVERT":
            require(os.path.isfile(RECORD), "REVERT_RECORD_MISSING")
            rec = C.load_json(RECORD)
            live = {r["guid"]: _state_of(show, r["cue_guid"], r["guid"]) for r in rec["added"]}
            ok, problems, drift = revert_gate(rec, live, a["revert_accept_drift"])
            report["drift"] = drift
            require(ok, "REVERT_GATE|%s" % problems)
            backup = C.backup_packages(unreal, "PreFxSmokeRevert-", run, [C.SHOW_PATH, C.EXPECTED_WORLD])
            report["backup"] = backup
            by_cue = {}
            for r in rec["added"]:
                by_cue.setdefault(r["cue_guid"], []).append(r["guid"])
            for cg, gs in sorted(by_cue.items()):
                _remove(show, cg, gs)
            _materialize(show, {r["passage"] for r in rec["added"]})
            require(C.dirty_census(unreal) == expected_dirty, "REVERT_DIRTY_SCOPE|%s" % C.dirty_census(unreal))
            C.save_show_and_level(unreal)
            gone = {r["guid"]: _state_of(show, r["cue_guid"], r["guid"]) for r in rec["added"]}
            require(all(v is None for v in gone.values()), "REVERT_READBACK_PRESENT")
            left = _spawned({r["guid"]: r for r in rec["added"]})
            require(not left, "REVERT_SPAWNED_LEFT|%s" % sorted(left))
            report["saved_master_command"] = C.queue_saved_master_test(unreal, world, "FXSMOKE_REVERT", run)
            report.update({"ok": True, "archived_record": C.archive_record(RECORD, run),
                           "dirty_after": C.dirty_census(unreal)})
            path = _write_report("REVERT", run, report)
            unreal.log("FXSMOKE_REVERT_OK|run=%s|removed=%d|report=%s" % (run, len(rec["added"]), path))
            return

        gate = _bp_gate(a["expected_template"])
        left = leftovers(_all_labels(show))
        require(not left, "LEFTOVER_SMOKE_LABELS|%s" % left)
        live = _live(show, a["passages"])
        rows = plan_rows(a, live)
        report.update({"bp_gate": gate, "plan": rows,
                       "panels": {k: [{"ordinal": b["ordinal"], "label": b["label"],
                                       "L_mesh": b["L"]["mesh"], "R_mesh": b["R"]["mesh"]} for b in v["bays"]]
                                  for k, v in live.items()}})

        if a["mode"] == "DRY":
            require(C.dirty_census(unreal) == report["dirty_before"], "DRY_CHANGED_CENSUS")
            report.update({"ok": True, "dirty_after": C.dirty_census(unreal)})
            path = _write_report("DRY", run, report)
            unreal.log("FXSMOKE_DRY_OK|run=%s|pots=%d|passages=%s|report=%s"
                       % (run, len(rows), ",".join(sorted(a["passages"])), path))
            return

        require(not os.path.exists(RECORD), "RECORD_EXISTS|" + RECORD)
        backup = C.backup_packages(unreal, "PreFxSmoke-", run, [C.SHOW_PATH, C.EXPECTED_WORLD])
        show_hash_before = backup["packages"][0]["sha256"]
        record = {"status": "prepared", "run": run, "args": a, "plan": rows, "backup": backup, "added": []}
        C.write_json(RECORD, record, exclusive=True)
        phase["record_written"] = True
        preexisting = _all_guids(show)
        for row in rows:
            gt, state = _add_one(show, row, a, preexisting)
            preexisting.add(gt)
            record["added"].append(dict(row, guid=gt, expected=state))
            C.write_json(RECORD, record)
        _materialize(show, {r["passage"] for r in rows})
        require(C.dirty_census(unreal) == expected_dirty, "APPLY_DIRTY_SCOPE|%s" % C.dirty_census(unreal))
        C.save_show_and_level(unreal)
        phase["saved"] = True
        show_rb = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        for r in record["added"]:
            got = _state_of(show_rb, r["cue_guid"], r["guid"])
            require(got is not None and not drift_paths(r["expected"], got), "SAVED_READBACK_MISMATCH|%s" % r["guid"])
        require(C.sha256(C.package_file(unreal, C.SHOW_PATH)) != show_hash_before, "SHOW_FILE_UNCHANGED_ON_DISK")
        spawned = _spawned({r["guid"]: r for r in record["added"]})
        _check_spawned(spawned, [r["guid"] for r in record["added"]], a["expected_template"])
        command = C.queue_saved_master_test(unreal, world, "FXSMOKE", run)
        record.update({"status": "applied", "spawned": spawned, "saved_master_command": command})
        C.write_json(RECORD, record)
        report.update({"ok": True, "backup": backup, "added": record["added"], "spawned": spawned,
                       "dirty_after": C.dirty_census(unreal), "saved_master_command": command})
        path = _write_report("APPLY", run, report)
        unreal.log("FXSMOKE_APPLY_OK|run=%s|pots=%d|backup=%s|report=%s" % (run, len(rows), backup["root"], path))
    except Exception as error:  # noqa: BLE001 - every stop is reported, then re-raised
        report["error"] = str(error)
        try:
            report["census_at_stop"] = C.dirty_census(unreal)
        except Exception:  # noqa: BLE001
            pass
        if a["mode"] == "APPLY" and phase["record_written"] and not phase["saved"] and os.path.exists(RECORD):
            # nothing reached disk: the in-memory Show edit dies with a Don't-Save restart, so the record must
            # not block the next APPLY or invite a REVERT of guids that were never saved
            os.replace(RECORD, RECORD + ".failed-" + run)
            report["record_archived"] = RECORD + ".failed-" + run
        report["saved"] = phase["saved"]
        _write_report(a["mode"] + "_STOPPED", run, report)
        unreal.log_error("FXSMOKE_STOPPED|run=%s|mode=%s|%s|census=%s|if anything is dirty: Don't-Save restart"
                         % (run, a["mode"], error, report.get("census_at_stop")))
        raise


if unreal is not None and __name__ in ("__main__", "__fx_smoke_place_runner__"):
    main()
