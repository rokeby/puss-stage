"""RZSWAP -- realism mesh swaps onto EXISTING P02 / P03 pair-cue rows: pure core (7 Oct, offline-written, NEVER RUN IN
UNREAL).  No `unreal` import.

7 Oct (later): REMAP mode (make_remap_plan, below the scoring code) -- a deterministic 1:1 {old mesh -> new mesh} swap
for any passage in PASSAGES (P06 added for the 12-flap v3 rebuilds); scoring (make_plan) supports P01-P04.  Every
cue's mechanism text is asserted unchanged by rzswap.py in BOTH modes (mechanism_drift).

SCOPE (extended 9 Oct): mesh swaps ONLY -- an existing L/R panel, or an explicitly planned T (Top) panel, gets a
realism mesh and its placement.  No gaps, no row count, no timing, no mechanisms or lights.  The ONLY fields ever
written: WingPair.Left / WingPair.Right / WingPair.Top -> Mesh, MaterialOverrides, LocalTransform,
FacingPolicy, bFlipImageHorizontally of the target sides (exactly what swapkit common.set_panel writes,
swapkit/common.py:230-254 [prec, ran in every swapkit APPLY and the P06 relayout P06RL-20261007-081048]).
bCastShadow / bVisibleInMainPass / Collision of the panel are NOT written (InfinityStageTypes.h:630-637 [decl]) and
are asserted unchanged.

Tiers per claim: [decl] read in source/header/config (cited), [prec] an in-repo tool made the same call and it RAN
(cited with its record), [meas] measured offline here or read back from a live record (cited), [inf] inferred (why).

PLACEMENT: the slot-D inner_edge rule in the UNREAL frame (swapkit/dry.py:93-123 [prec, ran 6 Oct FV3D]; the P06
relayout placements, relayout_apply.py:257-287, measured inner-edge deltas <= 3e-5 cm on 58 sides, record
relayout_apply_P06RL-20261007-081048.json [meas]): the new mesh's inner edge lands exactly on the old panel's inner
edge, from live bounds via common.side_bounds; planned panel = PRESERVE_ASSET, no flip, identity rotation/scale,
location (0, y, 0) (common.planned_panel, :433-438 [prec]).  Sides whose OLD local transform is not (0, y, 0) /
identity are never candidates (an authored offset we cannot interpret).  Never the TK lateral shift (memory
tk-lateral-shift-frame-mirrored).  Side = the design's BUILT side (owner suffix _L/_R); never flipped.

WHO IS PROTECTED (never replaced), each with its source:
  * IND 3D pieces (mesh name contains "_IND_", ~72-97 cm thick [meas topple_measurements.json via relayout_core.py:47]).
  * end rows: the passage's first and last enabled rows (Show PassageSettings FirstCueGuid/LastCueGuid -- the
    relayout's FIRST/LAST_ROW_MUST_STAY rule, relayout_core.py:276-279 [prec]); they frame the Scene handoffs and the
    hangar dock / end drape (p01_shorten.py:34, p02_straighten.py:66-67, passage_end_drape.py header [decl]).
    Count per end is opts["end_rows"] (default 1).
  * Master wing pins on the row (pins travel with the cue -- relayout master_p06_pins, relayout_apply.py:289-298 [prec]).
  * special mechanism: Kind != Slide or PlaybackMode in {OneShot, CameraGust} (EInfinityMechanismKind /
    EInfinityMotionPlaybackMode, InfinityStageTypes.h:573-582, :687-694 [decl]) -- topple/turn/trap/gust rows depend
    on the panel geometry.
  * EFFECT attachments on the row (fx_smoke_place 7 Oct put smoke on P03 Wing 008 L / 013 R / 018 L,
    Saved/CodexConductor/Effects_20261007/fx_smoke_place_record.json [meas]): the side named by the label suffix, else
    both; and any attachment whose export text names the side's current mesh (keyed to that mesh).
  * records (rzswap_protect.json, each entry cites its record): P02 Wing 003 keep_old (swapkit/run_p02.json
    keep_old_sides, FV3P02-20261002-02); P03 kept convent heroes (P03_LAYOUT_DRAFT.json kept_existing_lr); P03 pyre
    families flagged effects_handoff (P03_LAYOUT_DRAFT.json family_catalog).
  * realism already placed, disabled rows, empty panels, thick legacy (> 12 cm, not a V2 card), rows without a
    world-edge baseline (not materialized), and sides whose old local transform is not plain.

SCORING (deterministic; higher = replace first; documented in every plan):
  1000 x [V2 10 cm card: mesh outside /FlatV3/ and live thickness <= 12 cm]   (a) "V2 10 cm cards (flat, relief off)"
  + 100 x (rows in the passage carrying the same design family - 1)         (b) "the most-repeated designs"
  + 50 x [the row before or after carries the same family on the same side] (c) "adjacent same-design rows"
  tie-break: earlier pass time first, then L before R.
ASSIGNMENT (greedy over the scored sides): a realism design built for that side, intended for this passage, imported
(rzimport VERIFY) and live in the editor (DRY); each design at most 2x per passage (MAX_USES, counting realism already
standing) and never on the same side of two adjacent rows; among the allowed ones the least used, then the closest
height to the old panel, then the owner name.  opts["pair_mode"] "row" swaps only rows whose two sides can both take a
realism design (P02's matched-pair rule, P02_LAYOUT_DRAFT_v2.json rules[0] "L and R of one position are always the
same family (Gary 2 Oct)"); default "side" swaps per side and FLAGS each mixed row for Gary.
"""
import hashlib
import json
import re

MARK = "FLATV3_RZSWAP"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"              # relayout_core.py:34 [prec, ran]
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SHOW_FILE_REL = "Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset"
UMAP_FILE_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"

# Passage GUIDs [meas Saved/CodexConductor/dead_bulbs_warm_record.json, a live read 7 Oct 02:46]; actor label prefix
# [prec swapkit/run_p02.json / run_p03.json passage_actor_label_prefix]; the DRY asserts both live.
PASSAGES = {"P01": {"guid": "659D5386D64DA7742A351B9499ECCE4C", "actor_prefix": "Passage 01"},
            "P02": {"guid": "7FF34BBDA744E406C264A7B7E4DD61D9", "actor_prefix": "Passage 02"},
            "P03": {"guid": "49F93D652B46B99C10116EBAE927A3C6", "actor_prefix": "Passage 03"},
            "P04": {"guid": "0067B5F57142956FB5B80EA31B1210B5", "actor_prefix": "Passage 04"},
            # P06 (added 7 Oct for REMAP mode): guid = relayout_core.py:39 P06_GUID [decl; ran in P06RL-20261007-081048];
            # actor label prefix = swapkit/run_p06.json passage_actor_label_prefix [prec]; the DRY asserts both live.
            "P06": {"guid": "9BFC29C45D47911FF7836BB8537230D2", "actor_prefix": "Passage 06"}}

SCORING_PASSAGES = ("P01", "P02", "P03", "P04")

