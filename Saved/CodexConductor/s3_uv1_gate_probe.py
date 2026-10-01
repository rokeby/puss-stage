"""READ-ONLY: run s3_flats_import.verify_uv1_metres on the in-memory (unsaved) wave meshes."""
import ast
import os

import unreal


def _run():
    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    source = open(os.path.join(here, "s3_flats_import.py"), encoding="utf-8").read()
    tree = ast.parse(source)
    func = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ("verify_uv1_metres", "_polygon_instances")]
    namespace = {"unreal": unreal}
    exec(compile(ast.Module(body=func, type_ignores=[]), "verify_uv1_metres", "exec"), namespace)
    desc = unreal.load_asset("/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_WaveRow1_A").get_static_mesh_description(0)
    names = sorted(n for n in dir(desc) if any(k in n for k in ("polygon", "vertex_instance", "vertex_position", "triangle")))
    unreal.log("S3_UV1_GATE_API|" + ",".join(names))
    results = []
    for row in (1, 2, 3):
        for half in ("A", "B"):
            path = "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_WaveRow%d_%s" % (row, half)
            mesh = unreal.load_asset(path)
            for lod in (0, 1):
                try:
                    namespace["verify_uv1_metres"](mesh, lod)
                    results.append("%s_%d:PASS" % (path.rsplit("_", 2)[-2] + path[-1], lod))
                except Exception as exc:
                    results.append("%s|lod=%d:FAIL:%s" % (path, lod, exc))
    unreal.log("S3_UV1_GATE_PROBE|" + " ; ".join(results))


_run()
