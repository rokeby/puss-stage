"""Create-only Klara S2 Variant B MIs. Offline-written; run later in Unreal via the guarded Saved/ route.

DRY/APPLY/REVERT confirmations are '<MODE> S2KVARIANTB'. Klara's MI and parent are read-only. APPLY creates exactly
six packages; REVERT permanently deletes exactly those six recorded create-only packages and therefore requires the
explicit REVERT confirmation. Every write backs up first, gates the dirty-package census, saves only named packages,
reads back, and emits S2KVARB_<MODE>_OK|run=...
"""
import datetime
import importlib.util
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
ARGS = os.path.join(HERE, "s2k_variantB_mis_args.json")
RECORD = os.path.join(HERE, "s2k_variantB_mis_record.json")


def core():
    p = os.path.join(HERE, "s2k_variantB_mis_core.py")
    s = importlib.util.spec_from_file_location("s2k_variantB_mis_core_live", p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True); f.write("\n")


def apath(obj):
    return str(obj.get_path_name()).split(".")[0] if obj is not None else None


def load(path, cls=None):
    obj = unreal.load_asset(path)
    if obj is None or (cls is not None and not isinstance(obj, cls)):
        raise RuntimeError("LOAD|%s" % path)
    return obj


def census():
    content = sorted(str(x.get_name()).split(".")[0] for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    maps = sorted(str(x.get_name()).split(".")[0] for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    return {"content": content, "maps": maps}


def content_file(package):
    return os.path.join(PROJECT, "Content", *package[6:].split("/")) + ".uasset"


def backup(run, files):
    folder = os.path.join(PROJECT, "Backups", "PreS2KVariantB-" + run)
    if os.path.exists(folder):
        raise RuntimeError("BACKUP_EXISTS|" + folder)
    os.makedirs(folder)
    copied = []
    for src in files:
        if src and os.path.isfile(src):
            dst = os.path.join(folder, os.path.basename(src)); shutil.copy2(src, dst); copied.append(dst)
    write(os.path.join(folder, "backup.json"), {"run": run, "files": copied})
    return folder


def source_values(mi):
    mel = unreal.MaterialEditingLibrary
    out = {"scalar": {}, "vector": {}, "texture": {}, "switch": {}}
    for n in mel.get_scalar_parameter_names(mi):
        out["scalar"][str(n)] = float(mel.get_material_instance_scalar_parameter_value(mi, n))
    for n in mel.get_vector_parameter_names(mi):
        v = mel.get_material_instance_vector_parameter_value(mi, n)
        out["vector"][str(n)] = [float(v.r), float(v.g), float(v.b), float(v.a)]
    for n in mel.get_texture_parameter_names(mi):
        out["texture"][str(n)] = apath(mel.get_material_instance_texture_parameter_value(mi, n))
    for n in mel.get_static_switch_parameter_names(mi):
        out["switch"][str(n)] = bool(mel.get_material_instance_static_switch_parameter_value(mi, n))
    return out


def set_values(mi, values):
    mel = unreal.MaterialEditingLibrary
    for n, v in values["scalar"].items(): mel.set_material_instance_scalar_parameter_value(mi, n, float(v))
    for n, v in values["vector"].items(): mel.set_material_instance_vector_parameter_value(mi, n, unreal.LinearColor(*v))
    for n, v in values["texture"].items():
        if v: mel.set_material_instance_texture_parameter_value(mi, n, load(v, unreal.Texture))
    for n, v in values["switch"].items(): mel.set_material_instance_static_switch_parameter_value(mi, n, bool(v))


def state(C):
    mel = unreal.MaterialEditingLibrary; out = {}
    for row in C.rows():
        if not unreal.EditorAssetLibrary.does_asset_exist(row["target"]): continue
        mi = load(row["target"], unreal.MaterialInstanceConstant)
        names = [str(n) for n in mel.get_static_switch_parameter_names(mi)]
        out[row["target"]] = {"parent": apath(mi.get_editor_property("parent")),
            "PaperMap": apath(mel.get_material_instance_texture_parameter_value(mi, "PaperMap")),
            "UsePaperMap": bool(mel.get_material_instance_static_switch_parameter_value(mi, "UsePaperMap")) if "UsePaperMap" in names else None,
            "UseAlphaCutout": bool(mel.get_material_instance_static_switch_parameter_value(mi, "UseAlphaCutout")) if "UseAlphaCutout" in names else None,
            "values": source_values(mi)}
    return out


def plan(C):
    src = load(C.SOURCE_MI, unreal.MaterialInstanceConstant)
    parent = apath(src.get_editor_property("parent")); values = source_values(src)
    if parent != C.EXPECTED_PARENT: raise RuntimeError("SOURCE_PARENT|%s" % parent)
    for row in C.rows(): load(row["skin"], unreal.Texture)
    return {"rows": C.rows(), "parent": parent, "source_values": values,
            "digest": C.plan_digest(parent, values), "existing": sorted(state(C))}


def main():
    C = core(); args = globals().get("S2KVARB_ARGS") or read(ARGS)
    run = str(args.get("run") or "S2KVARB-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    try:
        bad = C.validate_args(args)
        if bad: raise RuntimeError("ARGS|" + ",".join(bad))
        if census() != {"content": [], "maps": []}: raise RuntimeError("DIRTY_BEFORE|%s" % census())
        p = plan(C)
        if mode == "DRY":
            if p["existing"]: raise RuntimeError("CREATE_ONLY_TARGETS_EXIST|%s" % p["existing"])
            out = os.path.join(HERE, "s2k_variantB_mis_dry_%s.json" % run); write(out, p)
            unreal.log("%s_DRY_OK|run=%s|packages=6|digest=%s|out=%s" % (C.MARK, run, p["digest"], out)); return
        if mode == "APPLY":
            dry = read(os.path.join(HERE, str(args.get("dry_report") or "")))
            if p["existing"]: raise RuntimeError("CREATE_ONLY_TARGETS_EXIST|%s" % p["existing"])
            if dry.get("digest") != p["digest"]: raise RuntimeError("PLAN_CHANGED_SINCE_DRY")
            rec = {"run": run, "applied": False, "targets": [r["target"] for r in p["rows"]], "digest": p["digest"],
                   "source_values": p["source_values"]}
            write(RECORD, rec)
            rec["backup"] = backup(run, [content_file(C.SOURCE_MI), content_file(C.EXPECTED_PARENT), RECORD] +
                                            [content_file(r["skin"]) for r in p["rows"]]); write(RECORD, rec)
            source = load(C.SOURCE_MI, unreal.MaterialInstanceConstant); parent = load(C.EXPECTED_PARENT, unreal.Material)
            made = []
            for row in p["rows"]:
                folder, name = row["target"].rsplit("/", 1)
                mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.MaterialInstanceConstant,
                                                                              unreal.MaterialInstanceConstantFactoryNew())
                if mi is None: raise RuntimeError("CREATE|" + row["target"])
                unreal.MaterialEditingLibrary.set_material_instance_parent(mi, parent)
                set_values(mi, p["source_values"])
                unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "PaperMap", load(row["skin"], unreal.Texture))
                unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(mi, "UsePaperMap", True)
                unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(mi, "UseAlphaCutout", False)
                mi.set_editor_property("base_property_overrides", source.get_editor_property("base_property_overrides"))
                unreal.MaterialEditingLibrary.update_material_instance(mi); made.append(row["target"])
            if sorted(census()["content"]) != sorted(made) or census()["maps"]: raise RuntimeError("DIRTY_SCOPE|%s" % census())
            for path in made:
                if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False): raise RuntimeError("SAVE|" + path)
            got = state(C); problems = C.state_problems(got, p["source_values"])
            if problems or census() != {"content": [], "maps": []}: raise RuntimeError("READBACK|%s|%s" % (problems, census()))
            rec.update(applied=True, state=got); write(RECORD, rec)
            unreal.log("%s_APPLY_OK|run=%s|packages=6|backup=%s" % (C.MARK, run, rec["backup"])); return
        rec = read(RECORD)
        if sorted(rec.get("targets") or []) != sorted(r["target"] for r in C.rows()) or C.state_problems(
                state(C), rec.get("source_values")):
            raise RuntimeError("REVERT_STATE_DRIFTED")
        b = backup(run + "-REVERT", [content_file(p) for p in rec["targets"]] + [RECORD])
        for path in reversed(rec["targets"]):
            if not unreal.EditorAssetLibrary.delete_asset(path): raise RuntimeError("DELETE_FAILED|" + path)
        if state(C) or census() != {"content": [], "maps": []}: raise RuntimeError("REVERT_READBACK|%s|%s" % (state(C), census()))
        os.replace(RECORD, RECORD + ".reverted-" + run)
        unreal.log("%s_REVERT_OK|run=%s|deleted=6|backup=%s" % (C.MARK, run, b))
    except Exception as exc:
        unreal.log_error("%s_FAILED|run=%s|mode=%s|%s: %s" % (C.MARK, run, mode, type(exc).__name__, exc)); raise


if __name__ == "__main__" and unreal is not None:
    main()
