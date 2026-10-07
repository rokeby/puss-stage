"""P06 REALISM v2 IMPORT KIT -- pure core (7 Oct, offline-written, NEVER RUN IN UNREAL). No `unreal` import.

What it imports: the 15 PASS wings of DerivedAssets/FlatV3/Realism_20261007/P06_backrooms/P06_IMPORT_MANIFEST_v2.json
(run FV3RZ-P06-20261007-02; picks 1 2 3 6 7 8 9 10 25 26 30 33 35 38 39), each = 1 mesh (LOD0+LOD1, sockets from the
sidecar) + 4 textures (SkinColor, SkinMask, SkinNormal, AgedPlywood_Stencil_Color) + 2 MIs (Front, Flap), slots
Front/Flap/Timber/Edge with Edge = M_Wing_CanvasEdge_Master_v3.  7 packages per wing, 105 in all, CREATE-ONLY.

Tiers per claim: [decl] read in source/header/config (cited), [prec] an in-repo tool made the same call and it RAN
(cited with its record), [meas] measured offline here (file hash / JSON / image read), [inf] inferred (why).

PRECEDENT FOLLOWED (the house import for fresh Flat V3 flats + skins + MIs):
  * Saved/CodexFlatV3/slot_a_import.py import_asset/verify_flat_general/create_instance/verify_instance/save_narrow,
    reused AS A LIBRARY by swapkit/p06_import.py (ran: swapkit_p06_import_FV3P06I-20261002-04.json status PASS, the
    P06 V3 flats) [prec].  Its pilot helpers phase1_import.py import_task/fbx_options/configure_texture/verify_texture
    [prec, same run].  The t5p HF import (swapkit/hf_workflow.py import_assets, hf_import_FV3HF-20261006-P06.json
    PASS) adds: sockets written from the sidecar even if Interchange created some, stray-asset diff of the
    destination folder (never-saved strays only), texture settings copied from a live reference texture [prec].
  * /Game layout: meshes follow the realism convention rz_build_one.py:296 / p06_build_one_v2.py:306
    "/Game/Scenes/Wings/FlatV3/Realism/T5J/SM_FlatV3_<asset>" [decl]; T5P by the same pattern (the HF suffix
    rz_hf.py:14) [inf: no T5P target string exists in the realism tools].  Textures/MIs use the slot_a naming
    (Textures/<owner>/..., Textures/Aged/<owner>/..., Materials/Instances/MI_FlatV3_<owner>_Front|Flap,
    swapkit/p06_import.py:121-131 [prec]) under the same Realism root.
  * MI parents: MI_Billboard_Front / MI_Billboard_Flap (v1) -- every wing's own skin_v3/<owner>_mi_params.json names
    them [meas], the live P06 V3 MIs were created on them (FV3P06I-20261002-04 instances.parent) [prec], and the
    Billboard v4 / wax reparent ran ONLY on two P04 designs (gloss4_apply_GLOSS4-APPLY-20261006-200726.json,
    gloss4_wax_apply_GLOSS4WAX-APPLY-20261006-223210.json targets = Passage04 MIs) [prec].  So v4 is NOT applied
    here; a later gloss4-style reparent can take these MIs.  The DRY re-reads the parent of a live P06 reference MI
    and refuses if it is not the configured parent [meas at DRY time].
  * Timber slot = M_Wing_CanvasEdge_Master (slot_a PARENTS [prec]; edge rollout never touches slot 2,
    edge_rollout_core.py:18 [decl]); Edge slot = M_Wing_CanvasEdge_Master_v3 (caller; the 6 Oct rollout put v3 on
    every thick5 P06 mesh, edge_rollout_plan.json Passage06 targets 9 + edge_rollout_verify_result.json PASS
    [prec]).  The DRY reads the reference P06 T5P mesh's slots 2/3 and refuses on a mismatch.
  * Aged textures: the six common aged PNGs are byte-identical (sha256) to the set FV3P06I-20261002-04 imported to
    /Game/Scenes/Wings/FlatV3/Passage06/Textures/Aged/Common (its common_hashes) [meas: compared here].  They are
    REUSED (slot_a destination_state 'verified_existing_saved' path [prec]), not duplicated (~84 MB of .uasset).
    No MI references them (slot_a sets only SkinColor/SkinMask/SkinNormal [prec]); the per-owner
    AgedPlywood_Stencil_Color is imported per wing exactly as slot_a does.
  * Texture profiles (pilot.configure_texture [prec]): SkinColor/AgedColor sRGB TC_Default; SkinMask TC_Masks sRGB
    off; SkinNormal TC_Normalmap sRGB off (BC5 on PC [inf: UE's normal-map format, not read here]); then the TEXTURE_CMP
    set is copied from the live reference texture of the same kind (hf_workflow _copy_texture_settings [prec]),
    must read back equal to it, and must still pass pilot.verify_texture for the kind.
  * Collision: the precedent sets auto_generate_collision False (phase1_import.fbx_options) and never authors
    collision; Interchange ignores FbxImportUI (memory ue58-fbx-import-traps) so the result is gated EQUAL to the
    reference P06 T5P mesh's simple-collision count (StaticMeshEditorSubsystem.GetSimpleCollisionCount,
    StaticMeshEditorSubsystem.h:259 [decl]) -- the reference came through the same import path [prec].

MEMORY RULES BAKED IN: batch <= 3 wings per MCP call + collect_garbage + free-RAM floor (ue58-bulk-import-oom-crash);
fbx_options(True) set anyway + LodGroup gate num_lods == 2 + stray diff (ue58-fbx-import-traps); modify() before
setters; no unreal object in a module global (puss-mcp-python-crashes-the-editor); runner purges the Saved module
cache (ue58-python-stale-module-cache); success marker only after asserted read-back (puss-assert-dont-print);
markers carry run=<id>|batch=<k> (puss-log-markers-run-id); a failure never reloads or deletes what this run made --
it stops, saves nothing, and asks for a Don't-Save editor restart (ue58-reimport-revert-by-reload-fails).
"""
import hashlib
import json
import os

