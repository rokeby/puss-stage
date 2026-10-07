"""P06 RELAYOUT CORE (7 Oct, offline-written, NEVER RUN IN UNREAL): pure logic, no `unreal` import.

Gary 7 Oct (his own words, relayed by the caller): "For p06, you are also replacing many wings there with v3 -- while
you're there, arrange to replace any fences needed so the fall can happen. Lengthen the gaps between wings while
reducing total passage bay number if needed." Conductor relay 7 Oct: "Swap fences out of the way"; keep 6 wings
slamming at ~37 s (dusk); change only P06 Show wing rows + the level's P06 Passage materialization; flag the rest.

Tiers per claim: [decl] read in source/header (cited), [prec] in-repo precedent call (cited; whether it ran),
[meas] read back from a live run record (cited), [inf] inferred (why).

WHAT A P06 LAYOUT IS (all [decl] InfinityStageCompiler.cpp unless noted)
  * A Passage is each maximal run of ENABLED WingPair cues (:200-205, :240-246); its settings row is found by an
    EXACT (FirstCueGuid, LastCueGuid) match (:81-89). A disabled cue INSIDE the run would split P06 into two compiled
    passages and ReconcilePassageSettings would mint a new settings row for the second half
    (InfinityStageShowAsset.cpp:126-181). So dropped rows are MOVED behind the last kept row and disabled there
    (the trailing-disable pattern of p01_shorten.py:631 [prec, NOT run]); the reorder itself follows
    p6_workflow.py:650-807 (set_editor_property("cues", list) + reconcile + LastCueGuid) [prec, ran 4 Oct FV3P6].
  * PassFrame_k = FirstPassFrame + sum(IntervalToNext of earlier rows), DistanceCm_k likewise with GapToNextCm
    (:254-288); SegmentEnd = LastPassFrame + TailFrames, Total = LastDistance + TailDistanceCm (:283-286); camera
    distance is piecewise-linear through those points (:385-410). So: keep the FIRST row, the LAST row, LeadIn and
    Tail untouched, give every kept row integer-cm gaps with IntervalToNext = gap * tick/speed (= 96 ticks/cm at
    250 cm/s, 24000 ticks/s), and the segment start/end, total distance, camera speed, music lock and every later
    segment are unchanged. FitMode is read only by the Cue Desk "Refit from music" button and the resize library
    (SInfinityStageCueDesk.cpp:5953-6030, InfinityStagePassageResizeLibrary.cpp:276), never by the compiler [decl:
    grep of Plugins/InfinityStage/Source]; it is left as is (a later "Refit from music" press would overwrite this
    layout -- flagged in the plan).
  * Mechanisms are not touched by this tool (STILL / keeper / chain belong to Saved/CodexFlatV3/topple).
"""
import hashlib
import json
import math

MARK = "FLATV3_P06RELAYOUT"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"              # topple_core.py:43 [prec, ran 7 Oct]
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SHOW_FILE_REL = "Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset"
UMAP_FILE_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
P06_GUID = "9BFC29C45D47911FF7836BB8537230D2"
TICKS_PER_CM = 96                     # 24000 ticks/s / 250 cm/s [meas topple_measurements.json law: 24000 ticks per 250 cm]
SPEED_CM_S = 250.0
KEEPER_GUID = "3F1CEC91DE4164DCF2F0698A885CBD14"   # P06 Wing 045 [meas topple_apply_TOPPLE-20261007-024333.json keeper]

# Gary 7 Oct cut list (relayed by the caller): these meshes may not stand on any kept row.
CUT_MESH_TOKENS = ("SM_FlatV3_P06_grand_pavilion_", "SM_FlatV3_P06_bronze_tree_", "SM_CeramicTotem_01_",
                   "SM_MutatedPeltFlora_01_L_v2")
IND_TOKEN = "SM_FlatV3_P02_IND_"      # 3D fence / shutter pieces, ~72-97 cm thick [meas topple_measurements.json]

