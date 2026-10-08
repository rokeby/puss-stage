"""Read-only: in-memory MI scalar values + dirty census. Marker MIPROBE|run=..."""
import datetime, json
import unreal
run = datetime.datetime.now().strftime("%H%M%S")
mel = unreal.MaterialEditingLibrary
out = {}
for p, names in {"/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/MI_PearlClam_Mantle": ["BreathAmp", "BreathPeriod", "RoughnessMultiplier"],
                 "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/MI_PearlClam_Pearl_v2": ["BreathAmp", "BreathPeriod"]}.items():
    mi = unreal.EditorAssetLibrary.load_asset(p)
    out[p.rsplit("/", 1)[1]] = {n: round(float(mel.get_material_instance_scalar_parameter_value(mi, n)), 4) for n in names}
els = unreal.EditorLoadingAndSavingUtils
content = [str(x.get_path_name()) for x in els.get_dirty_content_packages()]
maps = [str(x.get_path_name()) for x in els.get_dirty_map_packages()]
unreal.log("MIPROBE|run=%s|%s|content=%s|maps=%s" % (run, json.dumps(out), content, maps))
