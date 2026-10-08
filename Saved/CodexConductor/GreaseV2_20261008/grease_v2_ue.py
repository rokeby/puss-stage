"""S3 hand-print grease v2: import the approved v2 textures and repoint the 142 grease MIs.  PREPARED, NOT RUN.

Gary 8 Oct: go.  Plan: GREASE_V2_REPORT.md "Import plan".  Reference implementation (texture import with sha pinning,
the 142 MI_HP_S03_g1_* MIs, worklist batching, read-back): Saved/CodexFlatV3/handprints/grease/hp_grease_assets.py
(cited below as [ref:line]).  One mode per MCP call; wrappers gv2_ue_<step>.py set GV2_MODE (and GV2_CONFIRM for
APPLY / REVERT).  Optional args file grease_v2_ue_args.json (absent = all defaults).  Run order: README_GV2_UE.md.

  IMPORT_DRY / IMPORT   create-only: T_HP_S03_GreaseAtlas_v2 (srgb False, TC_MASKS) and T_HP_S03_PrintNormal_v2
                        (srgb False, TC_NORMALMAP); the lod/mip/filter/address/streaming settings (+ flip_green for the
                        normal) are COPIED from the live T_HP_S03_GreaseAtlas / T_S03_HandPrints_Normal, read live in
                        this call and recorded.  Source sha must equal the pins; refuses if either target exists.
                        Census before save == exactly those 2 packages; saves those 2 only; clean after.
                                                                   -> GV2_IMPORT_IMPORTED|NOT_YET_VERIFIED
  VERIFY_TEX            later call: class, size (2048^2 / 1024^2; a <=32 placeholder = PENDING, retry),
                        compression, srgb, flip_green and every copied setting == the recorded reference.
                                                                   -> GV2_VERIFY_TEX_SUCCESS
  SNAPSHOT_DRY/SNAPSHOT read-only in Unreal: lists MI_HP_S03_g1_* LIVE (must equal the pinned worklist, 142, and the
                        hp_grease_assets_record done list, unless args ack_mi_count == the live count); records every
                        MI's original GreaseMask/PrintNormal state (override or inherited, effective value), all
                        scalars and override-name sets, fixes the <=20 batches, backs up the MI .uasset files to
                        Backups/PreHPGreaseV2-<run>/, hashes every OTHER file under HandPrints (the protected set) and
                        reads back the protected materials' texture params.        -> GV2_SNAPSHOT_SUCCESS
  APPLY_DRY / APPLY     next batch (<=20; an interrupted batch first): writes ONLY the GreaseMask and PrintNormal
                        overrides -> v2, update, reads back (both params, every scalar, override sets, parent), census
                        == exactly the batch's MI packages, saves those only, clean, reads back again, protected hashes
                        unchanged.  Repeat until GV2_APPLY_NOTHING_TO_DO.        -> GV2_APPLY_BATCH_DONE
  APPLY_VERIFY          later call: every MI in the v2 state, scalars == snapshot, protected files and protected
                        read-backs unchanged.                                      -> GV2_APPLY_SUCCESS|verified=N
  REVERT_DRY / REVERT   next batch: drift check (each param original or v2; scalars == snapshot; else refuse), then
                        restore the recorded state exactly: an inherited param has its override CLEARED, an overridden
                        one is set back to its recorded texture.  Read back, census, save, read back.
                                                                   -> GV2_REVERT_BATCH_DONE / _NOTHING_TO_DO
  REVERT_VERIFY         later call: every MI == snapshot, protected unchanged.    -> GV2_REVERT_SUCCESS|verified=N

Every mode: right world, no PIE (preflight [ref:134-141]); write modes need a CLEAN census at start and exactly clean
after their own saves [ref:144-146]; the record is written BEFORE the first mutation [ref:177-179, 448-449].  Never
deletes an asset or node, never reloads, never touches the level, the master M_HP_S03_Grease, the tint layer, or the
visible print decal (M_HP_S03_Decal_v3 + Materials/V3 MIs, which also use T_S03_HandPrints_Normal).  A setter's return
value is never trusted: everything is read back [memory: setters lie].  On a STOP after a write the in-memory MIs stay
dirty and NOTHING is saved: resolve with a Don't-Save restart, then re-run the same step (it resumes).
No Unreal object (or call) at module level: `unreal` is imported inside functions only.

API tiers (UE 5.8 headers under D:/Unreal Engine/UE_5.8; [ref] = used by the live reference tool, so measured-in-use):
  ListAssets            EditorAssetLibrary.h:328            declaration-proven; used slot_e_mip_stopgap.py
  SetMaterialInstanceTextureParameterValue  MaterialEditingLibrary.h:430   declaration-proven; used curtain_image.py:421
  GetMaterialInstanceTextureParameterValue  MaterialEditingLibrary.h:426   declaration-proven; used curtain_image.py:374
  IsMaterialInstanceParameterOverridden     MaterialEditingLibrary.h:475   declaration-proven; ran live for SET params
                        (True: s3_sack_install_mat_record.json:171-181, measured); False for an INHERITED texture param
                        is INFERRED, so it is only a cross-check against the TextureParameterValues
                        entries (MaterialInstance.h:784-785; FTextureParameterValue::IsOverride() returns true for every
                        entry, MaterialInstance.h:250 => an entry IS an override, declaration-proven) and a
                        disagreement refuses in SNAPSHOT.
  SetMaterialInstanceParameterOverride      MaterialEditingLibrary.h:486   declaration-proven; NOT used before:
                        that bOverride=False removes the entry is INFERRED -> read back (entry gone, effective value ==
                        recorded inherited value) before any save; a lie STOPs unsaved.  args revert_pin_fallback=true
                        instead pins the recorded inherited texture as an override (renders identically; recorded).
  GetMaterialDefaultTextureParameterValue   MaterialEditingLibrary.h:301   declaration-proven; read-only; also called by
                        velvet_v2_build.py:298 (whether that ran live was not checked: INFERRED)
  GetScalarParameterNames(UMaterialInterface*) MaterialEditingLibrary.h:502 declaration-proven; [ref:366] on a Material
  Texture props: LODGroup Texture.h:1544, MipGenSettings :1427, LODBias :1508, Filter :1516, MaxTextureSize :1355,
                 bFlipGreenChannel :1391, VirtualTextureStreaming :1611 (EditAnywhere, BlueprintReadOnly: settable by
                 set_editor_property is INFERRED, read back), NeverStream StreamableRenderAsset.h:370,
                 AddressX/Y Texture2D.h:63/67.  All declaration-proven as UPROPERTY(EditAnywhere).
"""
import datetime
import glob
import hashlib
import json
import os
import shutil
import traceback

