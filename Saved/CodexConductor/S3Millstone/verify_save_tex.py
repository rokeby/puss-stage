"""Verify-then-save for textures imported by s3_props IMPORT_TEX that failed only on a first-load size read.
Saves ONLY the listed packages, only if each reads its expected size and the census holds exactly them."""
import unreal
EXPECT = {"/Game/InfinityStage/Dev/Generated/S3Props/GraniteMillstone/T_GraniteMillstone_N": 4096,
          "/Game/InfinityStage/Dev/Generated/S3Props/GraniteMillstone/T_GraniteMillstone_Roughness": 4096}
lib = unreal.EditorLoadingAndSavingUtils
dirty = sorted(p.get_name() for p in lib.get_dirty_content_packages())
maps = [p.get_name() for p in lib.get_dirty_map_packages()]
bad = []
if dirty != sorted(EXPECT) or maps:
    bad.append("CENSUS|%s|%s" % (dirty, maps))
for path, want in EXPECT.items():
    t = unreal.load_asset(path)
    sx, sy = (int(t.blueprint_get_size_x()), int(t.blueprint_get_size_y())) if t else (0, 0)
    if (sx, sy) != (want, want):
        bad.append("SIZE|%s|%dx%d" % (path.split('/')[-1], sx, sy))
if bad:
    unreal.log_error("S3PROPS_TEXSAVE_FAILED|" + "|".join(bad))
else:
    for path in EXPECT:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            unreal.log_error("S3PROPS_TEXSAVE_FAILED|SAVE|" + path)
            raise SystemExit
    after = sorted(p.get_name() for p in lib.get_dirty_content_packages())
    if after:
        unreal.log_error("S3PROPS_TEXSAVE_FAILED|DIRTY_AFTER|%s" % after)
    else:
        unreal.log("S3PROPS_TEXSAVE_OK|saved=2|sizes=4096")
