"""READ-ONLY (30 Sep): what floor is under the drape at P03's mouth, and at what height?

The Interaction 2 drape plays final13, a cache world-true for P01's stage front (floor z 0, lip x -150, fascia to -120).
It is placed at P03's route start (0, 160000, 0), yaw 0. The Wet Ground landscape was deleted at 16:36; Rig's 13:04
inventory has a 535.6 m oak plane at P03. This lists every level actor whose bounds overlap a box around the mouth
(x -2000..+1500, y 158000..162000, z -300..+300 cm), with its class, label, bounds and TOP z, so the site table gets
the real number. Also P03's Passage actor z (the fit places the drape there). Nothing is modified.
Writes probe_p03_floor.json; logs PUSS_SOFTGOODS_P03_FLOOR|... Crash rules: everything inside main().
"""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
BOX = ((-2000.0, 1500.0), (158000.0, 162000.0), (-300.0, 300.0))


def main():
    dirty0 = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    rows = []
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        try:
            origin, extent = a.get_actor_bounds(False)
        except Exception:  # noqa: BLE001
            continue
        lo = (origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
        hi = (origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
        if any(hi[k] < BOX[k][0] or lo[k] > BOX[k][1] for k in range(3)):
            continue
        if extent.x < 100 and extent.y < 100:            # small props are not floors
            continue
        rows.append({"label": a.get_actor_label(), "class": a.get_class().get_name(),
                     "top_z_cm": round(hi[2], 2), "bottom_z_cm": round(lo[2], 2),
                     "x_cm": [round(lo[0], 1), round(hi[0], 1)], "y_cm": [round(lo[1], 1), round(hi[1], 1)]})
    rows.sort(key=lambda r: -r["top_z_cm"])
    passages = [{"label": a.get_actor_label(), "z": round(a.get_actor_location().z, 2)}
                for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                if "Passage" in a.get_class().get_name() and ("03" in a.get_actor_label() or "3" in a.get_actor_label())]
    dirty1 = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    out = {"box_cm": BOX, "actors": rows, "p03_passage_actors": passages, "dirty_changed": dirty0 != dirty1}
    with open(os.path.join(HERE, "probe_p03_floor.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    unreal.log(f"PUSS_SOFTGOODS_P03_FLOOR|actors={len(rows)}|top={[(r['label'][:30], r['top_z_cm']) for r in rows[:6]]}"
               f"|passages={passages[:3]}|dirty_changed={dirty0 != dirty1}")


main()
