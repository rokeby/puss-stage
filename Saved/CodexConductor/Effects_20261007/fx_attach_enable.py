"""FX ATTACH ENABLE: DRY / APPLY / REVERT. Sets the Show `enabled` flag on Effect attachments whose label starts with
args.label_prefix, inside the passages in args.passages, then materializes those passages and saves the Show + level.
First use: Gary 8 Oct ~08:30 UTC, own words: "please remove the smoke machines in passage one or hide them for now ...
they currently look really, really bad" -> label_prefix "FX SMOKE P01", enabled false (hide, keep the attachment).
Reuses fx_smoke_place.py helpers (Show struct copy-back, materialize, narrow save).  Record + Backups/PreFxEnable-<run>.
Args fx_attach_enable_args.json {"mode", "confirm": "<MODE> FXENABLE", "passages": ["P01"], "label_prefix": "...",
"enabled": false}.  REVERT restores each recorded attachment's previous flag.
Markers FXENABLE_<MODE>_OK|run=.. / FXENABLE_FAILED|.."""
import importlib.util
import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "fx_attach_enable_args.json")
RECORD = os.path.join(HERE, "fx_attach_enable_record.json")
TAG_PREFIX = "InfinityStage.Attachment."


def _load_place():
    spec = importlib.util.spec_from_file_location("__fx_place_lib__", os.path.join(HERE, "fx_smoke_place.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def require(c, msg):
    if not c:
        raise RuntimeError(msg)


def _targets(P, show, passages, prefix):
    rows = []
    settings = {str(s.get_editor_property("label")): s for s in show.get_editor_property("passage_settings")}
    for pkey in passages:
        n = int(pkey[1:])
        pguid = settings["Passage %d" % n].get_editor_property("passage_guid")
        for g in show.get_wing_pair_cue_guids_in_passage(pguid):
            gt = P.C.guid_text(g)
            idx = P._cue_index(show, gt)
            unused_cue, pair = P._pair(show, idx)
            for it in pair.get_editor_property("attachments"):
                lab = str(it.get_editor_property("label"))
                if lab.startswith(prefix):
                    rows.append({"passage": pkey, "cue_guid": gt, "att_guid": P.C.guid_text(it.get_editor_property("attachment_guid")),
                                 "label": lab, "enabled": bool(it.get_editor_property("enabled"))})
    return rows


def _set(P, show, row, value):
    idx = P._cue_index(show, row["cue_guid"])
    unused_cue, pair = P._pair(show, idx)
    items = list(pair.get_editor_property("attachments"))
    hits = [i for i, it in enumerate(items) if P.C.guid_text(it.get_editor_property("attachment_guid")) == row["att_guid"]]
    require(len(hits) == 1, "NOT_FOUND|%s" % row["label"])
    it = items[hits[0]]
    it.set_editor_property("enabled", bool(value))
    items[hits[0]] = it
    P._set_pair_attachments(show, idx, items)


def _spawned(guids):
    out = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        for tag in actor.tags:
            t = str(tag)
            if t.startswith(TAG_PREFIX):
                g = t[len(TAG_PREFIX):].split("|")[-1].upper()
                if g in guids:
                    out.setdefault(g, []).append({"label": str(actor.get_actor_label()),
                                                  "hidden_game": bool(actor.get_editor_property("hidden"))})
    return out


def main():
    a = json.load(open(ARGS, encoding="utf-8"))
    mode = a["mode"]
    P = _load_place()
    run = P.C.stamp_now()
    P.C.editor_context(unreal)
    P.C.require_clean(unreal, "PRE")
    show = unreal.EditorAssetLibrary.load_asset(P.C.SHOW_PATH)
    if mode == "REVERT":
        require(os.path.exists(RECORD), "NO_RECORD")
        rec = json.load(open(RECORD, encoding="utf-8"))
        rows = rec["rows"]
        target = {r["att_guid"]: r["enabled"] for r in rows}
        passages = rec["args"]["passages"]
        prefix = rec["args"]["label_prefix"]
    else:
        passages = a["passages"]
        prefix = a["label_prefix"]
        rows = _targets(P, show, passages, prefix)
        target = {r["att_guid"]: bool(a["enabled"]) for r in rows}
    require(rows, "NO_TARGETS")
    if mode == "DRY":
        unreal.log("FXENABLE_DRY_OK|run=%s|n=%d|rows=%s|spawned=%s" % (run, len(rows), json.dumps(rows), json.dumps(_spawned(set(target)))))
        return
    require(a.get("confirm") == "%s FXENABLE" % mode, "CONFIRM")
    if mode == "APPLY":
        require(not os.path.exists(RECORD), "RECORD_EXISTS")
    bk = P.C.backup_packages(unreal, "PreFxEnable-", run, [P.C.SHOW_PATH, P.C.EXPECTED_WORLD])
    if mode == "APPLY":
        json.dump({"run": run, "args": a, "rows": rows, "backup": bk["root"]}, open(RECORD, "w", encoding="utf-8"), indent=1)
    for r in rows:
        _set(P, show, r, target[r["att_guid"]])
    now = {x["att_guid"]: x["enabled"] for x in _targets(P, show, passages, prefix)}
    require(all(now.get(g) == v for g, v in target.items()), "READBACK|%s|NOTHING SAVED; Don't-Save restart" % now)
    P._materialize(show, passages)
    census = P.C.dirty_census(unreal)
    require(census == {"content": [P.C.SHOW_PATH], "maps": [P.C.EXPECTED_WORLD]}, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % census)
    P.C.save_show_and_level(unreal)
    sp = _spawned(set(target))
    if mode == "REVERT":
        os.rename(RECORD, RECORD + ".reverted-" + run)
    unreal.log("FXENABLE_%s_OK|run=%s|n=%d|enabled=%s|spawned_after=%s|backup=%s" % (mode, run, len(rows), json.dumps(target), json.dumps(sp), bk["root"]))


try:
    main()
except Exception as exc:
    unreal.log_error("FXENABLE_FAILED|%r" % (exc,))