# Realism import convention: rz_build_one.py:296 / p06_build_one_v2.py:306 target
# "/Game/Scenes/Wings/FlatV3/Realism/T5J/SM_FlatV3_<asset>" [decl]; T5P by the same pattern [inf].  These are exactly
# the folders the import kit creates (Saved/CodexFlatV3/p06import/p06_import_core.MESH_FOLDERS); make_plan simulates
# existence from that kit's plan and the harness asserts every DESIGNS path equals a kit destination.
DEFAULT_MESH_ROOTS = {"t5p": "/Game/Scenes/Wings/FlatV3/Realism/T5P", "t5j": "/Game/Scenes/Wings/FlatV3/Realism/T5J"}
DEFAULT_VARIANTS = ("t5p", "t5j")
KEEP = "KEEP"


class PlanError(Exception):
    pass


def require(cond, reason):
    if not cond:
        raise PlanError(reason)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# =====================================================================================================================
# Design table (P06 realism picks).  side = the side the art was BUILT for (never flipped).
# =====================================================================================================================

# v2 builds (7 Oct, run FV3RZ-P06-20261007-02) [meas] P06_IMPORT_MANIFEST_v2.json + P06_BUILD_REPORT_v2.json: 15 PASS,
# ONE variant each (the one the import kit imports); width = validation.json dimensions_m[1] of that FBX; bounds Z
# -100..1020, depth 19.85 cm, SOCKET_Hinge at the origin for all 15 [meas: p06_import_core.build_plan reads them].
# Pick 10's owner is P06_real_10_building_under_construct_R (slug changed from the v1 '..._construction').
# Unavailable (not built in v2): 4, 5, 29 (subject touches the image edge), 11, 12 (NOT_BUILDABLE_NO_STILE); they keep
# their pick number so a later rebuild resolves automatically IF it is built for the slot's side.
DESIGNS = {
    "1":  {"slug": "1_stone_building_under", "side": "L", "pick": "80 BambooScaffold_01_L", "width_cm": 639.4, "built": ["t5p"]},
    "2":  {"slug": "2_pink_silk_structure", "side": "R", "pick": "80 GauzeLattice_01_L (pink)", "width_cm": 396.9, "built": ["t5p"]},
    "3":  {"slug": "3_orange_sail_structure", "side": "L", "pick": "80 GauzeLattice_01_R (orange)", "width_cm": 393.7, "built": ["t5p"]},
    "4":  {"slug": "4_qfefqz_fwvsvb", "side": None, "pick": "80 CoveredBiomech_rococo", "width_cm": None, "built": []},
    "5":  {"slug": "5_draped_architectural_sculpture", "side": None, "pick": "80 CoveredBiomech_exposed", "width_cm": None, "built": []},
    "6":  {"slug": "6_rock_formation_sculpture", "side": "L", "pick": "80 SaltFormation_01_L_v2", "width_cm": 696.3, "built": ["t5p"]},
    "7":  {"slug": "7_draped_marble_statue", "side": "L", "pick": "80 CoveredPillar_01_L", "width_cm": 631.3, "built": ["t5p"]},
    "8":  {"slug": "8_rock_formation_sculpture", "side": "R", "pick": "80 SaltFormation_01_R", "width_cm": 643.4, "built": ["t5p"]},
    "9":  {"slug": "9_draped_column_statue", "side": "R", "pick": "80 CoveredPillar_01_R", "width_cm": 664.6, "built": ["t5p"]},
    "10": {"slug": "10_building_under_construct", "side": "R", "pick": "80 BambooScaffold_01_R", "width_cm": 689.6, "built": ["t5j"]},
    "11": {"slug": "11_metal_scaffolding_structure", "side": None, "pick": "80 SteelScaffold_01_L", "width_cm": None, "built": []},
    "12": {"slug": "12_metal_scaffolding_structure", "side": None, "pick": "80 SteelScaffold_01_R", "width_cm": None, "built": []},
    "25": {"slug": "25_concrete_wall_with", "side": "L", "pick": "81i plastered wall", "width_cm": 356.6, "built": ["t5p"]},
    "26": {"slug": "26_concrete_panel_wood", "side": "L", "pick": "81c partition", "width_cm": 326.3, "built": ["t5p"]},
    "29": {"slug": "29_metal_panel_with", "side": None, "pick": "81k/l falling panel veil", "width_cm": None, "built": []},
    "30": {"slug": "30_rusty_metal_door", "side": "L", "pick": "81k/l falling panel door", "width_cm": 428.0, "built": ["t5j"]},
    "33": {"slug": "33_burnt_furniture_ruin", "side": "L", "pick": "81m-o burnt flats+furniture", "width_cm": 671.6, "built": ["t5j"]},
    "35": {"slug": "35_metal_frame_door", "side": "L", "pick": "81d doorway plastic", "width_cm": 331.4, "built": ["t5p"]},
    "38": {"slug": "38_burnt_wood_concrete", "side": "L", "pick": "81m-o burnt partition", "width_cm": 365.1, "built": ["t5j"]},
    "39": {"slug": "39_burnt_metal_door", "side": "L", "pick": "81m-o burnt door", "width_cm": 428.0, "built": ["t5j"]},
}
REALISM_HEIGHT_BOUNDS_CM = 1120.0     # bounds Z -100..1020 [meas v2 validation.json bounds_m, all 15]
REALISM_HEIGHT_SOCKET_CM = 1020.0     # topple height = maxZ - hinge Z; hinge socket at Z 0 if Interchange keeps it [inf]
REALISM_THICK_CM = 19.85              # [meas v2 validation depth 0.1985 m, all 15]
VARIETY_MAX = 3                       # caller 7 Oct: no design more than 3x, never in adjacent rows on one side