MARK = "FLATV3_P06IMPORT"
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
P06_DIR_REL = "DerivedAssets/FlatV3/Realism_20261007/P06_backrooms"
MANIFEST_REL = P06_DIR_REL + "/P06_IMPORT_MANIFEST_v2.json"
BUILD_REPORT_REL = P06_DIR_REL + "/P06_BUILD_REPORT_v2.json"
MANIFEST_RUN = "FV3RZ-P06-20261007-02"
EXPECTED_PICKS = (1, 2, 3, 6, 7, 8, 9, 10, 25, 26, 30, 33, 35, 38, 39)

ROOT = "/Game/Scenes/Wings/FlatV3/Realism"
MESH_FOLDERS = {"t5p": ROOT + "/T5P", "t5j": ROOT + "/T5J"}
TEX_ROOT = ROOT + "/Textures"
MI_ROOT = ROOT + "/Materials/Instances"

BB = "/Game/Scenes/Wings/PaintedSurface/Billboard/"
PS = "/Game/Scenes/Wings/PaintedSurface/"
PARENTS = {"Front": BB + "MI_Billboard_Front", "Flap": BB + "MI_Billboard_Flap",
           "Timber": PS + "M_Wing_CanvasEdge_Master", "Edge": PS + "M_Wing_CanvasEdge_Master_v3"}
SLOTS = ("Front", "Flap", "Timber", "Edge")