TOOL = "grease_v2_ue"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"            # [ref:39]
SUBDIR = ("Saved", "CodexConductor", "GreaseV2_20261008")
RECORD_NAME = "grease_v2_ue_record.json"
ARGS_NAME = "grease_v2_ue_args.json"
REF_DIR = ("Saved", "CodexFlatV3", "handprints", "grease")
REF_RECORD_NAME = "hp_grease_assets_record.json"
WORKLIST_NAME = "hp_grease_mi_worklist.json"
WORKLIST_SHA256 = "9d9c19a451f74fb9eaaae4c0a1fbf178ee0b9f72d0ca3d21bc142f1ac54ee157"       # [ref:44]
SRC_DIR = ("DerivedAssets", "S3Marble", "GreaseV2_20261008")
ATLAS_PNG_NAME = "T_HP_S03_GreaseAtlas_v2.png"
ATLAS_PNG_SHA256 = "d906dbee789f0764df90d1026a17f93da8d254371b01d39780577b244028c47e"     # gv2_build_report.json
NORMAL_PNG_NAME = "T_HP_S03_PrintNormal_v2.png"
NORMAL_PNG_SHA256 = "cbfd70d31aa78e806f6f3083bff3a574849db4f5cd5c4a9b2f5d30344399ff43"    # gv2_build_report.json
ROOT = "/Game/Scenes/Scene3/HandPrints"
TEX_DIR = ROOT + "/Textures"
ATLAS_V1 = TEX_DIR + "/T_HP_S03_GreaseAtlas"                                                # [ref:50]
NORMAL_V1 = TEX_DIR + "/T_S03_HandPrints_Normal"                                            # [ref:51]
ATLAS_V2_NAME = "T_HP_S03_GreaseAtlas_v2"
NORMAL_V2_NAME = "T_HP_S03_PrintNormal_v2"
ATLAS_V2 = TEX_DIR + "/" + ATLAS_V2_NAME
NORMAL_V2 = TEX_DIR + "/" + NORMAL_V2_NAME
MI_DIR = ROOT + "/Materials/Grease"
MASTER = MI_DIR + "/M_HP_S03_Grease"                                                        # [ref:54]
MI_PREFIX = "MI_HP_S03_g1_"
PRINT_MASTER_V3 = ROOT + "/Materials/M_HP_S03_Decal_v3"           # hp_import_atlas.py:144; NormalAtlas :561
PRINT_V3_DIR = ROOT + "/Materials/V3"
PRINT_NORMAL_PARAM = "NormalAtlas"
TINT_MASTER = ROOT + "/Materials/GreaseTint/M_HP_S03_GreaseTint"  # hp_grease_tint.py:56-58
PARAMS = {"GreaseMask": (ATLAS_V1, ATLAS_V2), "PrintNormal": (NORMAL_V1, NORMAL_V2)}         # [ref:289-293]
MASTER_SCALARS = sorted(("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize", "FlipU", "GlobalFlipU", "GlobalFlipV",
                         "GreaseGain", "GreaseRoughMin", "GreaseRoughRange", "NormalStrength"))  # [ref:61-62]
MI_SCALARS = ("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize", "FlipU", "GreaseGain")      # [ref:63] the six
EXPECTED_MI_COUNT = 142
SIZES = {ATLAS_V2: [2048, 2048], NORMAL_V2: [1024, 1024]}
# lod_group first: changing it can re-derive other settings in PostEditChange (INFERRED), so set it before the rest.
COPY_PROPS = ("lod_group", "mip_gen_settings", "filter", "lod_bias", "never_stream", "max_texture_size",
              "virtual_texture_streaming", "address_x", "address_y")
NORMAL_EXTRA = ("flip_green_channel",)
MI_BATCH_MAX = 20                                                                           # [ref:58]
MIN_FREE_RAM_GB = 8.0                                                                       # [ref:59]
EPS = 1e-6                                                                                  # [ref:498]
CONFIRM = {"APPLY": "APPLY GREASE V2", "REVERT": "REVERT GREASE V2"}
MODE = globals().get("GV2_MODE")
CONFIRM_GIVEN = globals().get("GV2_CONFIRM")
FREE_RAM_PROBE = globals().get("GV2_FREE_RAM_PROBE")        # harness seam only; None in every wrapper


class StageError(RuntimeError):
    pass


def require(cond, msg):
    if not cond:
        raise StageError(msg)


def U():
    import unreal                       # imported per call; never held at module level
    return unreal


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def project_dir():
    u = U()
    return str(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))