def asset_name(design_key, side, variant):
    d = DESIGNS[design_key]
    return "SM_FlatV3_P06_real_%s_%s_%s" % (d["slug"], side, variant)


def asset_paths(design_key, side, roots=None, variants=DEFAULT_VARIANTS):
    """Candidate /Game paths for one design on one side, in preference order. Handedness: the side is part of the
    asset NAME, so an R-built design can never resolve for an L slot (no flip anywhere)."""
    roots = roots or DEFAULT_MESH_ROOTS
    out = []
    for v in variants:
        n = asset_name(design_key, side, v)
        out.append("%s/%s" % (roots[v].rstrip("/"), n))
    return out


def resolve_slot(spec, side, exists, roots=None, variants=DEFAULT_VARIANTS):
    """spec: list of candidates, each a design key or KEEP. Returns (mesh_path or KEEP, design_key or KEEP, tried)."""
    tried = []
    for cand in spec:
        if cand == KEEP:
            return KEEP, KEEP, tried
        d = DESIGNS.get(cand)
        require(d is not None, "UNKNOWN_DESIGN %s" % cand)
        if d["side"] is not None and d["side"] != side:
            tried.append("%s:BUILT_FOR_%s" % (cand, d["side"]))
            continue
        for p in asset_paths(cand, side, roots, variants):
            if exists(p):
                return p, cand, tried
            tried.append(p)
    return None, None, tried


# =====================================================================================================================
# THE LAYOUT (29 rows).  Each row names an EXISTING P06 cue (identity, attachments and mechanism travel with it).
# station_cm: route distance of the station.  L/R: candidate lists (first that resolves wins; KEEP = current panel).
# =====================================================================================================================

