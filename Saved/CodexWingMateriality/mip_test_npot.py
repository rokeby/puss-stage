"""Mip test on DUPLICATES (conductor-approved, 30 Sep): do non-power-of-two wing textures get
mips in UE 5.8 at native size (option a), or do they need StretchToPowerOfTwo (option b)?

Phase via mip_test_request.json {"phase": "setup" | "read"}:
  setup  duplicate one RGBA-alpha wing texture and one height map into
         /Game/Scenes/Wings/PaintedSurface/MipTest/, set MipGen = FromTextureGroup with
         PowerOfTwoMode = None (option a), save only the duplicates. Nothing live is touched.
  read   report size, settings and built mip count for the duplicates and their live
         originals, by every route this build exposes (direct calls, then ListTextures).
"""
import importlib.util, os, re
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)

TEST = "/Game/Scenes/Wings/PaintedSurface/MipTest"
SOURCES = {
    "rgba_alpha": "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2/Textures/T_P02_SET01_L",
    "height": "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2/Textures/T_P02_SET01_L_H",
}


def dup_path(kind):
    return f"{TEST}/MIPTEST_{kind}"


def mip_count(tex):
    for name in ("get_num_mips", "blueprint_get_num_mips", "get_num_mips_allowed"):
        fn = getattr(tex, name, None)
        if fn:
            try:
                return name, int(fn())
            except Exception as exc:  # noqa: BLE001
                return name, f"ERR {exc!r}"[:80]
    return None, None


def describe(tex):
    rec = {"size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]}
    for p in ("mip_gen_settings", "power_of_two_mode", "compression_settings", "lod_group", "never_stream"):
        try:
            rec[p] = str(tex.get_editor_property(p))
        except Exception as exc:  # noqa: BLE001
            rec[p] = f"ERR {exc!r}"[:60]
    rec["mips_via"], rec["mips"] = mip_count(tex)
    return rec


wm.editor_ready()
before = wm.dirty()
phase = wm.read_json("mip_test_request.json")["phase"]
out = {"phase": phase}
# Resolve enum values first, so a naming difference in this build fails before anything is created.
POW2_NONE = getattr(unreal.TexturePowerOfTwoSetting, "NONE", None)
MIP_FROM_GROUP = getattr(unreal.TextureMipGenSettings, "TMGS_FROM_TEXTURE_GROUP", None)
wm.require(POW2_NONE is not None and MIP_FROM_GROUP is not None,
           f"enum names: {[n for n in dir(unreal.TexturePowerOfTwoSetting) if n.isupper()][:8]} / "
           f"{[n for n in dir(unreal.TextureMipGenSettings) if n.startswith('TMGS')][:6]}")
if phase == "setup":
    for kind, src in SOURCES.items():
        dst = dup_path(kind)
        wm.require(dst.startswith("/Game/Scenes/Wings/PaintedSurface/"), "test assets must live in our folder")
        if not unreal.EditorAssetLibrary.does_asset_exist(dst):
            wm.require(unreal.EditorAssetLibrary.duplicate_asset(src, dst) is not None, f"duplicate {kind} failed")
        tex = unreal.EditorAssetLibrary.load_asset(dst)
        out[kind + "_before"] = describe(tex)
        tex.set_editor_property("power_of_two_mode", POW2_NONE)
        tex.set_editor_property("mip_gen_settings", MIP_FROM_GROUP)
        wm.require(unreal.EditorAssetLibrary.save_asset(dst, only_if_is_dirty=False), f"save {dst}")
    after = wm.dirty()
    wm.require(set(after) <= set(before), f"test left new dirty packages: {sorted(set(after) - set(before))}")
else:
    for kind, src in SOURCES.items():
        out[kind + "_live_original"] = describe(unreal.EditorAssetLibrary.load_asset(src))
        out[kind + "_duplicate"] = describe(unreal.EditorAssetLibrary.load_asset(dup_path(kind)))
    # Fallback that doesn't depend on Python exposure: the engine's own texture listing.
    unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), "ListTextures")
    wm.require(wm.dirty() == before, "dirty changed during read")
wm.write_json(f"mip_test_{phase}.json", out)
unreal.log(f"PUSS_WING_MIPTEST_{phase.upper()}_SUCCESS")