P06 = "/Game/Scenes/Wings/FlatV3/Passage06"
REFERENCE = {   # live P06 V3 assets made by the precedent imports (FV3P06I-20261002-04 / FV3HF-20261006-P06) [prec]
    "mesh": P06 + "/StaticMeshes/T5P/SM_FlatV3_P06_bronze_tree_L_v2_t5p",
    "Front": P06 + "/Materials/Instances/MI_FlatV3_P06_bronze_tree_L_v2_Front_o2p",
    "Flap": P06 + "/Materials/Instances/MI_FlatV3_P06_bronze_tree_L_v2_Flap",
    "textures": {"SkinColor": P06 + "/Textures/P06_bronze_tree_L_v2/T_P06_bronze_tree_L_v2_SkinColor_o2",
                 "SkinMask": P06 + "/Textures/P06_bronze_tree_L_v2/T_P06_bronze_tree_L_v2_SkinMask_o2",
                 "SkinNormal": P06 + "/Textures/P06_bronze_tree_L_v2/T_P06_bronze_tree_L_v2_SkinNormal_o2",
                 "AgedStencil": P06 + "/Textures/Aged/P06_bronze_tree_L_v2/T_P06_bronze_tree_L_v2_AgedPlywood_Stencil_Color"},
}
AGED_COMMON_ROOT = P06 + "/Textures/Aged/Common"
COMMON_AGED = ("T_FlatV3_AgedSoftwood_Color", "T_FlatV3_AgedSoftwood_Roughness", "T_FlatV3_AgedSoftwood_NormalDX",
               "T_FlatV3_AgedPlywood_Roughness", "T_FlatV3_AgedPlywood_NormalDX", "T_FlatV3_AgedSteel_Color")
COMMON_AGED_RECORD_REL = "Saved/CodexFlatV3/swapkit/swapkit_p06_import_FV3P06I-20261002-04.json"
STENCIL_PNG = "T_FlatV3_AgedPlywood_Stencil_Color.png"

TEXTURE_KINDS = {"SkinColor": "SkinColor", "SkinMask": "SkinMask", "SkinNormal": "SkinNormal",
                 "AgedStencil": "AgedColor"}                       # phase1_import.texture_kind vocabulary [prec]
TEXTURE_CMP = ("compression_settings", "srgb", "lod_group", "mip_gen_settings", "flip_green_channel",
               "never_stream", "virtual_texture_streaming")
# Every compared property is COPIED from the live reference texture of the same kind after configure_texture (the
# hf_workflow._copy_texture_settings pattern copies its whole TEXTURE_PROPS set [prec]); pilot.verify_texture then
# asserts the kind rule (sRGB / compression / no green flip / POT + mips) on the result, and the DRY first runs that
# same verify_texture on the reference itself, so a reference that breaks the kind rule refuses before any import.
COPY_FROM_REFERENCE = TEXTURE_CMP

# Batches: <= 3 wings per MCP call (memory ue58-bulk-import-oom-crash).  Chain slabs first so the relayout's
# chain resolves as early as possible; every R design last.
BATCHES = ((26, 30, 25), (35, 38, 39), (33, 1, 3), (6, 7, 2), (8, 9, 10))
MAX_PER_BATCH = 3
MIN_FREE_RAM_GB = 12.0

BOUNDS_TOL_CM = 1.5            # slot_a verify_flat_general tolerance [prec]
PIVOT_TOL_CM = 1.0             # slot_a PIVOT_SOCKET_FAIL tolerance [prec]
FRONT_X, BACK_X, EDGE_TOL = -15.0, -10.0, 0.05   # edge_rollout_core.py:50 [prec]


class PlanError(Exception):
    pass


def require(cond, reason):
    if not cond:
        raise PlanError(reason)