LAYOUT = [
    # --- A. daylight gallery (1-38 s): the v2 statues / sails / scaffolds.  V2 cards fill R where the R-built V3
    #        designs run out: only 2, 8, 9, 10 are R-built = 12 R sides at <= 3 each, and 8 of those are forced (the
    #        mouth, the last row and the 6 chain rows stand on cut designs on R).
    {"station_cm": 250,   "cue": "DFD138DA78440386500FEC8E57AE3BA9", "role": "mouth",   "L": ["7"],        "R": ["9"]},
    {"station_cm": 1050,  "cue": "C1CDC6C8BB4116B5D3BB67B4103FF047", "role": "gallery", "L": ["1"],        "R": ["10", KEEP]},
    {"station_cm": 1950,  "cue": "D92313E04C50AB918446E1A5C1A766D6", "role": "gallery", "L": ["3"],        "R": ["2"]},
    {"station_cm": 2950,  "cue": "0A53E28D7C44CCD4B5F79EA1FC64B0E7", "role": "gallery", "L": ["6", KEEP],  "R": ["8"]},
    {"station_cm": 4050,  "cue": "E9850E1D8D4473A298BEA0A87E7AC60A", "role": "fence",   "L": [KEEP],       "R": [KEEP]},
    {"station_cm": 5150,  "cue": "A9E0E66B074D5EA45E23BE93ADA0F8CE", "role": "gallery", "L": ["11", KEEP], "R": ["12", KEEP]},
    {"station_cm": 6250,  "cue": "ABFFBA7B47F22FE2F67C52A63EE441F7", "role": "gallery", "L": ["4", KEEP],  "R": [KEEP]},
    {"station_cm": 7350,  "cue": "735A7090BC4094A56E9818B65CD531B7", "role": "gallery", "L": ["1"],        "R": [KEEP]},
    {"station_cm": 8450,  "cue": "F060763E471ABBB50FE986831AFBAC59", "role": "gallery", "L": ["7"],        "R": ["9"]},
    {"station_cm": 9450,  "cue": "884761C04271AFF58AF47B8B8AE5CD64", "role": "approach", "L": ["3"],       "R": [KEEP]},
    # --- B. the chain: 6 thin V3 slabs on L at 5.0 m, falling away -- six DIFFERENT designs: partition, rusty door,
    #        plaster wall, doorway, burnt partition (or the veil 29 if it is ever rebuilt L), burnt door
    {"station_cm": 10450, "cue": "7B0D67932249C38B1F010C93D74A38F2", "role": "chain1",  "L": ["26"],       "R": ["8"]},
    {"station_cm": 10950, "cue": "84D6E0B0E64D490C8BAEC7955AED56C2", "role": "chain2",  "L": ["30"],       "R": ["2"]},
    {"station_cm": 11450, "cue": "008D989B20485276BC8D0493439D39EA", "role": "chain3",  "L": ["25"],       "R": ["10"]},
    {"station_cm": 11950, "cue": "2C9C4A30466204C2890815B6C777DACF", "role": "chain4",  "L": ["35"],       "R": ["8"]},
    {"station_cm": 12450, "cue": "AA62A3AC5C432FCBE3A672B23443FA6A", "role": "chain5",  "L": ["29", "38"], "R": ["2"]},
    {"station_cm": 12950, "cue": "6DB7C86FE7463FB8ED5143833DF28400", "role": "chain6",  "L": ["39"],       "R": ["10"]},
    # --- the brace: the construction fence the 6th slab slams into (kept IND FenceTarp pair, 13 m, 97 cm)
    {"station_cm": 13450, "cue": "1D2D86BCE74A910A13CC588B0D451795", "role": "brace",   "L": [KEEP],       "R": [KEEP]},
    # --- the keeper, untouched (still sliding, towards the back)
    {"station_cm": 13950, "cue": KEEPER_GUID,                         "role": "keeper",  "L": [KEEP],       "R": [KEEP]},
    # --- C. the dark (after ~52 s): burnt rooms on L; R = kept V2 cards.  The seven dark rows now name cues whose R
    #        card is a non-cut V2 (the old dark cues all stood on cut designs on R: bronze_tree / grand_pavilion /
    #        CeramicTotem), each with the light-attachment count of the cue it replaces, +-2 [meas
    #        Saved/CodexConductor/p06_rig_pattern_record.json after_cue_rows, written 6 Oct 22:39; the DRY re-reads
    #        the live attachments]: W008 19 -> W046 17, W019 16 -> W053 16, W027 0 -> W052 0, W021 16 -> W048 16,
    #        W023 15 -> OLD 23 15, W015 17 -> W044 17, W043 15 -> W049 15.
    {"station_cm": 15150, "cue": "4927CDF2454CE3EC567E4C8BBB58AFB0", "role": "dark",    "L": ["33"],       "R": [KEEP]},
    {"station_cm": 16350, "cue": "88A3B6EF6F43524F0A057A84271187B7", "role": "fence",   "L": [KEEP],       "R": [KEEP]},
    {"station_cm": 17550, "cue": "6C060F41144F94D9214DF3BF039C7E99", "role": "dark",    "L": ["39"],       "R": [KEEP]},
    {"station_cm": 18750, "cue": "11F403689E45D226B3298AAF16790170", "role": "dark",    "L": ["38"],       "R": [KEEP]},
    {"station_cm": 19950, "cue": "4AA16A12224559F4375C89AF372F0857", "role": "fence",   "L": [KEEP],       "R": [KEEP]},
    {"station_cm": 21150, "cue": "821E817A714533C8BFDB38B63581F33F", "role": "dark",    "L": ["33"],       "R": [KEEP]},
    {"station_cm": 22350, "cue": "CC3403E5418809B2A1D9328EFC64C048", "role": "dark",    "L": ["30"],       "R": [KEEP]},
    {"station_cm": 23550, "cue": "73AFD9FE4A43CBCDC34ED08FC4D4CA21", "role": "fence",   "L": [KEEP],       "R": [KEEP]},
    {"station_cm": 24750, "cue": "AF6EB4EB57431F88F4BFC0957DA0E395", "role": "dark",    "L": ["26"],       "R": [KEEP]},
    {"station_cm": 25950, "cue": "30450225EE4DB0B28CEF8FA67FD430D4", "role": "dark",    "L": ["33"],       "R": [KEEP]},
    {"station_cm": 27250, "cue": "07E24048F24647AA7D5992AB6A8A0770", "role": "last",    "L": ["39"],       "R": ["9"]},
]
CHAIN_ROLES = ("chain1", "chain2", "chain3", "chain4", "chain5", "chain6")