def proj(*parts):
    return os.path.join(project_dir(), *parts)


def record_path():
    return proj(*SUBDIR, RECORD_NAME)


def sha256(path):                                                                           # [ref:103-108]
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def path_of(obj):                                                                           # [ref:111-112]
    return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]


def census():                                                                               # [ref:96-100]
    u = U()

    def names(pkgs):
        return sorted(str(p.get_path_name()).split(".", 1)[0] for p in pkgs)
    return {"maps": names(u.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(u.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def preflight(clean=True):                                                                  # [ref:134-141]
    u = U()
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor = None
    if clean:
        before = census()
        require(not before["maps"] and not before["content"], "DIRTY_AT_START|" + json.dumps(before))


def end_clean():                                                                            # [ref:144-146]
    after = census()
    require(after == {"maps": [], "content": []}, "DIRTY_AFTER|" + json.dumps(after))


def census_exact(expected, label):
    got = census()
    want = {"maps": [], "content": sorted(expected)}
    require(got == want, "CENSUS_%s|want=%s|got=%s" % (label, json.dumps(want), json.dumps(got)))


def write_json(path, obj):                                                                  # [ref:124-131]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_record():
    p = record_path()
    if not os.path.isfile(p):
        return {"schema": "grease_v2_ue/1", "worklist_sha256": WORKLIST_SHA256, "stages": {}}
    with open(p, encoding="utf-8") as fh:
        rec = json.load(fh)
    require(rec.get("worklist_sha256") == WORKLIST_SHA256, "RECORD_FOR_OTHER_WORKLIST")
    return rec


def write_record(rec):
    write_json(record_path(), rec)


def read_args():
    p = proj(*SUBDIR, ARGS_NAME)
    if not os.path.isfile(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        args = json.load(fh)
    require(isinstance(args, dict), "ARGS_NOT_OBJECT")
    unknown = sorted(set(args) - {"ack_mi_count", "revert_pin_fallback", "note"})
    require(not unknown, "ARGS_UNKNOWN_KEYS|%s" % unknown)
    return args


def content_file(asset_path):
    require(asset_path.startswith("/Game/"), "NOT_GAME_PATH|" + asset_path)
    return proj("Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


def package_files(asset_path):
    """The .uasset plus any split siblings (.uexp/.ubulk) that exist."""
    base = content_file(asset_path)[:-len(".uasset")]
    return [base + ext for ext in (".uasset", ".uexp", ".ubulk") if os.path.isfile(base + ext)]


def backup_files(prefix, run, files):                                     # hp_grease_tint.py:184-196 pattern
    root = proj("Backups", prefix + run)
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    os.makedirs(root)
    pdir = project_dir()
    for src in files:
        require(os.path.isfile(src), "BACKUP_SOURCE_MISSING|" + src)
        dest = os.path.join(root, os.path.relpath(src, pdir))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        require(sha256(src) == sha256(dest), "BACKUP_HASH_MISMATCH|" + src)
    return root


def free_ram_gb():                                                                          # [ref:392-404]
    if FREE_RAM_PROBE is not None:
        return float(FREE_RAM_PROBE())
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)), "RAM_QUERY_FAILED")
    return status.ullAvailPhys / float(1 << 30)


def collect_garbage():
    U().SystemLibrary.collect_garbage()                                                     # [ref:197]


def log(msg):
    U().log(msg)


# ============================================================================================ IMPORT / VERIFY_TEX
def tex_props(tex, names):
    return {k: tex.get_editor_property(k) for k in names}


def jsonable(props):
    return {k: (v if isinstance(v, (bool, int, float)) or v is None else str(v)) for k, v in props.items()}


def import_one(png, name, ref_live, compression):
    u = U()
    task = u.AssetImportTask()                                                              # [ref:180-185]
    for k, v in (("filename", png), ("destination_path", TEX_DIR), ("destination_name", name),
                 ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    task = None
    path = TEX_DIR + "/" + name
    tex = u.EditorAssetLibrary.load_asset(path)
    require(isinstance(tex, u.Texture2D), "TEXTURE_IMPORT_FAILED|" + path)                  # [ref:187]
    for k, v in ref_live.items():                     # lod_group first (COPY_PROPS order), then srgb, compression
        tex.modify()
        tex.set_editor_property(k, v)
    tex.modify()
    tex.set_editor_property("srgb", False)                                                  # [ref:188-191]
    tex.modify()
    tex.set_editor_property("compression_settings", compression)
    got = tex_props(tex, list(ref_live) + ["srgb", "compression_settings"])                 # setters may lie: read back
    want = dict(ref_live, srgb=False, compression_settings=compression)
    bad = sorted(k for k in want if not (got[k] == want[k]))
    tex = None
    require(not bad, "TEXTURE_SETTING_READBACK|%s|%s" % (path, json.dumps({k: [str(got[k]), str(want[k])] for k in bad})))
    return path


def stage_import(run, dry):
    u = U()
    preflight()
    rec = read_record()
    require("import" not in rec["stages"], "IMPORT_STAGE_ALREADY_RECORDED")
    atlas_png = proj(*SRC_DIR, ATLAS_PNG_NAME)
    normal_png = proj(*SRC_DIR, NORMAL_PNG_NAME)
    for png, pin in ((atlas_png, ATLAS_PNG_SHA256), (normal_png, NORMAL_PNG_SHA256)):          # [ref:170]
        require(os.path.isfile(png), "SOURCE_MISSING|" + png)
        got = sha256(png)
        require(got == pin, "SOURCE_HASH_MISMATCH|%s|got=%s|pin=%s" % (os.path.basename(png), got, pin))
    for p in (ATLAS_V2, NORMAL_V2):                                                         # [ref:171] create-only
        require(not u.EditorAssetLibrary.does_asset_exist(p), "TEXTURE_EXISTS|" + p)
    TC = u.TextureCompressionSettings
    refs = {}
    for ref, names, comp in ((ATLAS_V1, COPY_PROPS, TC.TC_MASKS), (NORMAL_V1, COPY_PROPS + NORMAL_EXTRA, TC.TC_NORMALMAP)):
        t = u.EditorAssetLibrary.load_asset(ref)
        require(isinstance(t, u.Texture2D), "REFERENCE_MISSING|" + ref)
        live = tex_props(t, names)
        sanity = tex_props(t, ("srgb", "compression_settings"))
        t = None
        require(sanity["srgb"] is False and sanity["compression_settings"] == comp,
                "REFERENCE_NOT_AS_RECORDED|%s|%s" % (ref, json.dumps(jsonable(sanity))))
        refs[ref] = live
    if dry:
        end_clean()
        log("GV2_IMPORT_DRY_RUN_OK|run=%s|sources=pinned|targets_absent=2|ref_atlas=%s|ref_normal=%s|mutated=0"
            % (run, json.dumps(jsonable(refs[ATLAS_V1])), json.dumps(jsonable(refs[NORMAL_V1]))))
        return
    files = [f for f in glob.glob(proj("Content", "Scenes", "Scene3", "HandPrints", "Textures", "*")) if os.path.isfile(f)]
    backup = backup_files("PreHPGreaseV2Import-", run, files)
    rec["stages"]["import"] = {"run": run, "started_utc": utc(), "saved": False, "verified": False,
                               "assets": [ATLAS_V2, NORMAL_V2], "backup": backup,
                               "source_sha256": {ATLAS_PNG_NAME: ATLAS_PNG_SHA256, NORMAL_PNG_NAME: NORMAL_PNG_SHA256},
                               "reference_settings": {k: jsonable(v) for k, v in refs.items()}}
    write_record(rec)                                                       # BEFORE the first mutation [ref:177-179]
    import_one(atlas_png, ATLAS_V2_NAME, refs[ATLAS_V1], TC.TC_MASKS)
    import_one(normal_png, NORMAL_V2_NAME, refs[NORMAL_V1], TC.TC_NORMALMAP)
    census_exact([ATLAS_V2, NORMAL_V2], "BEFORE_SAVE")
    for p in (ATLAS_V2, NORMAL_V2):
        require(u.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), "SAVE_FAILED|" + p)   # [ref:193]
    end_clean()
    rec["stages"]["import"]["saved"] = True
    rec["stages"]["import"]["saved_utc"] = utc()
    write_record(rec)
    collect_garbage()
    log("GV2_IMPORT_IMPORTED|run=%s|assets=2|NOT_YET_VERIFIED: send VERIFY_TEX" % run)


def stage_verify_tex(run, dry):
    u = U()
    preflight(clean=False)                                                                  # [ref:202]
    rec = read_record()
    st = rec["stages"].get("import") or {}
    require(st.get("saved") is True, "TEXTURES_NOT_IMPORTED")
    require(st.get("verified") is not True, "TEXTURES_ALREADY_VERIFIED")
    TC = u.TextureCompressionSettings
    out, pending = {}, []
    for path, ref, names, comp in ((ATLAS_V2, ATLAS_V1, COPY_PROPS, TC.TC_MASKS),
                                   (NORMAL_V2, NORMAL_V1, COPY_PROPS + NORMAL_EXTRA, TC.TC_NORMALMAP)):
        tex = u.load_asset(path)
        require(isinstance(tex, u.Texture2D), "TEXTURE_CLASS|" + path)
        size = [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]
        srgb = bool(tex.get_editor_property("srgb"))
        got_comp = tex.get_editor_property("compression_settings")
        props = jsonable(tex_props(tex, names))
        tex = None
        if dry:
            out[path] = {"size": size}
            continue
        require(srgb is False, "TEXTURE_SRGB|" + path)
        require(got_comp == comp, "TEXTURE_COMPRESSION|%s|%s" % (path, got_comp))
        want = st["reference_settings"][ref]
        bad = sorted(k for k in names if props[k] != want[k])
        require(not bad, "TEXTURE_SETTINGS_DIFFER_FROM_REFERENCE|%s|%s"
                % (path, json.dumps({k: [props[k], want[k]] for k in bad})))
        if size != SIZES[path]:
            require(max(size) <= 32, "TEXTURE_SIZE|%s|%s" % (path, size))                   # [ref:218-221]
            pending.append(path)
        out[path] = {"size": size, "srgb": srgb, "compression": str(got_comp), "settings": props}
    if dry:
        log("GV2_VERIFY_TEX_DRY_RUN_OK|run=%s|%s|mutated=0" % (run, json.dumps(out)))
        return
    if pending:
        u.log_warning("GV2_VERIFY_TEX_PENDING|run=%s|placeholder=%s|retry VERIFY_TEX" % (run, pending))
        return
    st.update({"verified": True, "verify_run": run, "readback": out})
    write_record(rec)
    log("GV2_VERIFY_TEX_SUCCESS|run=%s|atlas=%s|normal=%s|srgb=0|flip_green=%s"
        % (run, out[ATLAS_V2]["size"], out[NORMAL_V2]["size"], out[NORMAL_V2]["settings"]["flip_green_channel"]))


# ============================================================================================ MI state
def load_worklist():                                                                        # [ref:407-415]
    p = proj(*REF_DIR, WORKLIST_NAME)
    require(os.path.isfile(p) and sha256(p) == WORKLIST_SHA256, "WORKLIST_SHA256_MISMATCH")
    with open(p, encoding="utf-8") as fh:
        work = json.load(fh)
    require(work.get("master") == MASTER and work.get("mi_dir") == MI_DIR, "WORKLIST_MASTER")
    return work


def live_mi_paths():
    u = U()
    out = set()
    for obj_path in u.EditorAssetLibrary.list_assets(MI_DIR, recursive=False, include_folder=False):
        pkg = str(obj_path).split(".", 1)[0]
        if pkg.rsplit("/", 1)[1].startswith(MI_PREFIX):
            out.add(pkg)
    return sorted(out)


def tex_entries(mi):
    """The instance's own texture overrides (an entry IS an override: MaterialInstance.h:250)."""
    out = {}
    for e in mi.get_editor_property("texture_parameter_values"):                            # hp_marble_probe.py:18
        out[str(e.parameter_info.name)] = path_of(e.parameter_value)
    return out


def mi_state(mi):
    u = U()
    mel = u.MaterialEditingLibrary
    entries = tex_entries(mi)
    tex = {}
    for n in PARAMS:
        tex[n] = {"override": n in entries,
                  "override_value": entries.get(n),
                  "probe_override": bool(mel.is_material_instance_parameter_overridden(mi, n)),
                  "value": path_of(mel.get_material_instance_texture_parameter_value(mi, n))}
    return {"parent": path_of(mi.get_editor_property("parent")),
            "tex": tex,
            "tex_override_names": sorted(entries),
            "scalar_override_names": sorted(str(e.parameter_info.name)
                                            for e in mi.get_editor_property("scalar_parameter_values")),
            "scalars": {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in MASTER_SCALARS}}


def target_param(name):
    v2 = PARAMS[name][1]
    return {"override": True, "override_value": v2, "probe_override": True, "value": v2}


def param_equal(a, b):
    return all(a[k] == b[k] for k in ("override", "override_value", "probe_override", "value"))


def common_diffs(state, orig):
    """Differences OUTSIDE the two target params (must never change)."""
    bad = []
    if state["parent"] != orig["parent"]:
        bad.append("PARENT")
    if state["scalar_override_names"] != orig["scalar_override_names"]:
        bad.append("SCALAR_OVERRIDE_SET")
    others = sorted(set(state["tex_override_names"]) - set(PARAMS))
    if others != sorted(set(orig["tex_override_names"]) - set(PARAMS)):
        bad.append("OTHER_TEXTURE_OVERRIDES")
    for k in MASTER_SCALARS:
        if abs(state["scalars"][k] - orig["scalars"][k]) > EPS:
            bad.append("SCALAR:%s:%r!=%r" % (k, state["scalars"][k], orig["scalars"][k]))
    return bad


def classify(state, orig, pinned=None):
    """Per param: 'orig' | 'v2' | 'pinned' (revert fallback) | None (drift)."""
    out = {}
    for n in PARAMS:
        s = state["tex"][n]
        if param_equal(s, orig["tex"][n]):
            out[n] = "orig"
        elif param_equal(s, target_param(n)):
            out[n] = "v2"
        elif pinned and n in pinned and s["override"] and s["override_value"] == orig["tex"][n]["value"] \
                and s["value"] == orig["tex"][n]["value"]:
            out[n] = "pinned"
        else:
            out[n] = None
    return out


def protected_files():
    """Every file under Content/Scenes/Scene3/HandPrints except the g1 MIs and the two v2 textures."""
    root = proj("Content", "Scenes", "Scene3", "HandPrints")
    targets = {os.path.normcase(f) for f in (content_file(ATLAS_V2), content_file(NORMAL_V2))}
    pdir = project_dir()
    out = {}
    for f in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
        if not os.path.isfile(f):
            continue
        base = os.path.basename(f)
        if os.path.normcase(os.path.dirname(f)) == os.path.normcase(proj("Content", *MI_DIR[len("/Game/"):].split("/"))) \
                and base.startswith(MI_PREFIX):
            continue
        if os.path.normcase(os.path.splitext(f)[0] + ".uasset") in targets:
            continue
        out[os.path.relpath(f, pdir).replace("\\", "/")] = sha256(f)
    return out


def protected_readback():
    """UE read-back of the materials that must NOT change: grease master, tint master, visible print decal v3 + MIs."""
    u = U()
    mel = u.MaterialEditingLibrary
    out = {}
    m = u.load_asset(MASTER)
    require(isinstance(m, u.Material), "MASTER_MISSING")
    out["master_textures"] = sorted(str(n) for n in mel.get_texture_parameter_names(m))
    out["master_scalars"] = sorted(str(n) for n in mel.get_scalar_parameter_names(m))
    for n in PARAMS:
        out["master_default:" + n] = path_of(mel.get_material_default_texture_parameter_value(m, n))
    m = u.load_asset(TINT_MASTER)
    out["tint_default:GreaseMask"] = path_of(mel.get_material_default_texture_parameter_value(m, "GreaseMask")) \
        if isinstance(m, u.Material) else "MISSING"
    m = u.load_asset(PRINT_MASTER_V3)
    out["print_v3_default:" + PRINT_NORMAL_PARAM] = path_of(
        mel.get_material_default_texture_parameter_value(m, PRINT_NORMAL_PARAM)) if isinstance(m, u.Material) else "MISSING"
    m = None
    v3 = {}
    for obj_path in u.EditorAssetLibrary.list_assets(PRINT_V3_DIR, recursive=False, include_folder=False):
        pkg = str(obj_path).split(".", 1)[0]
        mi = u.load_asset(pkg)
        if isinstance(mi, u.MaterialInstanceConstant):
            v3[pkg.rsplit("/", 1)[1]] = path_of(mel.get_material_instance_texture_parameter_value(mi, PRINT_NORMAL_PARAM))
        mi = None
    out["print_v3_mi_count"] = len(v3)
    out["print_v3_mi_normal_values"] = sorted(set(v3.values()), key=str)
    out["print_v3_mi_digest"] = hashlib.sha256(json.dumps(sorted(v3.items()), sort_keys=True).encode()).hexdigest()
    return out


def assert_protected(snap, label):
    files = protected_files()
    want = snap["protected"]["files"]
    changed = sorted(k for k in set(files) | set(want) if files.get(k) != want.get(k))
    require(not changed, "PROTECTED_FILES_CHANGED_%s|%d|%s" % (label, len(changed), json.dumps(changed[:8])))
    rb = protected_readback()
    bad = sorted(k for k in set(rb) | set(snap["protected"]["readback"]) if rb.get(k) != snap["protected"]["readback"].get(k))
    require(not bad, "PROTECTED_READBACK_CHANGED_%s|%s" % (label, json.dumps({k: [rb.get(k), snap["protected"]["readback"].get(k)]
                                                                               for k in bad[:6]})))
    return len(files)


# ============================================================================================ SNAPSHOT
def stage_snapshot(run, dry):
    u = U()
    preflight()
    rec = read_record()
    require((rec["stages"].get("import") or {}).get("verified") is True, "TEXTURES_NOT_VERIFIED")
    require("snapshot" not in rec["stages"], "SNAPSHOT_ALREADY_RECORDED")
    args = read_args()
    work = load_worklist()
    expected = sorted(i["path"] for i in work["instances"])
    with open(proj(*REF_DIR, REF_RECORD_NAME), encoding="utf-8") as fh:
        ref_rec = json.load(fh)
    ref_done = sorted(MI_DIR + "/" + n for n in ((ref_rec.get("stages") or {}).get("mi") or {}).get("done", []))
    live = live_mi_paths()
    ack = args.get("ack_mi_count")
    agree = live == expected == ref_done and len(live) == EXPECTED_MI_COUNT
    if not agree:
        require(ack is not None and int(ack) == len(live),
                "MI_SET_DIFFERS|live=%d|worklist=%d|record=%d|expected=%d|missing=%s|extra=%s|set args ack_mi_count=%d"
                " to proceed with the LIVE list" % (len(live), len(expected), len(ref_done), EXPECTED_MI_COUNT,
                                                     json.dumps(sorted(set(expected) - set(live))[:5]),
                                                     json.dumps(sorted(set(live) - set(expected))[:5]), len(live)))
    require(live, "NO_MIS")
    mel = u.MaterialEditingLibrary
    m = u.load_asset(MASTER)
    require(isinstance(m, u.Material), "MASTER_MISSING")
    scal = sorted(str(n) for n in mel.get_scalar_parameter_names(m))
    texn = sorted(str(n) for n in mel.get_texture_parameter_names(m))
    m = None
    require(scal == MASTER_SCALARS, "MASTER_SCALARS|%s" % scal)
    require(texn == sorted(PARAMS), "MASTER_TEXTURES|%s" % texn)
    for p in (ATLAS_V2, NORMAL_V2):
        require(isinstance(u.load_asset(p), u.Texture2D), "V2_TEXTURE_MISSING|" + p)
    wl = {i["path"]: i for i in work["instances"]}
    originals, bad, scalar_vs_worklist = {}, [], []
    for p in live:
        mi = u.load_asset(p)
        if not isinstance(mi, u.MaterialInstanceConstant):
            bad.append("CLASS|" + p)
            continue
        s = mi_state(mi)
        mi = None
        if s["parent"] != MASTER:
            bad.append("PARENT|%s|%s" % (p, s["parent"]))
        for n, (v1, _v2) in PARAMS.items():
            t = s["tex"][n]
            if t["override"] != t["probe_override"]:
                bad.append("OVERRIDE_PROBES_DISAGREE|%s|%s|entry=%s|is_overridden=%s" % (p, n, t["override"], t["probe_override"]))
            if t["value"] != v1:
                bad.append("UNEXPECTED_ORIGINAL|%s|%s|%s" % (p, n, t["value"]))
        if p in wl:
            for k in MI_SCALARS:
                if abs(s["scalars"][k] - float(wl[p]["scalars"][k])) > EPS:
                    scalar_vs_worklist.append("%s|%s" % (p.rsplit("/", 1)[1], k))
        s["files"] = {os.path.basename(f): sha256(f) for f in package_files(p)}
        if not s["files"]:
            bad.append("NO_FILE|" + p)
        originals[p] = s
    require(not bad, "SNAPSHOT_REFUSED|%d|%s" % (len(bad), json.dumps(bad[:6])))
    readback = protected_readback()
    require(readback["master_default:GreaseMask"] == ATLAS_V1 and readback["master_default:PrintNormal"] == NORMAL_V1,
            "MASTER_DEFAULTS|%s" % json.dumps(readback))
    files = protected_files()
    batches = [live[i:i + MI_BATCH_MAX] for i in range(0, len(live), MI_BATCH_MAX)]
    overrides = {n: sum(1 for s in originals.values() if s["tex"][n]["override"]) for n in PARAMS}
    if dry:
        end_clean()
        log("GV2_SNAPSHOT_DRY_RUN_OK|run=%s|mis=%d|batches=%d|already_overridden=%s|protected_files=%d|"
            "print_v3_mis=%d|scalars_vs_worklist=%d|mutated=0"
            % (run, len(live), len(batches), json.dumps(overrides), len(files), readback["print_v3_mi_count"],
               len(scalar_vs_worklist)))
        return
    backup = backup_files("PreHPGreaseV2-", run, [f for p in live for f in package_files(p)])
    end_clean()
    rec["stages"]["snapshot"] = {"run": run, "utc": utc(), "mi_count": len(live), "ack_mi_count": ack,
                                 "backup": backup, "batches": batches, "originals": originals,
                                 "scalars_differ_from_worklist": scalar_vs_worklist,
                                 "protected": {"files": files, "readback": readback}}
    write_record(rec)
    collect_garbage()
    log("GV2_SNAPSHOT_SUCCESS|run=%s|mis=%d|batches=%d|already_overridden=%s|protected_files=%d|backup=%s"
        % (run, len(live), len(batches), json.dumps(overrides), len(files), backup))


# ============================================================================================ APPLY / REVERT
def next_batch(snap, st):                                                                   # [ref:418-424]
    if st.get("in_progress"):
        return st["in_progress_batch"]
    done = set(st["done"])
    for i, b in enumerate(snap["batches"]):
        if any(p not in done for p in b):
            return i
    return None


def stage_batch(run, dry, kind):
    """kind = 'apply' | 'revert'."""
    u = U()
    preflight()
    rec = read_record()
    snap = rec["stages"].get("snapshot")
    require(snap is not None, "NO_SNAPSHOT")
    require((rec["stages"].get("import") or {}).get("verified") is True, "TEXTURES_NOT_VERIFIED")
    args = read_args()
    pin_fallback = bool(args.get("revert_pin_fallback")) and kind == "revert"
    if kind == "apply":
        require("revert" not in rec["stages"], "REVERT_ALREADY_STARTED|archive the record before re-applying")
    else:
        require("apply" in rec["stages"], "NOTHING_APPLIED")
        if rec["stages"]["apply"].get("in_progress"):
            u.log_warning("GV2_REVERT_NOTE|run=%s|apply batch %s was interrupted; reverting what is live"
                          % (run, rec["stages"]["apply"].get("in_progress_batch")))
    if not dry:
        require(CONFIRM_GIVEN == CONFIRM[kind.upper()], "CONFIRM_MISSING|need GV2_CONFIRM=%r" % CONFIRM[kind.upper()])
    st = rec["stages"].get(kind) or {"done": [], "in_progress": [], "in_progress_batch": None, "batches": [],
                                     "verified": False}
    b = next_batch(snap, st)
    TAG = "GV2_" + kind.upper()
    if b is None:
        log("%s_NOTHING_TO_DO|run=%s|done=%d|send %s_VERIFY" % (TAG, run, len(st["done"]), kind.upper()))
        return
    resuming = bool(st.get("in_progress"))
    batch = [p for p in snap["batches"][b] if resuming or p not in set(st["done"])]
    origs = snap["originals"]
    plan, drift = {}, []
    v2 = {n: u.load_asset(PARAMS[n][1]) for n in PARAMS}
    require(all(isinstance(t, u.Texture2D) for t in v2.values()), "V2_TEXTURE_MISSING")
    for p in batch:
        mi = u.load_asset(p)
        if not isinstance(mi, u.MaterialInstanceConstant):
            drift.append("CLASS|" + p)
            continue
        s = mi_state(mi)
        mi = None
        c = common_diffs(s, origs[p])
        cls = classify(s, origs[p], pinned=(st.get("pinned") or {}).get(p))
        if c or None in cls.values():
            drift.append("%s|%s|%s" % (p.rsplit("/", 1)[1], ",".join(c), json.dumps(cls)))
            continue
        if kind == "apply" and not resuming and any(v != "orig" for v in cls.values()):
            drift.append("NOT_ORIGINAL_OUTSIDE_RESUME|%s|%s" % (p.rsplit("/", 1)[1], json.dumps(cls)))
            continue
        plan[p] = [n for n in PARAMS if cls[n] != ("v2" if kind == "apply" else "orig")]
    require(not drift, "%s_DRIFT|%d|%s" % (kind.upper(), len(drift), json.dumps(drift[:5])))
    writes = sorted(p for p in plan if plan[p])
    ram = free_ram_gb()
    require(ram >= MIN_FREE_RAM_GB, "FREE_RAM_LOW|%.1f" % ram)                                # [ref:441-442]
    if dry:
        end_clean()
        log("%s_DRY_RUN_OK|run=%s|batch=%d|size=%d|to_write=%d|resuming=%s|done=%d|total=%d|free_ram_gb=%.1f|mutated=0"
            % (TAG, run, b, len(batch), len(writes), resuming, len(st["done"]), snap["mi_count"], ram))
        return
    st["in_progress"] = list(batch)
    st["in_progress_batch"] = b
    rec["stages"][kind] = st
    write_record(rec)                                                       # BEFORE the first mutation [ref:448-449]
    mel = u.MaterialEditingLibrary
    pinned_now = {}
    for p in writes:
        mi = u.load_asset(p)
        mi.modify()
        for n in plan[p]:
            o = origs[p]["tex"][n]
            if kind == "apply":
                mel.set_material_instance_texture_parameter_value(mi, n, v2[n])   # the bool may lie: read back below
            elif o["override"]:
                mel.set_material_instance_texture_parameter_value(mi, n, u.load_asset(o["override_value"]))
            elif pin_fallback:
                mel.set_material_instance_texture_parameter_value(mi, n, u.load_asset(o["value"]))
                pinned_now.setdefault(p, []).append(n)
            else:
                mel.set_material_instance_parameter_override(mi, n, False)        # clear: inherited again
        mel.update_material_instance(mi)                                                    # [ref:464]
        mi = None

    def check(label):
        bad = []
        for p in batch:
            mi = u.load_asset(p)
            s = mi_state(mi)
            mi = None
            c = common_diffs(s, origs[p])
            pins = sorted(set((st.get("pinned") or {}).get(p, [])) | set(pinned_now.get(p, [])))
            cls = classify(s, origs[p], pinned=pins)
            want = "v2" if kind == "apply" else "orig"
            wrong = {n: v for n, v in cls.items() if v != want and not (v == "pinned" and n in pins)}
            if c or wrong:
                bad.append("%s|%s|%s" % (p.rsplit("/", 1)[1], ",".join(c), json.dumps(wrong)))
        require(not bad, "READBACK_%s|%d|%s|NOTHING SAVED in this step if BEFORE_SAVE: Don't-Save restart, re-run"
                % (label, len(bad), json.dumps(bad[:5])))
    check("BEFORE_SAVE")
    census_exact(writes, "BEFORE_SAVE")                                   # exactly the written MI packages
    for p in writes:
        require(u.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), "SAVE_FAILED|" + p)    # [ref:465]
    end_clean()
    check("AFTER_SAVE")
    n_files = assert_protected(snap, "AFTER_SAVE")
    v2 = None
    if pinned_now:
        st.setdefault("pinned", {})
        for p, ns in pinned_now.items():
            st["pinned"][p] = sorted(set(st["pinned"].get(p, [])) | set(ns))
    st["done"] = sorted(set(st["done"]) | set(batch))
    st["in_progress"] = []
    st["in_progress_batch"] = None
    st["batches"].append({"run": run, "batch": b, "names": [p.rsplit("/", 1)[1] for p in batch],
                          "written": len(writes), "resumed": resuming, "free_ram_gb": round(ram, 2),
                          "pinned": sorted(pinned_now)})
    write_record(rec)
    collect_garbage()
    log("%s_BATCH_DONE|run=%s|batch=%d|written=%d|done=%d|remaining=%d|protected_files=%d|pinned=%d|NOT_YET_VERIFIED"
        % (TAG, run, b, len(writes), len(st["done"]), snap["mi_count"] - len(st["done"]), n_files, len(pinned_now)))


def stage_verify(run, dry, kind):
    u = U()
    preflight(clean=False)
    rec = read_record()
    snap = rec["stages"].get("snapshot") or {}
    st = rec["stages"].get(kind) or {}
    allp = sorted(snap.get("originals") or {})
    require(allp and set(st.get("done") or []) == set(allp) and not st.get("in_progress"),
            "%s_NOT_COMPLETE" % kind.upper())
    if dry:
        log("GV2_%s_VERIFY_DRY_RUN_OK|run=%s|n=%d|mutated=0" % (kind.upper(), run, len(allp)))
        return
    bad = []
    want = "v2" if kind == "apply" else "orig"
    pinned = st.get("pinned") or {}
    for p in allp:
        mi = u.load_asset(p)
        if not isinstance(mi, u.MaterialInstanceConstant):
            bad.append("CLASS|" + p)
            continue
        s = mi_state(mi)
        mi = None
        c = common_diffs(s, snap["originals"][p])
        cls = classify(s, snap["originals"][p], pinned=pinned.get(p))
        wrong = {n: v for n, v in cls.items() if v != want and not (v == "pinned" and n in pinned.get(p, []))}
        if c or wrong:
            bad.append("%s|%s|%s" % (p.rsplit("/", 1)[1], ",".join(c), json.dumps(wrong)))
    if bad:
        st["verify_failures"] = bad[:20]
        write_record(rec)
        raise StageError("%s_VERIFY|%d|%s" % (kind.upper(), len(bad), json.dumps(bad[:5])))
    n_files = assert_protected(snap, "VERIFY")
    end_clean()                                                                             # [ref:509]
    st.update({"verified": True, "verify_run": run, "verified_count": len(allp)})
    write_record(rec)
    collect_garbage()
    log("GV2_%s_SUCCESS|run=%s|verified=%d|protected_files=%d|pinned=%d"
        % (kind.upper(), run, len(allp), n_files, len(pinned)))


# ============================================================================================ main
def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")                                 # [ref:517]
    modes = {"IMPORT": lambda r, d: stage_import(r, d), "VERIFY_TEX": lambda r, d: stage_verify_tex(r, d),
             "SNAPSHOT": lambda r, d: stage_snapshot(r, d),
             "APPLY": lambda r, d: stage_batch(r, d, "apply"), "APPLY_VERIFY": lambda r, d: stage_verify(r, d, "apply"),
             "REVERT": lambda r, d: stage_batch(r, d, "revert"),
             "REVERT_VERIFY": lambda r, d: stage_verify(r, d, "revert")}
    mode = str(MODE)
    dry = mode.endswith("_DRY")
    base = mode[:-4] if dry else mode
    try:
        require(base in modes, "GV2_MODE_NOT_SET|%s" % MODE)
        modes[base](run, dry)
    except StageError as exc:                                                               # [ref:523-529]
        U().log_error("GV2_%s_STOPPED|run=%s|reason=%s|census=%s" % (mode, run, exc, json.dumps(census())))
    except Exception:
        U().log_error("GV2_%s_ERROR|run=%s|traceback=%s|census=%s"
                      % (mode, run, traceback.format_exc().replace("\n", "\\n"), json.dumps(census())))


if MODE is not None:
    main()