def sha_obj(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def stem(path):
    return os.path.splitext(path.replace("\\", "/").rsplit("/", 1)[-1])[0]


# =====================================================================================================================
# Pure geometry helpers (Unreal static-mesh frame)
# =====================================================================================================================

def expected_import_bounds(validation):
    """slot_a_import.expected_import_bounds [prec]: Interchange reflects FBX Y; X/Z keep their sign."""
    b = validation["bounds_m"]
    return ([b["min"][0] * 100.0, -b["max"][1] * 100.0, b["min"][2] * 100.0],
            [b["max"][0] * 100.0, -b["min"][1] * 100.0, b["max"][2] * 100.0])


def side_extension_ok(side, mn, mx):
    """slot_a verify_flat_general LEFT/RIGHT_SIDE_EXTENSION rule [prec]."""
    if side == "L":
        return mn[1] >= -1.0 and mx[1] >= 100.0
    return mx[1] <= 1.0 and mn[1] <= -100.0


def height_gate(bounds_cm, height_cm, pole):
    """Bounds Z vs the manifest height: the card spans 0..height_cm, the baked poles add bottom_z_cm below and
    top_above_panel_cm above (sockets sidecar baked_pole_geometry [meas]).  Returns '' or the reason."""
    want_min = float(pole["bottom_z_cm"])
    want_max = float(height_cm) + float(pole["top_above_panel_cm"])
    zmin, zmax = float(bounds_cm["min"][2]), float(bounds_cm["max"][2])
    if abs(zmin - want_min) > BOUNDS_TOL_CM or abs(zmax - want_max) > BOUNDS_TOL_CM:
        return "HEIGHT_VS_MANIFEST z %.2f..%.2f want %.2f..%.2f" % (zmin, zmax, want_min, want_max)
    return ""


def edge_geometry_ok(geom):
    """edge_rollout_core.geometry_ok [prec]: per LOD the Edge section spans x -15..-10, Front sits at x -15."""
    if not geom:
        return False, "NO_LODS"
    for row in geom:
        e, f = row.get("edge_x"), row.get("front_x")
        if e is None:
            return False, "LOD%d_NO_EDGE_SECTION" % row["lod"]
        if abs(e[0] - FRONT_X) > EDGE_TOL or abs(e[1] - BACK_X) > EDGE_TOL:
            return False, "LOD%d_EDGE_X_%.3f_%.3f_NOT_-15_-10" % (row["lod"], e[0], e[1])
        if f is None or abs(f[0] - FRONT_X) > EDGE_TOL or abs(f[1] - FRONT_X) > EDGE_TOL:
            return False, "LOD%d_FRONT_NOT_AT_X-15|%s" % (row["lod"], f)
    return True, ""


def census_exact(census, expected_content):
    """The only dirty packages allowed are exactly this batch's new packages; no map."""
    return census.get("maps") == [] and sorted(census.get("content", [])) == sorted(expected_content)


# =====================================================================================================================
# The plan (files only; the DRY adds the editor's view)
# =====================================================================================================================

def _wing(project, entry, report_by_pick, record_hashes, refusals):
    pick = int(entry["pick_n"])
    tag = "pick %d" % pick
    asset = str(entry["asset"])
    variant = asset.rsplit("_", 1)[-1]
    side = str(entry["side"])
    if variant not in MESH_FOLDERS or not str(entry.get("variant", "")).startswith(variant):
        refusals.append("VARIANT_UNKNOWN %s %s %s" % (tag, asset, entry.get("variant")))
        return None
    require(asset.startswith("SM_FlatV3_"), "ASSET_PREFIX %s" % asset)
    owner = asset[len("SM_FlatV3_"):-len("_" + variant)]
    if not owner.endswith("_" + side):
        refusals.append("OWNER_SIDE %s %s %s" % (tag, owner, side))
    item_dir = "/".join(str(entry["fbx"]).split("/")[:5])
    rp = report_by_pick.get(pick)
    if rp is None or rp.get("build_status") != "PASS" or rp.get("owner") != owner or rp.get("side") != side \
            or rp.get("final_asset") != asset or rp.get("fbx_sha256") != entry.get("fbx_sha256"):
        refusals.append("BUILD_REPORT_DISAGREES %s" % tag)
    if not entry.get("validation_pass"):
        refusals.append("VALIDATION_NOT_PASS %s" % tag)
    stencil = [a for a in entry["aged_textures"] if a["path"].endswith(STENCIL_PNG)]
    if len(stencil) != 1:
        refusals.append("STENCIL_COUNT %s" % tag)
        return None
    for a in entry["aged_textures"]:
        n = stem(a["path"])
        if n in COMMON_AGED and record_hashes.get(n) != [a["sha256"]]:
            refusals.append("AGED_COMMON_HASH %s %s (not the set already in %s)" % (tag, n, AGED_COMMON_ROOT))
    if sorted(stem(a["path"]) for a in entry["aged_textures"]) != sorted(COMMON_AGED + (stem(STENCIL_PNG),)):
        refusals.append("AGED_SET %s" % tag)
    sources = {"fbx": (entry["fbx"], entry["fbx_sha256"]),
               "socket": (entry["socket_sidecar"], entry["socket_sidecar_sha256"]),
               "SkinColor": (entry["textures"]["SkinColor"]["path"], entry["textures"]["SkinColor"]["sha256"]),
               "SkinMask": (entry["textures"]["SkinMask"]["path"], entry["textures"]["SkinMask"]["sha256"]),
               "SkinNormal": (entry["textures"]["SkinNormal"]["path"], entry["textures"]["SkinNormal"]["sha256"]),
               "AgedStencil": (stencil[0]["path"], stencil[0]["sha256"]),
               "validation": (entry["validation"], None),
               "mi_params": ("%s/stage1/%s/skin_v3/%s_mi_params.json" % (item_dir, owner, owner), None),
               "edge_probe": ("%s/edge_gate/edge_probe.json" % item_dir, None)}
    src = {}
    for key, (rel, want) in sources.items():
        p = os.path.join(project, rel)
        if not os.path.isfile(p):
            refusals.append("SOURCE_MISSING %s %s %s" % (tag, key, rel))
            continue
        got = sha_file(p)
        if want is not None and got != want:
            refusals.append("SOURCE_HASH_MISMATCH %s %s" % (tag, key))
        src[key] = {"rel": rel, "abs": p.replace("\\", "/"), "sha256": got}
    if len(src) != len(sources):
        return None
    validation = load_json(src["validation"]["abs"])
    sidecar = load_json(src["socket"]["abs"])
    mi_params = load_json(src["mi_params"]["abs"])
    probe = load_json(src["edge_probe"]["abs"])
    checks = validation.get("checks", {})
    # ---- offline pre-gates: everything slot_a's verify_flat_general will assert, checked against the files first
    if not validation.get("pass") or checks.get("fbx_lod_group", {}).get("mechanism") != "FBX LodGroup NodeAttribute":
        refusals.append("LODGROUP_GATE %s" % tag)
    if checks.get("material_slots_exact", {}).get("value") != list(SLOTS):
        refusals.append("SLOTS_IN_FBX %s" % tag)
    sock_names = sorted(r["name"] for r in sidecar.get("sockets", []))
    poles = sorted(checks.get("baked_poles_lod0", {}).get("details", {}))
    # Socket authority = the sidecar (slot_a/hf write sockets from it [prec]); it must agree with the BAKED POLE
    # GEOMETRY the validator measured (baked_poles_lod0.details).  validation.socket_contract.details is NOT used:
    # for picks 2 and 3 it lists 3 sockets while the sidecar and the baked-pole geometry both carry SOCKET_Pole_2
    # [meas 7 Oct] -- slot_a's SOCKET_SPEC_NAMES rule would refuse those two; recorded per wing as a note.
    if sidecar.get("asset") != asset or sock_names != sorted(["SOCKET_Hinge", "SOCKET_Pivot"] + poles) or not poles:
        refusals.append("SOCKET_SIDECAR_VS_BAKED_POLES %s %s vs poles %s" % (tag, sock_names, poles))
    contract_names = sorted(checks.get("socket_contract", {}).get("details", {}))
    notes = [] if contract_names == sock_names else [
        "validation.socket_contract lists %s; sidecar + baked poles carry %s (sidecar used)" % (contract_names, sock_names)]
    by_sock = {r["name"]: r for r in sidecar.get("sockets", [])}
    if "SOCKET_Hinge" not in by_sock or max(abs(float(v)) for v in by_sock["SOCKET_Hinge"]["relative_location_cm"]) > 1.0:
        refusals.append("HINGE_NOT_AT_ORIGIN %s" % tag)
    if "SOCKET_Pivot" in by_sock:
        # Pivot at half the MANIFEST height (sidecar contract).  slot_a's rule (validation height.expected_m * 50,
        # tol 1 cm) is NOT reused: the realism validators record the measured art height (e.g. 4.435 m for pick 2)
        # while the pivot sits at 500 cm, so that rule would refuse 14 of 15 wings [meas 7 Oct, this function's
        # first run].
        pz = float(by_sock["SOCKET_Pivot"]["relative_location_cm"][2])
        if abs(pz - float(entry["height_cm"]) * 0.5) > PIVOT_TOL_CM:
            refusals.append("PIVOT_Z_VS_MANIFEST_HEIGHT %s %.3f vs %.3f" % (tag, pz, float(entry["height_cm"]) * 0.5))
    else:
        refusals.append("NO_PIVOT_SOCKET %s" % tag)
    mn, mx = expected_import_bounds(validation)
    if not side_extension_ok(side, mn, mx):
        refusals.append("SIDE_EXTENSION %s %s %s" % (tag, mn, mx))
    hg = height_gate({"min": mn, "max": mx}, entry["height_cm"], sidecar["baked_pole_geometry"])
    if hg:
        refusals.append("%s %s" % (hg, tag))
    if mi_params.get("parents") != {"Front": PARENTS["Front"], "Flap": PARENTS["Flap"]}:
        refusals.append("MI_PARENT_MISMATCH %s %s" % (tag, mi_params.get("parents")))
    tp = mi_params.get("texture_parameters", {})
    col = stem(src["SkinColor"]["rel"])
    if stem(tp.get("SkinMask", "")) != stem(src["SkinMask"]["rel"]) or \
            stem(tp.get("SkinNormal", "")) != stem(src["SkinNormal"]["rel"]) or \
            stem(tp.get("SkinColor", "")) not in (col, col[:-1] if col.endswith("_o2p") else col):
        refusals.append("MI_PARAMS_TEXTURES_DISAGREE %s" % tag)
    hit = [x for x in probe if x["fbx"].replace("\\", "/").endswith(src["fbx"]["rel"])]
    if len(hit) != 1:
        refusals.append("EDGE_PROBE_MISSING %s" % tag)
    else:
        geom = [{"lod": i, "edge_x": [o["slots"]["Edge"]["x_min"], o["slots"]["Edge"]["x_max"]],
                 "front_x": [o["slots"]["Front"]["x_min"], o["slots"]["Front"]["x_max"]]}
                for i, (_, o) in enumerate(sorted(hit[0]["objects"].items()))]
        ok, why = edge_geometry_ok(geom)
        if not ok:
            refusals.append("EDGE_PROBE %s %s" % (tag, why))
    dest = {"mesh": "%s/%s" % (MESH_FOLDERS[variant], asset),
            "SkinColor": "%s/%s/%s" % (TEX_ROOT, owner, col),
            "SkinMask": "%s/%s/%s" % (TEX_ROOT, owner, stem(src["SkinMask"]["rel"])),
            "SkinNormal": "%s/%s/%s" % (TEX_ROOT, owner, stem(src["SkinNormal"]["rel"])),
            "AgedStencil": "%s/Aged/%s/T_%s_AgedPlywood_Stencil_Color" % (TEX_ROOT, owner, owner),
            "Front": "%s/MI_FlatV3_%s_Front" % (MI_ROOT, owner),
            "Flap": "%s/MI_FlatV3_%s_Flap" % (MI_ROOT, owner)}
    return {"pick": pick, "owner": owner, "asset": asset, "variant": variant, "side": side,
            "height_cm": float(entry["height_cm"]), "width_cm": round(float(validation["dimensions_m"][1]) * 100.0, 1),
            "thickness_cm": round(float(validation["dimensions_m"][0]) * 100.0, 2),
            "sources": src, "destinations": dest, "packages": sorted(dest.values()), "notes": notes,
            "expected": {"bounds_cm": {"min": mn, "max": mx},
                         "triangles": {"lod0": int(validation["triangle_counts"]["lod0"]),
                                       "lod1": int(validation["triangle_counts"]["lod1"])},
                         "sockets": sock_names, "pole": sidecar["baked_pole_geometry"],
                         "scalars": mi_params["scalar_parameters"],
                         "slot_materials": [dest["Front"], dest["Flap"], PARENTS["Timber"], PARENTS["Edge"]]},
            "validation": validation}


def build_plan(project, batches=BATCHES):
    """Files-only plan.  Returns {wings, batches, refusals, inputs_hash, ...}; refusals empty = file gates pass."""
    refusals = []
    manifest = load_json(os.path.join(project, MANIFEST_REL))
    report = load_json(os.path.join(project, BUILD_REPORT_REL))
    record = load_json(os.path.join(project, COMMON_AGED_RECORD_REL))
    record_hashes = record.get("common_hashes", {}).get("P06", {})
    if record.get("status") != "PASS" or sorted(record_hashes) != sorted(COMMON_AGED):
        refusals.append("AGED_COMMON_RECORD %s" % COMMON_AGED_RECORD_REL)
    if manifest.get("run") != MANIFEST_RUN or manifest.get("unreal_imported") is not False:
        refusals.append("MANIFEST_RUN %s imported=%s" % (manifest.get("run"), manifest.get("unreal_imported")))
    picks = sorted(int(e["pick_n"]) for e in manifest["meshes"])
    if picks != sorted(EXPECTED_PICKS):
        refusals.append("PICKS_MISMATCH %s" % picks)
    report_by_pick = {int(p["pick_n"]): p for p in report.get("picks", [])}
    passed = sorted(k for k, p in report_by_pick.items() if p.get("build_status") == "PASS")
    if passed != sorted(EXPECTED_PICKS):
        refusals.append("BUILD_REPORT_PASS_SET %s" % passed)
    wings = {}
    for e in manifest["meshes"]:
        w = _wing(project, e, report_by_pick, record_hashes, refusals)
        if w is not None:
            wings[w["pick"]] = w
    flat = [p for b in batches for p in b]
    if sorted(flat) != sorted(EXPECTED_PICKS) or len(flat) != len(set(flat)):
        refusals.append("BATCHES_DO_NOT_COVER_PICKS_ONCE %s" % (batches,))
    if any(len(b) > MAX_PER_BATCH or not b for b in batches):
        refusals.append("BATCH_TOO_BIG (max %d wings per MCP call)" % MAX_PER_BATCH)
    allpk = [p for w in wings.values() for p in w["packages"]]
    if len(allpk) != len(set(allpk)):
        refusals.append("DUPLICATE_DESTINATION")
    if any(not p.startswith(ROOT + "/") for p in allpk):
        refusals.append("DESTINATION_OUTSIDE_ROOT")
    out_batches = []
    for k, b in enumerate(batches, 1):
        pk = sorted(p for pick in b if pick in wings for p in wings[pick]["packages"])
        out_batches.append({"batch": k, "picks": list(b), "owners": [wings[p]["owner"] for p in b if p in wings],
                            "packages": pk})
    inputs = {"wings": {str(k): {"sources": {s: v["sha256"] for s, v in w["sources"].items()},
                                 "destinations": w["destinations"]} for k, w in sorted(wings.items())},
              "batches": [list(b) for b in batches], "parents": PARENTS, "reference": REFERENCE,
              "aged_common_root": AGED_COMMON_ROOT, "texture_cmp": list(TEXTURE_CMP)}
    plan = {"mark": MARK, "manifest": MANIFEST_REL, "manifest_run": manifest.get("run"), "root": ROOT,
            "mesh_folders": MESH_FOLDERS, "wings": {str(k): w for k, w in sorted(wings.items())},
            "batches": out_batches, "package_count": len(allpk), "refusals": refusals,
            "aged_common": {"root": AGED_COMMON_ROOT, "names": list(COMMON_AGED), "strategy": "REUSE_EXISTING"},
            "inputs_hash": sha_obj(inputs)}
    plan["gates_ok"] = not refusals
    return plan


def relayout_mesh_paths(plan):
    """For the P06 relayout: {owner: /Game mesh path} -- the only realism meshes this kit creates."""
    return {w["owner"]: w["destinations"]["mesh"] for w in plan["wings"].values()}


# =====================================================================================================================
# Args, tokens, ledger, undo
# =====================================================================================================================

def confirm_for(mode, plan=None, batch=None):
    if mode == "DRY":
        return "DRY P06IMPORT"
    if mode == "VERIFY":
        return "VERIFY P06IMPORT"
    if mode == "UNDO_LIST":
        return "UNDO_LIST P06IMPORT"
    if mode == "APPLY":
        require(plan is not None and batch is not None, "APPLY_NEEDS_PLAN_AND_BATCH")
        return "APPLY P06IMPORT BATCH %d #%s" % (int(batch), plan["inputs_hash"][:8])
    raise PlanError("MODE_INVALID %r" % (mode,))


def validate_args(args, plan=None):
    mode = str(args.get("mode") or "").upper()
    require(mode in ("DRY", "APPLY", "VERIFY", "UNDO_LIST"), "MODE_INVALID %r" % (mode,))
    batch = None
    if mode == "APPLY":
        try:
            batch = int(args.get("batch"))
        except (TypeError, ValueError):
            raise PlanError("BATCH_INVALID %r" % (args.get("batch"),))
        require(plan is not None and 1 <= batch <= len(plan["batches"]), "BATCH_INVALID %r" % (batch,))
    want = confirm_for(mode, plan, batch)
    require(args.get("confirm") == want, "CONFIRM_MISMATCH %r want %r" % (args.get("confirm"), want))
    return mode, batch


def undo_list(plan, ledger=None):
    """Manual undo for a create-only import: the package list in a reference-safe delete order (MIs, then meshes,
    then textures -- slot_a delete_unsaved_created order [prec]).  NOTHING here deletes; a human (or a separately
    reviewed one-off) deletes in the Content Browser, only after the relayout no longer references the meshes."""
    done = set()
    if ledger:
        done = {int(k) for k, v in ledger.get("batches", {}).items() if v.get("status") == "SAVED"}
    rows = []
    for b in plan["batches"]:
        if ledger is not None and b["batch"] not in done:
            continue
        pk = b["packages"]
        order = [p for p in pk if "/Materials/Instances/" in p] + [p for p in pk if "/T5P/" in p or "/T5J/" in p]
        order += [p for p in pk if p not in order]
        rows.append({"batch": b["batch"], "owners": b["owners"], "delete_in_order": order,
                     "files": ["Content/%s.uasset" % p[len("/Game/"):] for p in order]})
    return {"mode": "UNDO_LIST", "auto_delete": False,
            "how": ["1 Make sure nothing references these meshes: the P06 relayout must be REVERTED (or never applied) "
                    "-- relayout_apply REVERT restores the old panels.",
                    "2 In the Content Browser, select the listed assets of a batch (MIs first, then the mesh, then the "
                    "textures) and Delete; the editor's reference check must report NO referencers.  Never Force Delete.",
                    "3 Save nothing else; then VERIFY reports the batch as missing.",
                    "Never use Save All; never delete Passage06 assets (the reused aged Common set belongs to P06)."],
            "batches": rows}


if __name__ == "__main__":   # offline: python p06_import_core.py  -> p06_import_plan_offline.json
    here = os.path.dirname(os.path.abspath(__file__))
    project = os.path.abspath(os.path.join(here, "..", "..", ".."))
    p = build_plan(project)
    slim = json.loads(json.dumps(p))
    for w in slim["wings"].values():
        w.pop("validation", None)
    slim["undo_list_if_all_applied"] = undo_list(p)
    with open(os.path.join(here, "p06_import_plan_offline.json"), "w", encoding="utf-8") as fh:
        json.dump(slim, fh, indent=1)
    print("P06IMPORT_OFFLINE_PLAN|wings=%d|packages=%d|batches=%s|gates_ok=%s|hash=%s" % (
        len(p["wings"]), p["package_count"], [b["picks"] for b in p["batches"]], p["gates_ok"], p["inputs_hash"][:8]))
    for r in p["refusals"]:
        print("  REFUSAL " + r)
    for b in p["batches"]:
        print("  batch %d: %s (%d packages)" % (b["batch"], ", ".join(b["owners"]), len(b["packages"])))