WRITTEN_PANEL_FIELDS = ("Mesh", "MaterialOverrides", "LocalTransform", "FacingPolicy", "bFlipImageHorizontally")
SIDE_FIELD = {"L": "Left", "R": "Right", "T": "Top"}
SIDE_PROP = {"L": "left", "R": "right", "T": "top"}
REALISM_ROOT = "/Game/Scenes/Wings/FlatV3/Realism/"
V3_ROOT = "/Game/Scenes/Wings/FlatV3/"
IND_TOKEN = "_IND_"
V2_CARD_MAX_THICK_CM = 12.0
MAX_USES = 2
EDGE_TOL_CM = 1.0            # relayout_apply.py:59 [prec]
CONTROL_TOL_CM = 0.05        # relayout_apply.py:60 [prec]
PLACE_TOL_CM = 0.01          # relayout placements INNER_EDGE_PLAN_FAIL tolerance [prec]
PLAIN_TOL = 0.01
SCORE_V2, SCORE_REPEAT, SCORE_ADJ = 1000, 100, 50
P04_FRONT_GROWTH_MAX_CM = 6.0


def row_sides(row):
    """Panel sides actually present in a DRY row.  Top is real only when bHasTop and the DRY measured it."""
    out = [s for s in ("L", "R") if s in row.get("sides", {})]
    if row.get("has_top") and "T" in row.get("sides", {}):
        out.append("T")
    return out


class PlanError(Exception):
    pass


def require(cond, reason):
    if not cond:
        raise PlanError(reason)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def sha_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =====================================================================================================================
# Classification
# =====================================================================================================================

def mesh_name(mesh):
    return None if not mesh else str(mesh).rsplit("/", 1)[-1].split(".", 1)[0]


_VARIANT = re.compile(r"(_(t5[pij]|sc\d+|v\d+|o\d+p?|CR\d+|r\d+|B\d+|Mount[LR]))+$")


def family_of(mesh):
    """Design family, side-agnostic: SM_FlatV3_P02_SET01_L_t5p -> P02_SET01; SM_P03_SunWashedAdministration_01_L ->
    P03_SunWashedAdministration_01; SM_FlatV3_P04_coventry_ruin_L_v2_t5p -> P04_coventry_ruin."""
    n = mesh_name(mesh)
    if n is None:
        return None
    for p in ("SM_FlatV3_", "SM_"):
        if n.startswith(p):
            n = n[len(p):]
            break
    for _ in range(3):
        n = _VARIANT.sub("", n)
        n2 = re.sub(r"_+[LRC]$", "", n)
        if n2 == n:
            break
        n = n2
    return n


def classify(mesh, thickness_cm):
    if not mesh:
        return "EMPTY"
    if REALISM_ROOT in mesh:
        return "REALISM"
    if IND_TOKEN in (mesh_name(mesh) or ""):
        return "IND_3D"
    if mesh.startswith(V3_ROOT):
        return "V3"
    if thickness_cm is not None and float(thickness_cm) <= V2_CARD_MAX_THICK_CM:
        return "V2_CARD"
    return "LEGACY_THICK_OR_UNMEASURED"


def plain_transform(lt):
    """(0, y, 0), zero rotation, unit scale -- the only old placements this tool replaces."""
    loc, rot, sc = lt["location"], lt["rotation"], lt["scale"]
    return abs(loc[0]) <= PLAIN_TOL and abs(loc[2]) <= PLAIN_TOL and all(abs(r) <= PLAIN_TOL for r in rot) and \
        all(abs(s - 1.0) <= PLAIN_TOL for s in sc)


def special_mechanism(mech):
    kind = str(mech.get("kind", "")).upper()
    play = str(mech.get("playback_mode", "")).upper()
    if "SLIDE" not in kind:
        return "MECHANISM_KIND %s" % mech.get("kind")
    if "ONE_SHOT" in play or "ONESHOT" in play or "CAMERA_GUST" in play or "CAMERAGUST" in play:
        return "MECHANISM_PLAYBACK %s" % mech.get("playback_mode")
    return ""


def effect_sides(attachments):
    """Sides an EFFECT attachment belongs to: label suffix ' L' / ' R' (fx_smoke_place labels 'FX SMOKE P03 B08 L'
    [meas record]); no suffix -> both."""
    out = set()
    for a in attachments:
        if "EFFECT" not in str(a.get("kind", "")).upper():
            continue
        lab = str(a.get("label", "")).strip()
        if lab.endswith(" T") or lab.upper().endswith(" TOP"):
            out.add("T")
        elif lab.endswith(" L"):
            out.add("L")
        elif lab.endswith(" R"):
            out.add("R")
        else:
            out |= {"L", "R", "T"}
    return out


# =====================================================================================================================
# DRY measurement -> per-side facts
# =====================================================================================================================

def state_for_hash(dry):
    """The swap-relevant live state (what a plan depends on).  Deliberately EXCLUDES light/attachment edits by other
    streams except the protect-relevant facts (EFFECT sides, mesh-referencing attachments)."""
    rows = []
    for r in dry["rows"]:
        rows.append([r["cue_guid"], r["enabled"], r["mechanism"], bool(r.get("master_pinned")),
                      sorted(effect_sides(r.get("attachments", []))),
                      {s: [r["sides"][s]["panel"], r["sides"][s].get("attachment_refs_mesh", False),
                           r["sides"][s].get("old_bounds"), r["sides"][s].get("box_cm"),
                           r["sides"][s].get("route_interval_cm"), r["sides"][s].get("route_faces_cm"),
                           r["sides"][s].get("placement_anchor")]
                       for s in row_sides(r)}, r.get("prop_route_intervals", [])])
    cands = {m: [c.get("exists"), c.get("zero_bounds"), c.get("box_cm")]
             for m, c in sorted(dry.get("candidates", {}).items())}
    return {"passage": dry["passage"], "passage_guid": dry["passage_guid"], "rows": rows,
            "first": dry["settings"]["first_cue_guid"], "last": dry["settings"]["last_cue_guid"], "candidates": cands}


def state_hash(dry):
    return sha(state_for_hash(dry))


