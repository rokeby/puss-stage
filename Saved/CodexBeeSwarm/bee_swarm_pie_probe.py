"""READ-ONLY probe of a running swarm in PIE (sandbox or S6). Never ends PIE.

Run it TWICE, a second or more apart, while PIE is playing. Each run logs, per
swarm actor in the game world: simulated bee count, the uploaded Niagara array
lengths (GetNiagaraArrayPosition/Vector on User.BeePositions/User.BeeVelocities),
the target position, the camera bubble (minimum bee distance to the player camera),
and a hash of the first 4 positions. Two runs with DIFFERENT hashes and EQUAL array
lengths == bee count prove the C++ -> Niagara upload is live (measured).

Marker: BEE_SWARM_PIE_PROBE|run=...|actor=...|bees=...|positions=...|velocities=...|
        min_cam_cm=...|target=...|hash=...
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


def _load_common():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bs_common.py")
    spec = importlib.util.spec_from_file_location("_bs_common_pp", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load_common()


def main():
    C.require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    run = C.stamp_now()
    report_path = os.path.join(C.saved_dir(unreal), "bee_swarm_pie_probe_%s.json" % run)
    rows = []
    try:
        game = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        C.require(game is not None, "NO_PIE_WORLD|start PIE yourself; this probe never starts or ends it")
        cls = unreal.load_class(None, C.SWARM_ACTOR_CLASS)
        C.require(cls is not None, "SWARM_CLASS_MISSING")
        actors = unreal.GameplayStatics.get_all_actors_of_class(game, cls)
        C.require(len(actors) >= 1, "NO_SWARM_ACTOR_IN_PIE")
        manager = unreal.GameplayStatics.get_player_camera_manager(game, 0)
        camera = manager.get_camera_location() if manager else None
        lib = unreal.NiagaraDataInterfaceArrayFunctionLibrary
        for actor in actors:
            comp = actor.get_swarm_component()
            niagara = actor.get_niagara_component()
            positions = list(lib.get_niagara_array_position(niagara, C.USER_POSITIONS))
            velocities = list(lib.get_niagara_array_vector(niagara, C.USER_VELOCITIES))
            bees = int(comp.get_simulated_bee_count())
            target = comp.get_swarm_target_position()
            min_cam = None
            if camera is not None and positions:
                min_cam = min((p - camera).length() for p in positions)
            digest = hashlib.sha1(json.dumps([[round(p.x, 3), round(p.y, 3), round(p.z, 3)]
                                              for p in positions[:4]]).encode()).hexdigest()[:12]
            row = {"actor": actor.get_actor_label() if hasattr(actor, "get_actor_label") else actor.get_name(),
                   "bees": bees, "positions": len(positions), "velocities": len(velocities),
                   "min_cam_cm": min_cam, "target": [target.x, target.y, target.z], "hash": digest,
                   "niagara_asset": C.asset_id(niagara.get_asset())}
            rows.append(row)
            C.require(len(positions) == bees and len(velocities) == bees,
                      "ARRAY_LENGTH_MISMATCH|%s" % row)
            C.require(min_cam is None or min_cam >= 24.99, "CAMERA_BUBBLE_BREACHED|%s" % row)
            unreal.log("BEE_SWARM_PIE_PROBE|run=%s|actor=%s|bees=%d|positions=%d|velocities=%d|min_cam_cm=%s|"
                       "target=%s|hash=%s" % (run, row["actor"], bees, len(positions), len(velocities),
                                              "n/a" if min_cam is None else "%.2f" % min_cam,
                                              json.dumps(row["target"]), digest))
        C.write_json(report_path, {"ok": True, "run": run, "camera": None if camera is None else
                                   [camera.x, camera.y, camera.z], "rows": rows})
    except Exception as error:  # noqa: BLE001
        C.write_json(report_path, {"ok": False, "run": run, "rows": rows, "error": str(error)})
        unreal.log_error("BEE_SWARM_PIE_PROBE_STOPPED|run=%s|%s" % (run, error))
        raise


if __name__ == "__main__":
    main()