# =====================================================================================================================
# Plan from the live (or recorded) P06 rows
# =====================================================================================================================

def is_cut(mesh):
    return bool(mesh) and any(t in mesh for t in CUT_MESH_TOKENS)


def is_ind(mesh):
    return bool(mesh) and IND_TOKEN in mesh


def side_identity(side_doc):
    """What a viewer sees on one side: the V3 design key, or the kept card's mesh name (V2 card or IND piece)."""
    if side_doc.get("action") == "swap":
        return "V3:" + str(side_doc["design"])
    mesh = side_doc.get("mesh")
    return None if mesh is None else str(mesh).rsplit("/", 1)[-1].split(".", 1)[0]


def variety_counts(out_rows):
    counts = {}
    for r in out_rows:
        for side in ("L", "R"):
            ident = side_identity(r["sides"][side])
            if ident is not None:
                counts[ident] = counts.get(ident, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def variety_refusals(out_rows, limit=VARIETY_MAX):
    """Gate on the RESOLVED rows (so a fallback can never quietly break it): every identity (V3 design, kept V2
    card, IND piece) at most `limit` times in the passage, and never on the same side of two consecutive rows."""
    ref = ["VARIETY_OVER_%d %s x%d" % (limit, i, n) for i, n in sorted(variety_counts(out_rows).items()) if n > limit]
    for a, b in zip(out_rows[:-1], out_rows[1:]):
        for side in ("L", "R"):
            ia, ib = side_identity(a["sides"][side]), side_identity(b["sides"][side])
            if ia is not None and ia == ib:
                ref.append("VARIETY_ADJACENT %s rows %d/%d %s" % (side, a["new_ordinal"] + 1, b["new_ordinal"] + 1, ia))
    return ref


def old_law(rows, lead_frames, lead_cm, tail_frames, tail_cm):
    pts = [(0, 0.0)]
    f, d = int(lead_frames), float(lead_cm)
    for i, r in enumerate(rows):
        pts.append((f, d))
        if i < len(rows) - 1:
            f, d = f + int(r["interval_ticks"]), d + float(r["gap_cm"])
    pts.append((f + int(tail_frames), d + float(tail_cm)))
    return pts


def dist_at(pts, frame):
    for (f0, d0), (f1, d1) in zip(pts[:-1], pts[1:]):
        if frame <= f1:
            return d1 if f1 <= f0 else d0 + (d1 - d0) * (frame - f0) / float(f1 - f0)
    return pts[-1][1]


def build_plan(rows, settings, layout=LAYOUT, exists=lambda p: False, roots=None, variants=DEFAULT_VARIANTS,
               keeper_guid=KEEPER_GUID):
    """rows: the live P06 rows in compiled order, each {cue_guid, label, show_index, enabled, interval_ticks, gap_cm,
    L_mesh, R_mesh, text_outside_mechanism_sha}. settings: {lead_in_frames, lead_in_distance_cm, tail_frames,
    tail_distance_cm, first_cue_guid, last_cue_guid}. Returns the plan dict with "refusals" (empty = gates pass)."""
    ref = []
    by = {r["cue_guid"]: r for r in rows}
    order = [r["cue_guid"] for r in rows]
    require(len(set(order)) == len(order), "DUPLICATE_CUE_GUIDS_IN_P06")
    kept = [x["cue"] for x in layout]
    if len(set(kept)) != len(kept):
        ref.append("LAYOUT_REUSES_A_CUE")
    missing = [g for g in kept if g not in by]
    if missing:
        ref.append("LAYOUT_CUE_NOT_IN_P06 %s" % missing)
        return {"refusals": ref}
    if not all(r.get("enabled", True) for r in rows):
        ref.append("P06_HAS_DISABLED_ROWS (a disabled row inside P06 is impossible: it would split the run)")
    if [r["show_index"] for r in rows] != list(range(rows[0]["show_index"], rows[0]["show_index"] + len(rows))):
        ref.append("P06_NOT_CONTIGUOUS")
    # anchors
    if kept[0] != order[0] or kept[0] != settings["first_cue_guid"]:
        ref.append("FIRST_ROW_MUST_STAY (layout %s, live %s)" % (kept[0][:8], order[0][:8]))
    if kept[-1] != order[-1] or kept[-1] != settings["last_cue_guid"]:
        ref.append("LAST_ROW_MUST_STAY (layout %s, live %s)" % (kept[-1][:8], order[-1][:8]))
    stations = [int(x["station_cm"]) for x in layout]
    if any(float(x["station_cm"]) != int(x["station_cm"]) for x in layout):
        ref.append("STATIONS_MUST_BE_INTEGER_CM (integer ticks at 96 ticks/cm)")
    old = old_law(rows, settings["lead_in_frames"], settings["lead_in_distance_cm"], settings["tail_frames"],
                  settings["tail_distance_cm"])
    old_first_cm, old_last_cm = old[1][1], old[-2][1]
    old_first_f, old_last_f = old[1][0], old[-2][0]
    if abs(stations[0] - old_first_cm) > 1e-6 or abs(stations[-1] - old_last_cm) > 1e-3:
        ref.append("ENDPOINT_STATIONS_MOVED first %.3f/%.3f last %.3f/%.3f" % (stations[0], old_first_cm,
                                                                               stations[-1], old_last_cm))
    gaps = [b - a for a, b in zip(stations[:-1], stations[1:])]
    if any(g <= 0 for g in gaps):
        ref.append("STATIONS_NOT_INCREASING")
    ivals = [g * TICKS_PER_CM for g in gaps]
    if old_last_f - old_first_f != sum(ivals):
        ref.append("INTERVAL_SUM_CHANGES_DURATION old %d new %d ticks" % (old_last_f - old_first_f, sum(ivals)))
    new_pts = [(0, 0.0)]
    f = old_first_f
    pass_frames = []
    for i, s in enumerate(stations):
        pass_frames.append(f)
        new_pts.append((f, float(s)))
        if i < len(ivals):
            f += ivals[i]
    new_pts.append((old[-1][0], old[-1][1]))
    seg_end = old[-1][0]
    dev = max(abs(dist_at(new_pts, fr) - dist_at(old, fr)) for fr in range(0, seg_end + 1, 240))
    if dev > 0.5:
        ref.append("CAMERA_LAW_DEVIATES %.3f cm" % dev)
    # rows
    out_rows, cut_left, swaps = [], [], []
    for k, (x, iv, g) in enumerate(zip(layout, ivals + [None], gaps + [None])):
        live = by[x["cue"]]
        row = {"new_ordinal": k, "cue_guid": x["cue"], "label": live["label"], "role": x["role"],
               "old_ordinal": order.index(x["cue"]), "old_show_index": live["show_index"],
               "station_cm": stations[k], "pass_frame_rel": pass_frames[k], "pass_s": pass_frames[k] / 24000.0,
               "interval_ticks": iv, "gap_cm": g, "sides": {}}
        if x["cue"] == keeper_guid and (x["L"] != [KEEP] or x["R"] != [KEEP]):
            ref.append("KEEPER_MESH_CHANGE_REFUSED")
        for side in ("L", "R"):
            cur = live[side + "_mesh"]
            mesh, design, tried = resolve_slot(x[side], side, exists, roots, variants)
            if mesh is None:
                ref.append("NO_ASSET %s %s %s tried %s" % (live["label"], side, x[side], tried[:4]))
                row["sides"][side] = {"action": "UNRESOLVED", "spec": x[side], "tried": tried}
                continue
            if mesh == KEEP:
                if is_cut(cur):
                    cut_left.append("%s %s %s" % (live["label"], side, cur))
                row["sides"][side] = {"action": "keep", "mesh": cur, "spec": x[side], "fallback": bool(tried)}
            else:
                row["sides"][side] = {"action": "swap", "mesh": mesh, "design": design, "old_mesh": cur,
                                      "spec": x[side], "fallback_from": tried}
                swaps.append((x["cue"], side))
        out_rows.append(row)
    if cut_left:
        ref.append("CUT_DESIGN_STILL_STANDING %s" % cut_left)
    ref += variety_refusals(out_rows)
    # chain gates (layout-level; the topple DRY re-measures them live)
    chain = [r for r in out_rows if r["role"] in CHAIN_ROLES]
    if [r["role"] for r in chain] != list(CHAIN_ROLES):
        ref.append("CHAIN_ROWS_MISSING_OR_OUT_OF_ORDER")
    else:
        ks = [r["new_ordinal"] for r in chain]
        if ks != list(range(ks[0], ks[0] + 6)):
            ref.append("CHAIN_ROWS_NOT_CONSECUTIVE")
        for r in chain:
            m = r["sides"]["L"].get("mesh") or ""
            if r["sides"]["L"].get("action") != "swap" or is_ind(m):
                ref.append("CHAIN_SLAB_NOT_A_THIN_V3 %s %s" % (r["label"], m))
        nxt = out_rows[ks[-1] + 1] if ks[-1] + 1 < len(out_rows) else None
        if nxt is None or nxt["role"] != "brace":
            ref.append("NO_BRACE_AFTER_CHAIN")
    dropped = [g for g in order if g not in kept]
    for g in dropped:
        if g == keeper_guid:
            ref.append("KEEPER_DROPPED")
    new_order = kept + dropped
    plan = {"rows": out_rows, "dropped": [{"cue_guid": g, "label": by[g]["label"], "old_ordinal": order.index(g),
                                           "old_show_index": by[g]["show_index"], "L_mesh": by[g]["L_mesh"],
                                           "R_mesh": by[g]["R_mesh"]} for g in dropped],
            "new_order": new_order, "old_order": order, "count_old": len(order), "count_new": len(kept),
            "first_show_index": rows[0]["show_index"], "swaps": len(swaps),
            "settings_before": settings, "law_old_points": old, "law_new_points": new_pts,
            "camera_law_max_dev_cm": dev, "segment_end_rel": seg_end,
            "duration_s": seg_end / 24000.0, "refusals": ref, "variety_counts": variety_counts(out_rows)}
    plan["inputs"] = {"rows": [[r["cue_guid"], r["text_outside_mechanism_sha"]] for r in rows], "settings": settings,
                      "layout": layout, "resolved": [[r["cue_guid"], {s: r["sides"][s].get("mesh") for s in ("L", "R")}]
                                                    for r in out_rows]}
    plan["inputs_hash"] = sha(plan["inputs"])
    plan["confirm_token"] = "P06 %d->%d #%s" % (len(order), len(kept), plan["inputs_hash"][:8])
    return plan


def confirm_for(mode, plan=None, originals=None):
    if mode == "DRY":
        return "DRY P06RELAYOUT"
    if mode == "APPLY":
        require(plan is not None, "APPLY_NEEDS_DRY_PLAN")
        return "APPLY P06RELAYOUT " + plan["confirm_token"]
    if mode == "REVERT":
        require(originals is not None, "REVERT_NEEDS_ORIGINALS")
        return "REVERT P06RELAYOUT " + originals["run_id"]
    raise PlanError("MODE_INVALID %r" % (mode,))


def validate_args(args, plan=None, originals=None):
    mode = str(args.get("mode") or "").upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE_INVALID %r" % (mode,))
    want = confirm_for(mode, plan, originals)
    require(args.get("confirm") == want, "CONFIRM_MISMATCH %r want %r" % (args.get("confirm"), want))
    if mode == "APPLY":
        require(str(args.get("decided_by") or "").strip(), "NOT_DECIDED (decided_by empty; a Show + level write)")
        require(plan.get("gates_ok") is True, "PLAN_GATES_FAILED %s" % plan.get("refusals"))
        require(args.get("attachments_ack") == "DROPPED_ROWS_GO_DARK_KEPT_ROWS_MOVE",
                "ATTACHMENTS_NOT_ACKED (dropped rows' lights stop materializing; kept rows' lights move with them)")
        require(args.get("structure_ack") == "STRUCTURE_06_LEFT_STALE",
                "STRUCTURE_NOT_ACKED (Structure 06 is not re-materialized by this tool: its owner must)")
    return mode


# =====================================================================================================================
# Panel placement (slot-D inner_edge rule, Unreal frame) -- pure part
# =====================================================================================================================

def inner_edge_y(side, old_bounds, zero_bounds):
    """swapkit/dry.py:93-101 + lateral_geometry.inner_edge_local_y [prec, ran 6 Oct FV3D]: new local Y that puts the
    new mesh's inner edge exactly on the old panel's inner edge. side 'L' -> inner = max Y; 'R' -> inner = min Y
    (in the panel-local frame swapkit common.side_bounds returns)."""
    k = "max_y_cm" if side == "L" else "min_y_cm"
    return float(old_bounds[k]) - float(zero_bounds[k])


def planned_panel(mesh_path, y):
    """swapkit/common.py:433-438 [prec]: PRESERVE_ASSET, no flip (handedness as built), identity rotation/scale."""
    return {"mesh": mesh_path, "material_overrides": [],
            "local_transform": {"location": [0.0, float(y), 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            "facing_policy": "PRESERVE_ASSET", "flip_image_horizontally": False}


# =====================================================================================================================
# Synthetic topple measurement for the planned layout (offline window check)
# =====================================================================================================================

def synth_topple_rows(meas, plan, height_mode="socket"):
    """topple_core-shaped rows for the planned layout. Kept-panel geometry is copied from the live measurement and
    shifted by the station move; swapped V3 realism panels get: height 1020 (socket) or 1120 (bounds) cm [inf which
    one the live DRY reads: depends on Interchange keeping SOCKET_Hinge], thickness 19.85, hinge at the station
    (socket at the origin) [inf], inner edge = the old panel's inner edge (inner_edge rule), width from the build."""
    by = {r["cue_guid"]: r for r in meas["rows"]}
    tick = float(meas["tick"])
    out = []
    for r in plan["rows"]:
        src = by[r["cue_guid"]]
        shift = r["station_cm"] - src["station_cm"]
        sides = {}
        for side in ("L", "R"):
            s = dict(src["sides"][side])
            s.pop("curve_export", None)
            plan_side = r["sides"][side]
            if plan_side["action"] == "swap":
                d = DESIGNS[plan_side["design"]]
                inner = s["lateral_max_cm"] if side == "L" else s["lateral_min_cm"]
                w = float(d["width_cm"])
                s.update({"mesh": plan_side["mesh"], "materialized": True, "has_hinge_socket": True,
                          "height_cm": REALISM_HEIGHT_SOCKET_CM if height_mode == "socket" else REALISM_HEIGHT_BOUNDS_CM,
                          "thickness_cm": REALISM_THICK_CM, "width_cm": w, "hinge_route_cm": float(r["station_cm"]),
                          "lateral_min_cm": inner - w if side == "L" else inner,
                          "lateral_max_cm": inner if side == "L" else inner + w,
                          "axis_dot_tangent": 0.0, "upright": True, "external_curve": None})
            else:
                s["hinge_route_cm"] = float(s["hinge_route_cm"]) + shift
            sides[side] = s
        out.append({"ordinal": r["new_ordinal"], "show_index": plan["first_show_index"] + r["new_ordinal"],
                    "cue_guid": r["cue_guid"], "label": r["label"], "enabled": True, "has_top": src["has_top"],
                    "local_override_mask": src["local_override_mask"], "curve_at0": src["curve_at0"],
                    "mechanism_sha": src["mechanism_sha"], "mechanism": src["mechanism"],
                    "mechanism_export": src["mechanism_export"], "sides": sides,
                    "interval_ticks": r["interval_ticks"] or src["interval_ticks"], "gap_cm": r["gap_cm"] or src["gap_cm"],
                    "pass_frame": r["pass_frame_rel"], "station_cm": float(r["station_cm"])})
    law = {"points": [list(p) for p in plan["law_new_points"]], "segment_end": plan["segment_end_rel"],
           "stations": [[r["pass_frame_rel"], float(r["station_cm"])] for r in plan["rows"]],
           "total_cm": plan["law_new_points"][-1][1]}
    doc = dict(meas)
    doc.update({"rows": out, "law": law, "run_id": "SYNTH-RELAYOUT", "tick": tick})
    return doc