def side_facts(dry, protect, opts):
    """Every (row, side) with class, family, protections, score inputs.  Pure."""
    rows = dry["rows"]
    n = len(rows)
    end_rows = int(opts.get("end_rows", 1))
    prot = protect.get(dry["passage"], {}) if protect else {}
    prot_sides = {(p["cue_guid"], p["side"]): p for p in prot.get("sides", [])}
    prot_fam = {f["family"]: f for f in prot.get("families", [])}
    first, last = dry["settings"]["first_cue_guid"], dry["settings"]["last_cue_guid"]
    fam_rows = {}
    for r in rows:
        for s in row_sides(r):
            f = family_of(r["sides"][s]["panel"]["mesh"])
            if f:
                fam_rows.setdefault(f, set()).add(r["ordinal"])
    out = []
    for i, r in enumerate(rows):
        eff = effect_sides(r.get("attachments", []))
        for s in row_sides(r):
            sd = r["sides"][s]
            mesh = sd["panel"]["mesh"]
            cls = "TOP_BORDER" if s == "T" and r.get("has_top") else classify(mesh, sd.get("thickness_cm"))
            fam = family_of(mesh)
            why = []
            if not r["enabled"]:
                why.append("DISABLED")
            if i < end_rows or i >= n - end_rows or r["cue_guid"] in (first, last):
                why.append("END_ROW (frames a Scene handoff / hangar dock / end drape)")
            if r.get("master_pinned"):
                why.append("MASTER_PIN")
            sm = special_mechanism(r["mechanism"])
            if sm:
                why.append("SPECIAL_" + sm)
            if s in eff:
                why.append("EFFECT_ATTACHMENT")
            if sd.get("attachment_refs_mesh"):
                why.append("ATTACHMENT_REFERENCES_MESH")
            ps = prot_sides.get((r["cue_guid"], s))
            if ps is not None:
                if ps.get("label") and ps["label"] != r["label"]:
                    why.append("PROTECT_RECORD_STALE label %r != live %r (re-check the record)" % (ps["label"], r["label"]))
                why.append("RECORD_KEEP %s [%s]" % (ps.get("reason", ""), ps.get("source", "")))
            if fam in prot_fam:
                why.append("RECORD_FAMILY %s [%s]" % (fam, prot_fam[fam].get("source", "")))
            if cls == "IND_3D":
                why.append("IND_3D")
            elif cls == "REALISM":
                why.append("REALISM_ALREADY")
            elif cls == "EMPTY":
                why.append("EMPTY_PANEL")
            elif cls == "LEGACY_THICK_OR_UNMEASURED":
                why.append("LEGACY_THICK_OR_UNMEASURED %s cm" % sd.get("thickness_cm"))
            if s == "T":
                if not sd.get("placement_anchor"):
                    why.append("NO_TOP_PLACEMENT_ANCHOR")
            elif not plain_transform(sd["panel"]["local_transform"]):
                why.append("OLD_LOCAL_TRANSFORM_NOT_PLAIN %s" % sd["panel"]["local_transform"])
            if s != "T" and not sd.get("old_bounds"):
                why.append("NO_OLD_BOUNDS")
            if not sd.get("edge_baseline"):
                why.append("NO_WORLD_EDGE_BASELINE (not materialized?)")
            adj = False
            for j in (i - 1, i + 1):
                if 0 <= j < n and s in rows[j].get("sides", {}) and fam and \
                        family_of(rows[j]["sides"][s]["panel"]["mesh"]) == fam:
                    adj = True
            reps = len(fam_rows.get(fam, ())) if fam else 0
            score = (SCORE_V2 if cls == "V2_CARD" else 0) + SCORE_REPEAT * max(0, reps - 1) + (SCORE_ADJ if adj else 0)
            out.append({"key": "%s|%s" % (r["cue_guid"], s), "cue_guid": r["cue_guid"], "label": r["label"],
                        "ordinal": r["ordinal"], "side": s, "pass_s": r["pass_s"], "mesh": mesh, "class": cls,
                        "family": fam, "family_rows": reps, "adjacent_same_family": adj,
                        "height_cm": sd.get("height_cm"), "thickness_cm": sd.get("thickness_cm"),
                        "protected": why, "eligible": not why, "score": score})
    return out


# =====================================================================================================================
# Placement (pure) -- slot-D inner_edge rule
# =====================================================================================================================

def inner_edge_y(side, old_bounds, zero_bounds):
    """swapkit/dry.py:93-123 / relayout_core.py:405-410 [prec]: L inner = max Y, R inner = min Y (panel-local)."""
    k = "max_y_cm" if side == "L" else "min_y_cm"
    return float(old_bounds[k]) - float(zero_bounds[k])


