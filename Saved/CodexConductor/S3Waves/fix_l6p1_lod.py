"""Recover the L6Foam_P1/P2 import that failed only on a same-call LOD screen-size read ([0,0]): re-read/set in a later
call, require census == exactly this mesh, save it, read back. Marker S3WAVES_L6FIX_OK / FAILED."""
import unreal
P = "/Game/Scenes/Wings/FlatV3/Scene3/WavesV3/StaticMeshes/SM_FlatV3_S3_WaveV3_L6Foam_P2"
lib = unreal.EditorLoadingAndSavingUtils
try:
    dirty = sorted(p.get_name() for p in lib.get_dirty_content_packages())
    maps = [p.get_name() for p in lib.get_dirty_map_packages()]
    if dirty != [P] or maps:
        raise RuntimeError("CENSUS|%s|%s" % (dirty, maps))
    mesh = unreal.load_asset(P)
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    before = [float(x) for x in sme.get_lod_screen_sizes(mesh)]
    if len(before) != 2 or mesh.get_num_lods() != 2:
        raise RuntimeError("LODS|%s|%d" % (before, mesh.get_num_lods()))
    if abs(before[1] - 0.3) > 1e-4:
        sme.set_lod_screen_sizes(mesh, [before[0] if before[0] > 0 else 1.0, 0.3])
    after = [float(x) for x in sme.get_lod_screen_sizes(mesh)]
    if abs(after[1] - 0.3) > 1e-4:
        raise RuntimeError("READBACK|%s" % after)
    if not unreal.EditorAssetLibrary.save_asset(P, only_if_is_dirty=False):
        raise RuntimeError("SAVE")
    left = [p.get_name() for p in lib.get_dirty_content_packages()]
    if left:
        raise RuntimeError("DIRTY_AFTER|%s" % left)
    unreal.log("S3WAVES_L6FIX_OK|before=%s|after=%s" % (before, after))
except Exception as exc:
    unreal.log_error("S3WAVES_L6FIX_FAILED|%r" % (exc,))