def planned_panel(mesh_path, y):
    """swapkit/common.py:433-438 [prec]."""
    return {"mesh": mesh_path, "material_overrides": [],
            "local_transform": {"location": [0.0, float(y), 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            "facing_policy": "PRESERVE_ASSET", "flip_image_horizontally": False}


def planned_top_panel(mesh_path, box, anchor):
    """Centred valance whose upper edge stays on the existing Top panel's local top-border Z."""
    require(box and anchor, "TOP_PLACEMENT_NEEDS_BOX_AND_ANCHOR")
    y = float(anchor["center_y_cm"]) - (float(box["min"][1]) + float(box["max"][1])) * 0.5
    z = float(anchor["top_z_cm"]) - float(box["max"][2])
    panel = planned_panel(mesh_path, y)
    panel["local_transform"]["location"][2] = z
    return panel


def _interval_gap(a, b):
    """Positive separation, zero for touch, negative overlap (cm)."""
    if float(a[1]) < float(b[0]):
        return float(b[0]) - float(a[1])
    if float(b[1]) < float(a[0]):
        return float(a[0]) - float(b[1])
    return -min(float(a[1]), float(b[1])) + max(float(a[0]), float(b[0]))


def p04_clearance(dry, row, side, new_box):
    """Analytical longitudinal gate from the fresh DRY.

    The materialized current panel supplies its route-distance interval.  Candidate min/max X moves that interval's
    front/back faces.  Every L/R/T panel and measured PROP actor on the immediately adjacent rows is an obstacle.
    """
    sd = row["sides"][side]
    old_box, old_iv, faces = sd.get("box_cm"), sd.get("route_interval_cm"), sd.get("route_faces_cm")
    if not old_box or not new_box or not old_iv or not faces:
        return {}, ["P04_CLEARANCE_UNMEASURED %s %s" % (row["label"], side)]
    front = float(old_box["min"][0]) - float(new_box["min"][0])
    back = float(new_box["max"][0]) - float(old_box["max"][0])
    old_x_span = float(old_box["max"][0]) - float(old_box["min"][0])
    require(abs(old_x_span) > 1e-6, "P04_OLD_BOX_ZERO_DEPTH %s %s" % (row["label"], side))
    route_per_x = (float(faces["back_s_cm"]) - float(faces["front_s_cm"])) / old_x_span
    new_front_s = float(faces["front_s_cm"]) + (float(new_box["min"][0]) - float(old_box["min"][0])) * route_per_x
    new_back_s = float(faces["back_s_cm"]) + (float(new_box["max"][0]) - float(old_box["max"][0])) * route_per_x
    old_face_iv = sorted((float(faces["front_s_cm"]), float(faces["back_s_cm"])))
    new_face_iv = sorted((new_front_s, new_back_s))
    proposed = [new_face_iv[0] - (old_face_iv[0] - float(old_iv[0])),
                new_face_iv[1] + (float(old_iv[1]) - old_face_iv[1])]
    obstacles = []
    rows = {int(r["ordinal"]): r for r in dry["rows"]}
    for o in (int(row["ordinal"]) - 1, int(row["ordinal"]) + 1):
        nr = rows.get(o)
        if nr is None:
            continue
        for ns in row_sides(nr):
            iv = nr["sides"][ns].get("route_interval_cm")
            if iv:
                obstacles.append({"kind": "panel", "row": nr["label"], "side": ns, "interval_cm": iv})
        for prop in nr.get("prop_route_intervals", []):
            if prop.get("interval_cm"):
                obstacles.append({"kind": "prop", "row": nr["label"], "label": prop.get("label"),
                                  "interval_cm": prop["interval_cm"]})
    bad = []
    if front > P04_FRONT_GROWTH_MAX_CM + 1e-6:
        bad.append("P04_FRONT_GROWTH_OVER %.3f cm > %.1f" % (front, P04_FRONT_GROWTH_MAX_CM))
    if not obstacles:
        bad.append("P04_CLEARANCE_NO_NEIGHBOUR_OBSTACLES %s %s" % (row["label"], side))
    gaps = []
    for ob in obstacles:
        gap = _interval_gap(proposed, ob["interval_cm"])
        gaps.append(dict(ob, clearance_cm=round(gap, 3)))
        if gap < -1e-6:
            bad.append("P04_CLEARANCE_INTERSECTION %s %s with %s %s by %.3f cm" % (
                row["label"], side, ob["row"], ob.get("side") or ob.get("label"), -gap))
    return {"front_growth_cm": round(front, 3), "back_delta_cm": round(back, 3),
            "route_cm_per_local_x_cm": round(route_per_x, 6),
            "proposed_route_interval_cm": [round(x, 3) for x in proposed],
            "minimum_clearance_cm": min([g["clearance_cm"] for g in gaps] or [None]),
            "obstacles": gaps}, bad


def close_transform(actual, expected, tol=0.001):
    """swapkit/common.py:212-215 [prec], pure copy."""
    return all(abs(float(a) - float(b)) <= tol for key in ("location", "rotation", "scale")
               for a, b in zip(actual[key], expected[key]))


def panel_matches(actual, expected):
    """swapkit/common.py:218-228 [prec], pure copy (no unreal)."""
    ep = str(expected["facing_policy"])
    key = next((k for k in ("AUTO_BY_ROLE", "PRESERVE_ASSET", "ROTATE180_AROUND_UP") if k in ep), ep)
    return (actual["mesh"] == expected["mesh"] and actual["material_overrides"] == expected["material_overrides"] and
            close_transform(actual["local_transform"], expected["local_transform"]) and
            key in str(actual["facing_policy"]) and
            bool(actual["flip_image_horizontally"]) == bool(expected["flip_image_horizontally"]))


# =====================================================================================================================
# The plan
# =====================================================================================================================

def _allowed(design, side_fact, assigned, rows_by_ord, uses):
    if design["side"] != side_fact["side"]:
        return "BUILT_FOR_%s" % design["side"]
    if uses.get(design["mesh"], 0) >= MAX_USES:
        return "USED_%dx" % MAX_USES
    o, s = side_fact["ordinal"], side_fact["side"]
    for j in (o - 1, o + 1):
        if assigned.get((j, s)) == design["mesh"]:
            return "ADJACENT_SAME_SIDE"
        row = rows_by_ord.get(j)
        if row is not None and s in row.get("sides", {}) and row["sides"][s]["panel"]["mesh"] == design["mesh"]:
            return "ADJACENT_SAME_SIDE_STANDING"
    return ""


def _choose(designs, f, assigned, rows_by_ord, uses):
    options = []
    for d in designs:
        why = _allowed(d, f, assigned, rows_by_ord, uses)
        if not why:
            hd = abs(float(d.get("height_cm") or 0.0) - float(f.get("height_cm") or 0.0))
            options.append((uses.get(d["mesh"], 0), hd, d["owner"], d))
    if not options:
        return None
    options.sort(key=lambda t: (t[0], t[1], t[2]))
    return options[0][3]


def make_plan(dry, designs, protect, opts=None):
    """dry: a DRY measurement doc; designs: [{owner, side, mesh, height_cm, width_cm, passage, mount, imported,
    exists, zero_bounds, skin_png}] (make_swap_plan builds it); protect: rzswap_protect.json; opts: {end_rows,
    pair_mode, max_swaps, exclude: ["<label>|<side>"]}.  Returns the plan (refusals empty = appliable)."""
    opts = dict(opts or {})
    refusals = []
    require(dry.get("mode") == "DRY" and dry.get("status") == "PASS", "DRY_NOT_PASSING (%s)" % dry.get("status"))
    P = dry["passage"]
    require(P in SCORING_PASSAGES, "PASSAGE_UNSUPPORTED %s (scoring mode supports P01-P04; P06 = --remap)" % P)
    pair_mode = opts.get("pair_mode", "side")
    require(pair_mode in ("side", "row"), "PAIR_MODE %r" % pair_mode)
    selected_sides = tuple(opts.get("sides") or ("L", "R"))
    require(selected_sides and set(selected_sides) <= {"L", "R", "T"}, "SIDES %r" % (selected_sides,))
    require(pair_mode != "row" or set(selected_sides) == {"L", "R"}, "PAIR_MODE_ROW_NEEDS_LR")
    excl = set(opts.get("exclude") or [])
    facts = side_facts(dry, protect, opts)
    target_keys = set(opts.get("target_keys") or [])
    target_expected = dict(opts.get("target_expected_meshes") or {})
    fact_keys = {f["key"] for f in facts}
    for key in sorted(target_keys - fact_keys):
        refusals.append("TARGET_NOT_IN_FRESH_DRY %s" % key)
    for f in facts:
        f["protections_waived"] = []
        if f["side"] not in selected_sides:
            f["protected"].append("SIDE_NOT_SELECTED")
        if target_keys and f["key"] not in target_keys:
            f["protected"].append("NOT_IN_TARGET_FILTER")
        if f["key"] in target_keys:
            want = target_expected.get(f["key"])
            if want and want != f["mesh"]:
                f["protected"].append("TARGET_MESH_STALE expected %s live %s" % (want, f["mesh"]))
            # Gary's exact seven-side direction includes P03 Wing 001.  Only the broad end-row heuristic is waived;
            # pins, mechanisms, effects, records, authored transforms and missing measurements remain hard guards.
            keep = []
            for reason in f["protected"]:
                if reason.startswith("END_ROW"):
                    f["protections_waived"].append(reason)
                else:
                    keep.append(reason)
            f["protected"] = keep
        if f["side"] == "T" and "T" in selected_sides:
            # A Top-border plan is explicit placement review, not an accidental replacement of a legacy side card.
            keep = []
            for reason in f["protected"]:
                if reason.startswith("END_ROW"):
                    f["protections_waived"].append(reason)
                else:
                    keep.append(reason)
            f["protected"] = keep
        f["eligible"] = not f["protected"]
        if "%s|%s" % (f["label"], f["side"]) in excl:
            f["protected"].append("EXCLUDED_BY_REVIEW")
            f["eligible"] = False
    usable, unusable = [], []
    for d in designs:
        why = []
        if d.get("passage") != P and d.get("mount") != "top-border":
            why.append("OTHER_PASSAGE %s" % d.get("passage"))
        want_mount = "top-border" if d.get("side") == "T" else "wing"
        if d.get("mount", "wing") != want_mount:
            why.append("MOUNT %s (wanted %s)" % (d.get("mount"), want_mount))
        if d.get("side") not in selected_sides:
            why.append("SIDE_NOT_SELECTED %s" % d.get("side"))
        if not d.get("imported"):
            why.append("NOT_VERIFIED_IMPORTED (no rzimport VERIFY lists it)")
        if not d.get("exists"):
            why.append("NOT_IN_EDITOR (DRY)")
        if not d.get("zero_bounds") and d.get("side") != "T":
            why.append("NO_LIVE_BOUNDS (DRY)")
        if d.get("side") not in ("L", "R", "T"):
            why.append("SIDE %r" % d.get("side"))
        (unusable if why else usable).append(dict(d, unusable=why))
    usable.sort(key=lambda d: d["owner"])
    rows_by_ord = {r["ordinal"]: r for r in dry["rows"]}
    uses = {}
    for r in dry["rows"]:                      # realism already standing counts toward the 2x limit
        for s in row_sides(r):
            m = r["sides"][s]["panel"]["mesh"]
            if m and REALISM_ROOT in m:
                uses[m] = uses.get(m, 0) + 1
    assigned, swaps = {}, []
    order = sorted([f for f in facts if f["eligible"]], key=lambda f: (-f["score"], f["pass_s"], f["side"]))
    max_swaps = opts.get("max_swaps")
    by_key = {f["key"]: f for f in facts}

    def take(f, d):
        assigned[(f["ordinal"], f["side"])] = d["mesh"]
        uses[d["mesh"]] = uses.get(d["mesh"], 0) + 1
        row = rows_by_ord[f["ordinal"]]
        sd = row["sides"][f["side"]]
        if f["side"] == "T":
            new_box = (dry.get("candidates", {}).get(d["mesh"]) or {}).get("box_cm")
            planned = planned_top_panel(d["mesh"], new_box, sd.get("placement_anchor"))
            y = planned["local_transform"]["location"][1]
            new_inner, old_inner, outer_shift = None, None, 0.0
        else:
            y = inner_edge_y(f["side"], sd["old_bounds"], d["zero_bounds"])
            new = {"min_y_cm": d["zero_bounds"]["min_y_cm"] + y, "max_y_cm": d["zero_bounds"]["max_y_cm"] + y}
            k = "max_y_cm" if f["side"] == "L" else "min_y_cm"
            o = "min_y_cm" if f["side"] == "L" else "max_y_cm"
            if abs(new[k] - sd["old_bounds"][k]) > PLACE_TOL_CM:
                refusals.append("INNER_EDGE_PLAN_FAIL %s %s" % (f["label"], f["side"]))
            outer_shift = (new[o] - sd["old_bounds"][o]) * (1.0 if f["side"] == "L" else -1.0)
            planned, old_inner, new_inner = planned_panel(d["mesh"], y), sd["old_bounds"][k], new[k]
        geometry = None
        if P == "P04" and f["side"] in ("L", "R"):
            geometry, gbad = p04_clearance(dry, row, f["side"], (dry.get("candidates", {}).get(d["mesh"]) or {}).get("box_cm"))
            refusals.extend("%s %s" % (reason, f["key"]) for reason in gbad)
        swaps.append({"key": f["key"], "cue_guid": f["cue_guid"], "label": f["label"], "ordinal": f["ordinal"],
                      "side": f["side"], "pass_s": f["pass_s"], "score": f["score"], "class": f["class"],
                      "family": f["family"], "family_rows": f["family_rows"],
                      "adjacent_same_family": f["adjacent_same_family"],
                      "old_panel": sd["panel"], "old_height_cm": f["height_cm"], "old_thickness_cm": f["thickness_cm"],
                      "new_owner": d["owner"], "new_mesh": d["mesh"], "new_height_cm": d.get("height_cm"),
                      "new_width_cm": d.get("width_cm"), "new_skin_png": d.get("skin_png"),
                      "planned_panel": planned, "old_inner_cm": old_inner,
                      "new_inner_cm": new_inner, "outer_edge_onstage_shift_cm": round(outer_shift, 3),
                      "geometry": geometry, "protections_waived": list(f["protections_waived"])})

    if pair_mode == "side":
        for f in order:
            if max_swaps is not None and len(swaps) >= int(max_swaps):
                break
            d = _choose(usable, f, assigned, rows_by_ord, uses)
            if d is not None:
                take(f, d)
    else:
        rows_scored = {}
        for f in order:
            rows_scored.setdefault(f["cue_guid"], []).append(f)
        pairs = [v for v in rows_scored.values() if len(v) == 2]
        pairs.sort(key=lambda v: (-(v[0]["score"] + v[1]["score"]), v[0]["pass_s"]))
        for v in pairs:
            if max_swaps is not None and len(swaps) + 2 > int(max_swaps):
                break
            fl, fr = sorted(v, key=lambda f: f["side"])
            dl = _choose(usable, fl, assigned, rows_by_ord, uses)
            if dl is None:
                continue
            assigned[(fl["ordinal"], "L")] = dl["mesh"]
            uses[dl["mesh"]] = uses.get(dl["mesh"], 0) + 1
            dr = _choose(usable, fr, assigned, rows_by_ord, uses)
            del assigned[(fl["ordinal"], "L")]
            uses[dl["mesh"]] -= 1
            if dr is None:
                continue
            take(fl, dl)
            take(fr, dr)
    swaps.sort(key=lambda s: (s["ordinal"], s["side"]))
    swapped_rows = {}
    for s in swaps:
        swapped_rows.setdefault(s["cue_guid"], []).append(s["side"])
    mixed = sorted(rows_by_ord[by_key[g + "|L"]["ordinal"]]["label"] for g, sides in swapped_rows.items()
                   if set(sides) < {"L", "R"} and any(x in sides for x in ("L", "R")) and g + "|L" in by_key)
    flags = []
    if mixed and P == "P02":
        flags.append("MIXED_PAIR_ROWS %s: P02's matched-pair rule (P02_LAYOUT_DRAFT_v2.json rules[0], Gary 2 Oct) -- "
                     "Gary to accept, or re-plan with pair_mode 'row'" % mixed)
    narrower = [s["label"] + " " + s["side"] for s in swaps if s["outer_edge_onstage_shift_cm"] > 1.0]
    if narrower:
        flags.append("NARROWER_THAN_OLD (outer edge moves onstage, a gap opens behind it): %s" % narrower)
    taller = [s["label"] + " " + s["side"] for s in swaps
              if s.get("new_height_cm") and s.get("old_height_cm") and float(s["new_height_cm"]) > float(s["old_height_cm"]) + 50]
    if taller:
        flags.append("TALLER_THAN_OLD by > 50 cm (check Top borders / masking): %s" % taller)
    if target_keys:
        got = {s["key"] for s in swaps}
        if got != target_keys:
            refusals.append("TARGET_SET_NOT_EXACT missing=%s unexpected=%s" % (sorted(target_keys - got), sorted(got - target_keys)))
        waived = sorted({p.split(" ", 1)[0] for s in swaps for p in s.get("protections_waived", [])})
        if waived:
            flags.append("TARGET_FILTER_PROTECTIONS_WAIVED %s (exact user-directed target set; all other guards remain)" % waived)
    if selected_sides == ("T",):
        flags.append("TOP_BORDER_PLACEMENT canonical identity rotation/scale; centred on existing Top centre Y; upper "
                     "edge held at existing Top local Z (the old Top rotation is measured, not preserved)")
    if P == "P04":
        gs = [s["geometry"] for s in swaps if s.get("geometry")]
        clearances = [g["minimum_clearance_cm"] for g in gs if g.get("minimum_clearance_cm") is not None]
        if clearances:
            flags.append("P04_CLEARANCE_GATE front growth <= %.1f cm; candidate route interval tested against every "
                         "materialized panel and measured PROP bounds on adjacent DRY rows; minimum %.3f cm" % (
                             P04_FRONT_GROWTH_MAX_CM, min(clearances)))
    for m, c in uses.items():
        if c > MAX_USES:
            refusals.append("USES_OVER_%d %s x%d" % (MAX_USES, m, c))
    for s in swaps:
        if by_key[s["key"]]["protected"]:
            refusals.append("PROTECTED_SIDE_IN_PLAN %s" % s["key"])
    if not swaps:
        refusals.append("NO_SWAPS (no eligible side x usable design)")
    inputs = {"passage": P, "dry_run_id": dry["run_id"], "dry_state_hash": state_hash(dry),
              "swaps": [[s["key"], s["new_mesh"], s["planned_panel"]] for s in swaps], "opts": opts}
    h = sha(inputs)
    plan = {"mark": MARK, "passage": P, "passage_guid": dry["passage_guid"], "dry_run_id": dry["run_id"],
            "dry_state_hash": inputs["dry_state_hash"], "opts": opts, "pair_mode": pair_mode, "sides": list(selected_sides),
            "scoring": {"V2_card": SCORE_V2, "per_extra_family_row": SCORE_REPEAT, "adjacent_same_family": SCORE_ADJ,
                        "max_uses_per_design": MAX_USES, "tie_break": "pass time, then L before R"},
            "swaps": swaps, "facts": facts, "designs_usable": [d["owner"] for d in usable],
            "designs_unusable": {d["owner"]: d["unusable"] for d in unusable},
            "design_uses": {m: c for m, c in sorted(uses.items())}, "flags": flags, "refusals": refusals,
            "inputs_hash": h, "hash8": h[:8]}
    plan["confirm"] = confirm_for("APPLY", P, plan)
    plan["gates_ok"] = not refusals
    return plan


# =====================================================================================================================
# REMAP mode (7 Oct): deterministic 1:1 mesh replacement, no scoring
# =====================================================================================================================
# A remap {old mesh path: new mesh path} swaps EVERY side of the passage whose panel currently shows an old mesh to its
# new mesh: same side, same placement rule (planned_panel + inner_edge_y, i.e. the slot-D inner edge in the Unreal
# frame), nothing else.  The scoring-mode protections (end rows, Master pins, special mechanisms, EFFECT sides, realism
# already standing, MAX_USES) are WAIVED -- a 1:1 rebuild of the same design keeps every one of those decisions -- and
# listed per swap as "scoring_protections_waived".  What still REFUSES (the swap would change more than the mesh, or
# could not be verified): disabled row, old local transform not plain, old panel not the canonical planned panel
# (MaterialOverrides / FacingPolicy / flip), no old bounds / no world-edge baseline, an attachment naming the old mesh,
# a protect-record side or family, a new mesh not verified-imported / not live / built for the other side, an old
# mesh standing nowhere, and the geometry gates below.  Mechanisms are never written by this tool (WRITTEN_PANEL_FIELDS)
# and rzswap.py asserts every cue's WingPair.Mechanism + LocalOverrideMask text unchanged (mechanism_drift).
# DEPTH: instead of the swapkit tk_core depth gate, a declared FRONT-growth allowance: the new box may extend further
# toward -X (the front/art face, FRONT_X = -15 per rzimport_core.py:99 / edge_rollout_core.py:50 [prec]) by at most
# REMAP_FRONT_GROWTH_MAX_CM (Gary approved more flaps on P06, 7 Oct; the 12-flap v3 rebuilds grow 4.9-5.05 cm,
# P06_V3_VS_V2.json [meas]); the back face (+X) must not move and height (Z) must not change.

REMAP_FRONT_GROWTH_MAX_CM = 6.0
REMAP_BACK_TOL_CM = 0.5
REMAP_Z_TOL_CM = 1.5            # rzimport BOUNDS_TOL_CM [prec]
REMAP_WIDTH_TOL_CM = 1.5
REMAP_Y_SHIFT_FLAG_CM = 0.5
_SIDE_SUFFIX = re.compile(r"_([LR])(_t5[pij])?$")


def built_side(mesh):
    m = _SIDE_SUFFIX.search(mesh_name(mesh) or "")
    return m.group(1) if m else None


def load_remap(doc):
    """{"remap": {old: new}} or a flat {old: new}.  Returns (remap, refusals).  1:1, no chains, /Game paths."""
    raw = doc.get("remap", doc) if isinstance(doc, dict) else None
    ref = []
    if not isinstance(raw, dict) or not raw:
        return {}, ["REMAP_EMPTY_OR_NOT_A_MAPPING"]
    out = {}
    for old, new in sorted(raw.items()):
        if not isinstance(old, str) or not isinstance(new, str) or not old.startswith("/Game/") or not new.startswith("/Game/"):
            ref.append("REMAP_ENTRY_NOT_GAME_PATHS %r -> %r" % (old, new))
            continue
        if "." in old.rsplit("/", 1)[-1] or "." in new.rsplit("/", 1)[-1]:
            ref.append("REMAP_ENTRY_HAS_OBJECT_SUFFIX %s (package paths only)" % old)
            continue
        if old == new:
            ref.append("REMAP_IDENTITY %s" % old)
            continue
        out[old] = new
    vals = list(out.values())
    if len(vals) != len(set(vals)):
        ref.append("REMAP_NOT_ONE_TO_ONE (two old meshes map to one new mesh)")
    chain = sorted(set(out) & set(vals))
    if chain:
        ref.append("REMAP_CHAINED %s (a new mesh is also an old one)" % chain[:3])
    return out, ref


def remap_geometry(side, old_box, new_box):
    """Pure.  Boxes in the static-mesh frame {min:[x,y,z], max:[x,y,z]} (cm).  Returns (facts, refusal_reasons)."""
    if not old_box or not new_box:
        return {}, ["REMAP_NO_BOX (old %s, new %s)" % (bool(old_box), bool(new_box))]
    f = {"front_growth_cm": round(float(old_box["min"][0]) - float(new_box["min"][0]), 3),
         "back_delta_cm": round(float(new_box["max"][0]) - float(old_box["max"][0]), 3),
         "z_delta_cm": [round(float(new_box["min"][2]) - float(old_box["min"][2]), 3),
                        round(float(new_box["max"][2]) - float(old_box["max"][2]), 3)],
         "width_delta_cm": round((float(new_box["max"][1]) - float(new_box["min"][1])) -
                                 (float(old_box["max"][1]) - float(old_box["min"][1])), 3)}
    bad = []
    if f["front_growth_cm"] > REMAP_FRONT_GROWTH_MAX_CM + 1e-6:
        bad.append("REMAP_DEPTH_GROWTH_OVER %.2f cm > %.1f (front face)" % (f["front_growth_cm"], REMAP_FRONT_GROWTH_MAX_CM))
    if abs(f["back_delta_cm"]) > REMAP_BACK_TOL_CM:
        bad.append("REMAP_BACK_FACE_MOVED %.2f cm (growth must be on the front/art side only)" % f["back_delta_cm"])
    if max(abs(z) for z in f["z_delta_cm"]) > REMAP_Z_TOL_CM:
        bad.append("REMAP_HEIGHT_CHANGED %s cm" % f["z_delta_cm"])
    return f, bad


def mechanism_fields(tc, cue_text):
    """The mechanism-owned text of one cue: [WingPair.Mechanism, WingPair.LocalOverrideMask] (the two fields topple
    writes, topple_core.cue_text_outside_mechanism [prec]).  None for a cue text without WingPair."""
    wp = tc.get_field(cue_text, "WingPair")
    if wp is None:
        return None
    return [tc.get_field(wp, "Mechanism"), tc.get_field(wp, "LocalOverrideMask")]


def mechanism_drift(tc, before, after):
    """Every cue's mechanism text identical before/after (the swap must never touch a mechanism)."""
    if len(before) != len(after):
        return ["CUE_COUNT_CHANGED %d -> %d" % (len(before), len(after))]
    return ["MECHANISM_CHANGED index %d" % i for i, (a, b) in enumerate(zip(before, after))
            if mechanism_fields(tc, a) != mechanism_fields(tc, b)]


def make_remap_plan(dry, remap_doc, designs, protect, opts=None):
    """REMAP plan.  dry: a DRY doc (rows[].sides[].box_cm + candidates[].box_cm/zero_bounds); remap_doc: see load_remap;
    designs: as make_plan (imported / exists / zero_bounds per new mesh); protect: rzswap_protect.json.  Returns the plan
    (same swap schema as make_plan, mode "REMAP"; refusals empty = appliable)."""
    opts = dict(opts or {})
    require(dry.get("mode") == "DRY" and dry.get("status") == "PASS", "DRY_NOT_PASSING (%s)" % dry.get("status"))
    P = dry["passage"]
    require(P in PASSAGES, "PASSAGE_UNSUPPORTED %s" % P)
    for k in ("pair_mode", "max_swaps", "exclude"):
        require(not opts.get(k) or (k == "pair_mode" and opts[k] == "side"),
                "REMAP_OPTION_NOT_SUPPORTED %s (a remap swaps every standing old mesh; edit the remap instead)" % k)
    remap, refusals = load_remap(remap_doc)
    flags = []
    facts = side_facts(dry, protect, {"end_rows": 1})
    by_key = {f["key"]: f for f in facts}
    by_design = {d["mesh"]: d for d in designs}
    cands = dry.get("candidates") or {}
    standing = {}
    swaps = []
    WAIVABLE = ("END_ROW", "MASTER_PIN", "SPECIAL_", "EFFECT_ATTACHMENT", "REALISM_ALREADY", "IND_3D",
                "LEGACY_THICK_OR_UNMEASURED")
    for r in dry["rows"]:
        for s in ("L", "R"):
            sd = r["sides"][s]
            old = sd["panel"]["mesh"]
            if old not in remap:
                continue
            new = remap[old]
            key = "%s|%s" % (r["cue_guid"], s)
            standing[old] = standing.get(old, 0) + 1
            tag = "%s %s" % (r["label"], s)
            why = []
            if not r["enabled"]:
                why.append("REMAP_ROW_DISABLED")
            if built_side(old) != s:
                why.append("REMAP_OLD_BUILT_FOR_%s" % built_side(old))
            if built_side(new) != s:
                why.append("REMAP_NEW_BUILT_FOR_%s" % built_side(new))
            pl = sd["panel"]
            if not plain_transform(pl["local_transform"]):
                why.append("OLD_LOCAL_TRANSFORM_NOT_PLAIN %s" % pl["local_transform"])
            if pl.get("material_overrides"):
                why.append("REMAP_OLD_HAS_MATERIAL_OVERRIDES (the planned panel writes none)")
            if "PRESERVE_ASSET" not in str(pl.get("facing_policy")) or bool(pl.get("flip_image_horizontally")):
                why.append("REMAP_OLD_PANEL_NOT_CANONICAL facing %s flip %s" % (pl.get("facing_policy"),
                                                                              pl.get("flip_image_horizontally")))
            if not sd.get("old_bounds"):
                why.append("NO_OLD_BOUNDS")
            if not sd.get("edge_baseline"):
                why.append("NO_WORLD_EDGE_BASELINE (not materialized?)")
            if sd.get("attachment_refs_mesh"):
                why.append("REMAP_ATTACHMENT_NAMES_OLD_MESH")
            f = by_key[key]
            why += [p for p in f["protected"] if p.startswith(("RECORD_KEEP", "RECORD_FAMILY", "PROTECT_RECORD_STALE"))]
            d = by_design.get(new)
            if d is None:
                why.append("REMAP_NEW_NOT_A_DESIGN %s (not in the DRY's manifests for %s)" % (new, P))
            else:
                if not d.get("imported"):
                    why.append("NOT_VERIFIED_IMPORTED %s" % new)
                if not d.get("exists") or not d.get("zero_bounds"):
                    why.append("NOT_IN_EDITOR_OR_NO_LIVE_BOUNDS (DRY) %s" % new)
                if d.get("mount", "wing") != "wing" or d.get("passage") != P:
                    why.append("REMAP_NEW_MOUNT_OR_PASSAGE %s %s" % (d.get("mount"), d.get("passage")))
            geom, gbad = remap_geometry(s, sd.get("box_cm"), (cands.get(new) or {}).get("box_cm"))
            why += gbad
            if why:
                refusals += ["%s %s" % (w, tag) for w in why]
                continue
            y = inner_edge_y(s, sd["old_bounds"], d["zero_bounds"])
            k_in = "max_y_cm" if s == "L" else "min_y_cm"
            k_out = "min_y_cm" if s == "L" else "max_y_cm"
            nb = {"min_y_cm": d["zero_bounds"]["min_y_cm"] + y, "max_y_cm": d["zero_bounds"]["max_y_cm"] + y}
            if abs(nb[k_in] - sd["old_bounds"][k_in]) > PLACE_TOL_CM:
                refusals.append("INNER_EDGE_PLAN_FAIL %s" % tag)
            y_shift = y - float(pl["local_transform"]["location"][1])
            swaps.append({"key": key, "cue_guid": r["cue_guid"], "label": r["label"], "ordinal": r["ordinal"], "side": s,
                          "pass_s": r.get("pass_s"), "score": 0, "class": f["class"], "family": f["family"],
                          "family_rows": f["family_rows"], "adjacent_same_family": f["adjacent_same_family"],
                          "old_panel": pl, "old_height_cm": sd.get("height_cm"), "old_thickness_cm": sd.get("thickness_cm"),
                          "new_owner": d.get("owner"), "new_mesh": new, "new_height_cm": d.get("height_cm"),
                          "new_width_cm": d.get("width_cm"), "new_skin_png": d.get("skin_png"),
                          "planned_panel": planned_panel(new, y), "old_inner_cm": sd["old_bounds"][k_in],
                          "new_inner_cm": nb[k_in], "local_y_shift_cm": round(y_shift, 4),
                          "outer_edge_onstage_shift_cm": round((nb[k_out] - sd["old_bounds"][k_out]) * (1.0 if s == "L" else -1.0), 3),
                          "geometry": geom, "mechanism_at_dry": r["mechanism"],
                          "scoring_protections_waived": [p for p in f["protected"] if p.startswith(WAIVABLE)]})
    for old in sorted(set(remap) - set(standing)):
        refusals.append("REMAP_OLD_NOT_STANDING %s (no side of %s shows it; fix the remap)" % (old, P))
    swaps.sort(key=lambda x: (x["ordinal"], x["side"]))
    if not swaps:
        refusals.append("NO_SWAPS (no side shows a remapped mesh)")
    growth = [x["geometry"]["front_growth_cm"] for x in swaps]
    if growth:
        flags.append("DEPTH_GROWTH_FRONT declared: %d sides grow %.2f..%.2f cm toward the front/art face (allowed <= %.1f "
                     "cm, Gary approved more flaps on %s 7 Oct; replaces the swapkit tk_core depth gate); back face moved "
                     "<= %.2f cm" % (len(swaps), min(growth), max(growth), REMAP_FRONT_GROWTH_MAX_CM, P,
                                     max(abs(x["geometry"]["back_delta_cm"]) for x in swaps)))
    shifted = ["%s %s %.3f" % (x["label"], x["side"], x["local_y_shift_cm"]) for x in swaps
               if abs(x["local_y_shift_cm"]) > REMAP_Y_SHIFT_FLAG_CM]
    if shifted:
        flags.append("LOCAL_Y_SHIFT > %.1f cm (new Y extents differ from old): %s" % (REMAP_Y_SHIFT_FLAG_CM, shifted))
    wide = ["%s %s %.2f" % (x["label"], x["side"], x["geometry"]["width_delta_cm"]) for x in swaps
            if abs(x["geometry"]["width_delta_cm"]) > REMAP_WIDTH_TOL_CM]
    if wide:
        flags.append("WIDTH_CHANGED (outer edge moves; inner edge held): %s" % wide)
    waived = sorted({p.split(" ")[0] for x in swaps for p in x["scoring_protections_waived"]})
    if waived:
        flags.append("SCORING_PROTECTIONS_WAIVED for a 1:1 rebuild (recorded per swap): %s" % waived)
    mech_rows = sorted({x["label"] for x in swaps if special_mechanism(x["mechanism_at_dry"])})
    if mech_rows:
        flags.append("MECHANISM_ROWS (not written; rzswap.py asserts every cue's mechanism text unchanged): %s" % mech_rows)
    inputs = {"passage": P, "mode": "REMAP", "dry_run_id": dry["run_id"], "dry_state_hash": state_hash(dry),
              "remap": remap, "swaps": [[x["key"], x["new_mesh"], x["planned_panel"]] for x in swaps], "opts": opts}
    h = sha(inputs)
    plan = {"mark": MARK, "mode": "REMAP", "passage": P, "passage_guid": dry["passage_guid"], "dry_run_id": dry["run_id"],
            "dry_state_hash": inputs["dry_state_hash"], "opts": opts, "pair_mode": "remap", "remap": remap,
            "remap_standing": standing,
            "limits": {"front_growth_max_cm": REMAP_FRONT_GROWTH_MAX_CM, "back_tol_cm": REMAP_BACK_TOL_CM,
                       "z_tol_cm": REMAP_Z_TOL_CM, "place_tol_cm": PLACE_TOL_CM},
            "swaps": swaps, "facts": facts, "designs_usable": sorted(d["owner"] for d in designs if d["mesh"] in remap.values()),
            "designs_unusable": {}, "design_uses": {}, "flags": flags, "refusals": refusals,
            "mechanisms_at_dry": {r["cue_guid"]: r["mechanism"] for r in dry["rows"]},
            "inputs_hash": h, "hash8": h[:8]}
    plan["confirm"] = confirm_for("APPLY", P, plan)
    plan["gates_ok"] = not refusals
    return plan


# =====================================================================================================================
# Args / tokens
# =====================================================================================================================

def confirm_for(mode, passage, plan=None, originals=None):
    if mode == "DRY":
        return "DRY RZSWAP %s" % passage
    if mode == "APPLY":
        require(plan is not None, "APPLY_NEEDS_PLAN")
        return "APPLY RZSWAP %s #%s" % (passage, plan["hash8"])
    if mode == "REVERT":
        require(originals is not None, "REVERT_NEEDS_ORIGINALS")
        return "REVERT RZSWAP %s %s" % (passage, originals["run_id"])
    raise PlanError("MODE_INVALID %r" % (mode,))


def validate_args(args, plan=None, originals=None):
    mode = str(args.get("mode") or "").upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE_INVALID %r" % (mode,))
    P = str(args.get("passage") or "")
    require(P in PASSAGES, "PASSAGE_INVALID %r (%s)" % (P, " / ".join(sorted(PASSAGES))))
    if mode == "DRY":
        require(isinstance(args.get("manifests"), list), "MANIFESTS_MISSING (DRY measures the candidate meshes)")
    if mode == "APPLY":
        require(plan is not None and plan.get("passage") == P, "PLAN_PASSAGE_MISMATCH")
    want = confirm_for(mode, P, plan, originals)
    require(args.get("confirm") == want, "CONFIRM_MISMATCH %r want %r" % (args.get("confirm"), want))
    if mode == "APPLY":
        require(str(args.get("decided_by") or "").strip(), "NOT_DECIDED (decided_by empty; a Show + level write)")
        require(plan.get("gates_ok") is True, "PLAN_GATES_FAILED %s" % plan.get("refusals"))
    return mode, P


# =====================================================================================================================
# Read-back verdicts (pure; the struct-text parser is topple_core's [prec, measured live 7 Oct])
# =====================================================================================================================

def panel_text(tc, cue_text, side):
    return tc.get_field(tc.get_field(cue_text, "WingPair"), SIDE_FIELD[side])


def blank_sides(tc, cue_text, sides):
    wp = tc.get_field(cue_text, "WingPair")
    return tc.replace_field(cue_text, "WingPair", tc.without_fields(wp, [SIDE_FIELD[s] for s in sides]))


def unwritten_panel_text(tc, cue_text, side):
    return tc.without_fields(panel_text(tc, cue_text, side), WRITTEN_PANEL_FIELDS)


def panel_text_fields(tc, cue_text, side):
    return [k for k, _ in tc.fields(panel_text(tc, cue_text, side))]


def verify_texts(tc, before, after, targets):
    """targets: {show_index: [sides]}.  Every non-target cue byte-identical; each target cue identical once its target
    panels are blanked; each target panel identical outside the written fields (bCastShadow, bVisibleInMainPass,
    Collision ...).  In-script comparison (before/after inside ONE run) -- never against an older run's text (other
    streams edit lights on these cues)."""
    bad = []
    if len(before) != len(after):
        return ["CUE_COUNT_CHANGED %d -> %d" % (len(before), len(after))]
    for i, (a, b) in enumerate(zip(before, after)):
        sides = targets.get(i)
        if not sides:
            if a != b:
                bad.append("NON_TARGET_CUE_CHANGED index %d" % i)
            continue
        if blank_sides(tc, a, sides) != blank_sides(tc, b, sides):
            bad.append("TARGET_CUE_CHANGED_OUTSIDE_PANELS index %d" % i)
        for s in sides:
            if unwritten_panel_text(tc, a, s) != unwritten_panel_text(tc, b, s):
                bad.append("UNWRITTEN_PANEL_FIELD_CHANGED index %d %s" % (i, s))
    return bad


def edge_verdict(keys, swapped, before, after, tol=EDGE_TOL_CM, ctl_tol=CONTROL_TOL_CM, expect=None):
    """World placement probe.  L/R hold inner edge; T holds centre-Y and upper Z.  Non-targets are controls."""
    probe, bad = [], []
    for key in keys:
        b, a = before.get(key), after.get(key)
        if expect and key in expect:
            b = expect[key] if isinstance(expect[key], dict) else {"inner_cm": expect[key]}
        if not b or not a or "error" in a:
            bad.append("EDGE_MISSING %s" % key)
            continue
        ctl = key not in swapped
        limit = ctl_tol if ctl else tol
        if key.endswith("|T"):
            dz = float(a["top_cm"]) - float(b["top_cm"])
            dy = float(a["center_y_cm"]) - float(b["center_y_cm"])
            probe.append({"key": key, "control": ctl, "top_delta_cm": dz, "center_y_delta_cm": dy,
                          "inner_delta_cm": max(abs(dz), abs(dy)), "mesh": a.get("mesh")})
            if max(abs(dz), abs(dy)) > limit:
                bad.append("TOP_PLACEMENT_MOVED %s top %.3f cm centreY %.3f cm%s" % (
                    key, dz, dy, " (CONTROL)" if ctl else ""))
        else:
            d = float(a["inner_cm"]) - float(b["inner_cm"])
            probe.append({"key": key, "control": ctl, "inner_delta_cm": d, "mesh": a.get("mesh")})
            if abs(d) > limit:
                bad.append("INNER_EDGE_MOVED %s %.3f cm%s" % (key, d, " (CONTROL)" if ctl else ""))
    return probe, bad


def revert_drift(live_panels, written_panels):
    """REVERT compares ONLY the fields it wrote: each target side's live panel must still be the APPLY's panel."""
    return ["DRIFT_SINCE_APPLY %s (live %s)" % (k, live_panels.get(k, {}).get("mesh"))
            for k, want in sorted(written_panels.items()) if not live_panels.get(k) or not panel_matches(live_panels[k], want)]
