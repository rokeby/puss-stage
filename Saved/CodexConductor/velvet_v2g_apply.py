"""VELVET V2G APPLY (offline-written 6 Oct 2026, NEVER RUN IN UNREAL): Gary's chosen velvet variant V2G on the
house-curtain drapes. Harness: test_velvet_v2g_apply_offline.py (system Python, fake adapter, no Unreal).

Decision: Gary 7 Oct chose bench variant V2G (relayed by the Conductor; args decided_by must carry it for APPLY).

Tiers per claim: [decl] read in a file we can open (cited), [prec] an in-repo call that ran (cited), [meas] read back
by an earlier run (cited), [inf] inferred (why stated).

WHAT IT WRITES
  1. CREATE-ONLY  /Game/Scenes/Curtain/Chaos/Materials/MI_CurtainVelvet_v2_V2G, parent MI_CurtainVelvet_v2_DeepRed.
     Overrides exactly the V2G row of velvet_v2_bench_variants.json (8 scalars, 2 vectors; pinned below, the file must
     agree). PatternWidthM / DropM are NOT overridden: they are inherited from MI_CurtainVelvet_v2_DeepRed, which copied
     them from MI_CurtainVelvet_DeepRed_Drop [decl velvet_v2_build.py:81, :501-503; meas
     velvet_v2_build_VV2-20261006-221131.json mapping_from_drop_mi 37.629/10.0]. That is how the bench showed V2G: a MID
     parented to MI_CurtainVelvet_v2_DeepRed with only the variant's keys set [decl velvet_v2_bench.py:9, :193-201].
     The gate is the read-back (values, override flags for ALL 17 parameters, parent, effective PatternWidthM/DropM ==
     the Drop MI's), never a setter bool. If the MI already exists (e.g. after a REVERT) it is REUSED only if that
     read-back passes; it is never edited.
  2. Component OverrideMaterials = [MI_V2G] * slots on every GeometryCacheComponent whose cache is
     GC_CurtainDrop_Opening, found by DISCOVERY (asset-registry referencers of the cache + a level-actor scan), and
     cross-checked against the expected set below. The cache asset and MI_CurtainVelvet_DeepRed_Drop are NOT edited:
     Rig's portal-border MI is a child of the Drop MI [decl Saved/CodexSoftGoods/apply_drape_material_b.py:2-3, :23-26]
     and the cache's own Materials slot holds the Drop MI [decl import_passing_bake.py:259-261].
     Expected (11 spawnable templates) [decl + meas]:
       LS_Opening_Curtain_Baked  "Opening Drape (baked)"  [decl Saved/CodexSoftGoods/curtain_place_opening_and_transitions.py:122-124;
                                                           meas inspect_opening_template.json geometry_cache = GC]
       LS_Interaction_0N (N=1..5) "Transition Drape (baked)" [decl fit_transition_drapes.py:31, :127-140;
                                                           meas probe_opening_cache_provenance.json gc_sections]
       LS_Interaction_0N (N=1..5) "Sleight Hangar Drape" (the hangar twin) [decl curtain_sleight.py:2059-2069;
                                                           meas curtain_sleight_record_I1..I5.json applied=true, binding_guids]
     Level actors using the cache: NONE expected [inf: import_passing_bake_mode.json place=null; passage_end_drape.py
     ("P0N End Drape (stand-in)") has no record = never applied]. Any found is listed and handled (level is saved only
     then). Any referencer the tool cannot handle (another map, a possessable GC track, a non-GeometryCacheActor
     template) REFUSES APPLY unless listed in args ignore_referencers with a reason.
  Template edit method: binding.get_object_template() -> geometry_cache_component -> set_editor_property
  ("override_materials", [...]) [prec curtain_sleight.py:1901-1904 + read-back :2192-2197, applied I1-I5 5 Oct, on a
  StaticMeshComponent]; for a GeometryCacheComponent template it is [inf]: UGeometryCacheComponent is a UMeshComponent
  [decl UE_5.8 GeometryCacheComponent.h:36, cited by curtain_image.py:21-23], and that the override wins over the
  cache's own Materials is [inf] (engine .cpp not on disk) -> the read-back also reads comp.get_material(i).
  Spawned copies only pick the template up on respawn [inf]; the run refuses while any Sequencer is open.

MODES  args file velvet_v2g_apply_args.json (runner velvet_v2g_apply_run.py):
  DRY     read-only census: every target with its CURRENT override list and effective material per slot, every
          referencer, the MI state, refusals, and a plan digest -> velvet_v2g_dry.json (+ _<run>.json).
  APPLY   confirm "APPLY V2G", decided_by non-empty, dry_digest == the live plan digest. Order: gates -> backups
          Backups/PreVelvetV2G-<run>/ (level .umap + every touched sequence .uasset) -> record velvet_v2g_record.json
          (O_EXCL, before values as asset paths) -> create MI -> set overrides -> in-memory read-back -> dirty-scope
          gate -> save ONLY touched packages -> clean census -> saved read-back -> record applied=true.
  VERIFY  read-only: MI read-back + every target reads V2G.
  REVERT  confirm "REVERT V2G": restores every target's override list EXACTLY to the record's before (entries and
          length), only where live == record after (else DRIFT refusal); targets already at before are skipped. Backup
          PreVelvetV2G-<run>-revert first. The MI is left in place (never delete anything). The record is renamed
          .reverted-<run> (.unapplied-<run> if the APPLY never completed).
Markers (run id on each): VV2G_DRY_OK | VV2G_DRY_REFUSED | VV2G_APPLY_OK | VV2G_VERIFY_OK | VV2G_REVERT_OK |
  VV2G_STOPPED (nothing written) | VV2G_FAILED (writes happened, NOTHING saved -> Don't-Save restart, never Save All) |
  VV2G_PARTIAL_SAVE (some packages saved -> run REVERT).
Rules: no PIE (refuse; never end it), expected world, no Sequencer open, no ZZ_ actors, clean census at start, never
Save All, no delete/destroy calls, no unreal objects at module level (adapter lives inside main), no reload of the level.
"""
import datetime
import hashlib
import json
import os
import shutil

TOOL = "VV2G"
FOLDER = "/Game/Scenes/Curtain/Chaos/Materials"
MI_V2G = FOLDER + "/MI_CurtainVelvet_v2_V2G"
MI_PARENT = FOLDER + "/MI_CurtainVelvet_v2_DeepRed"
DROP_MI = "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"
GC_PATH = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ_DIR = "/Game/InfinityStage/Interactions"
OPENING_SEQ = SEQ_DIR + "/LS_Opening_Curtain_Baked"
INTERACTION_SEQS = {1: "LS_Interaction_01_WashingTheBoy", 2: "LS_Interaction_02_Turnips",
                    3: "LS_Interaction_03_ForgetsHisName", 4: "LS_Interaction_04_GetsAName",
                    5: "LS_Interaction_05_BecomesKing"}                      # curtain_sleight.py:65-66
OPENING_DRAPE = "Opening Drape (baked)"
MOUTH_DRAPE = "Transition Drape (baked)"
HANGAR_DRAPE = "Sleight Hangar Drape"
EXPECTED_TEMPLATES = [(OPENING_SEQ, OPENING_DRAPE)] + \
    [("%s/%s" % (SEQ_DIR, s), name) for _, s in sorted(INTERACTION_SEQS.items()) for name in (MOUTH_DRAPE, HANGAR_DRAPE)]

# Pinned V2G (velvet_v2_bench_variants.json variants.V2G); the file must agree or the run refuses.
V2G_SCALARS = {"SheenAmount": 1.0, "Roughness": 0.72, "RimLift": 0.15, "FoldDarken": 0.5, "NapExponent": 5.0,
               "CrushAmount": 0.6, "CrushScale": 1.4, "PileNormalStrength": 0.2}
V2G_VECTORS = {"BaseColour": [0.11, 0.01, 0.015, 1.0], "SheenColour": [0.7, 0.2, 0.18, 1.0]}
INHERITED_FROM_DROP = ("PatternWidthM", "DropM")
# The master's parameter set (velvet_v2_build.py SCALARS/VECTORS/TEX; the harness parses the builder to prove it).
PARAM_SCALARS = ("SheenAmount", "RimLift", "NapExponent", "FoldDarken", "Roughness", "Specular", "PileNormalStrength",
                 "PileScale", "CrushAmount", "CrushScale", "CrushNormalStrength", "PatternWidthM", "DropM")
PARAM_VECTORS = ("BaseColour", "SheenColour")
PARAM_TEXTURES = ("PileNormal", "CrushNormal")
TOL = 1.0e-4

ARGS_NAME = "velvet_v2g_apply_args.json"
VARIANTS_NAME = "velvet_v2_bench_variants.json"
RECORD_NAME = "velvet_v2g_record.json"
DRY_NAME = "velvet_v2g_dry.json"
CONFIRM = {"APPLY": "APPLY V2G", "REVERT": "REVERT V2G"}
MODES = ("DRY", "APPLY", "VERIFY", "REVERT")


class Stop(Exception):
    """A refusal or failure; the orchestrator turns it into a marker."""


# ====================================================================== pure helpers (offline-tested)
def pk(path):
    """'/Game/A/B.B' or "Class'/Game/A/B.B'" -> '/Game/A/B'; None stays None."""
    if path is None:
        return None
    s = str(path)
    if "'" in s:
        s = s.split("'")[1]
    return s.split(".")[0]


def target_key(row):
    ident = row.get("guid") if row["kind"] == "template" else row.get("actor_path")
    return "%s|%s|%s|%s" % (row["kind"], row["package"], ident, row["component"])


def is_prior_ok(overrides):
    """Override states this tool may replace: none at all, or the Drop MI (the cache's own material)."""
    return all(p is None or p == DROP_MI for p in overrides)


def classify(row):
    want = [MI_V2G] * int(row["slots"])
    if list(row["overrides"]) == want:
        return "ALREADY"
    if is_prior_ok(row["overrides"]):
        return "SWAP"
    return "FOREIGN"


def variant_problems(doc):
    row = ((doc or {}).get("variants") or {}).get("V2G")
    if not isinstance(row, dict):
        return ["variants.V2G missing"]
    probs = []
    if row.get("textures"):
        probs.append("V2G has textures %r (not expected)" % row.get("textures"))
    sc, vc = row.get("scalars") or {}, row.get("vectors") or {}
    if sorted(sc) != sorted(V2G_SCALARS):
        probs.append("V2G scalar names %r != pinned %r" % (sorted(sc), sorted(V2G_SCALARS)))
    if sorted(vc) != sorted(V2G_VECTORS):
        probs.append("V2G vector names %r != pinned %r" % (sorted(vc), sorted(V2G_VECTORS)))
    for k, v in V2G_SCALARS.items():
        if k in sc and abs(float(sc[k]) - v) > 1e-9:
            probs.append("V2G %s file %r != pinned %r" % (k, sc[k], v))
    for k, v in V2G_VECTORS.items():
        got = list(vc.get(k) or [])
        if k in vc and (len(got) != 4 or any(abs(float(a) - b) > 1e-9 for a, b in zip(got, v))):
            probs.append("V2G %s file %r != pinned %r" % (k, got, v))
    unknown = [n for n in list(sc) + list(vc) if n not in PARAM_SCALARS + PARAM_VECTORS]
    if unknown:
        probs.append("V2G names not on the master: %r" % unknown)
    return probs


def mi_readback_problems(mi, drop_mapping):
    """mi = read_mi() dict: parent, scalars{}, vectors{}, overridden{} for EVERY master parameter."""
    if mi is None:
        return ["MI missing"]
    p = []
    if mi.get("parent") != MI_PARENT:
        p.append("parent %r != %r" % (mi.get("parent"), MI_PARENT))
    for k, v in V2G_SCALARS.items():
        got = mi["scalars"].get(k)
        if got is None or abs(float(got) - v) > TOL:
            p.append("%s read %r != %r" % (k, got, v))
    for k, v in V2G_VECTORS.items():
        got = mi["vectors"].get(k)
        if got is None or len(got) != 4 or any(abs(float(a) - b) > TOL for a, b in zip(got, v)):
            p.append("%s read %r != %r" % (k, got, v))
    for k in INHERITED_FROM_DROP:
        got, want = mi["scalars"].get(k), (drop_mapping or {}).get(k)
        if got is None or want is None or abs(float(got) - float(want)) > TOL:
            p.append("%s effective %r != Drop MI %r" % (k, got, want))
    want_over = set(V2G_SCALARS) | set(V2G_VECTORS)
    for name in PARAM_SCALARS + PARAM_VECTORS + PARAM_TEXTURES:
        flag = (mi.get("overridden") or {}).get(name)
        if flag is None:
            p.append("override flag for %s unread" % name)
        elif bool(flag) != (name in want_over):
            p.append("%s overridden=%r, expected %r" % (name, bool(flag), name in want_over))
    return p


def plan_digest(targets, mi_state):
    rows = [[target_key(t), t["slots"], list(t["overrides"])] for t in sorted(targets, key=target_key)]
    blob = json.dumps({"rows": rows, "mi": mi_state, "s": V2G_SCALARS, "v": V2G_VECTORS}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def make_plan(census, args):
    """census: {rows, unhandled, referencers, gc_slots, mi_state ('absent'|'same'|'different'), variant_problems}.
    Returns {targets, refusals, notes, digest, counts}. Pure."""
    args = args or {}
    ignore = args.get("ignore_referencers") or {}
    allow_missing = args.get("allow_missing") or {}
    refusals, notes = [], []
    rows = [dict(r) for r in census.get("rows") or []]
    gc_slots = census.get("gc_slots")
    seen = {}
    for r in rows:
        r["state"] = classify(r)
        r["after"] = [MI_V2G] * int(r["slots"])
        seen.setdefault(target_key(r), 0)
        seen[target_key(r)] += 1
        if not isinstance(gc_slots, int) or gc_slots < 1:
            refusals.append("GC_SLOTS_UNREADABLE|%r" % gc_slots)
        elif int(r["slots"]) != gc_slots:
            refusals.append("SLOT_MISMATCH|%s|slots=%s|cache=%s" % (target_key(r), r["slots"], gc_slots))
        if r.get("component_num_materials") not in (None, r["slots"]):
            refusals.append("SLOT_MISMATCH|%s|component=%s|cache=%s" % (target_key(r), r["component_num_materials"], r["slots"]))
        if r["state"] == "FOREIGN":
            refusals.append("FOREIGN_OVERRIDE|%s|%r" % (target_key(r), r["overrides"]))
    for k, c in seen.items():
        if c > 1:
            refusals.append("DUPLICATE_TARGET|%s|%d" % (k, c))
    named = {}
    for r in rows:
        if r["kind"] == "template":
            named.setdefault((r["package"], r["binding"]), []).append(r)
    for pkg, name in EXPECTED_TEMPLATES:
        hits = named.get((pkg, name), [])
        if not hits:
            if "%s|%s" % (pkg, name) in allow_missing:
                notes.append("EXPECTED_MISSING_ALLOWED|%s|%s|%s" % (pkg, name, allow_missing["%s|%s" % (pkg, name)]))
            else:
                refusals.append("EXPECTED_TARGET_MISSING|%s|%s" % (pkg, name))
        elif len(hits) > 1:
            refusals.append("EXPECTED_TARGET_AMBIGUOUS|%s|%s|%d" % (pkg, name, len(hits)))
    for (pkg, name), hits in sorted(named.items()):
        if (pkg, name) not in EXPECTED_TEMPLATES:
            notes.append("EXTRA_TEMPLATE_TARGET|%s|%s (discovered; will be swapped too)" % (pkg, name))
    for r in rows:
        if r["kind"] == "level":
            notes.append("LEVEL_TARGET|%s|%s (level will be saved)" % (r.get("actor_label"), r["component"]))
    for u in census.get("unhandled") or []:
        if u.get("package") in ignore:
            notes.append("UNHANDLED_IGNORED|%s|%s|reason=%s" % (u.get("package"), u.get("why"), ignore[u["package"]]))
        else:
            refusals.append("UNHANDLED_REFERENCER|%s|%s" % (u.get("package"), u.get("why")))
    if not rows:
        refusals.append("NO_TARGETS")
    for v in census.get("variant_problems") or []:
        refusals.append("VARIANT_DRIFT|%s" % v)
    mi_state = census.get("mi_state")
    if mi_state == "different":
        refusals.append("MI_EXISTS_DIFFERENT|%s (create-only: never edited; rename or remove it by hand)" % MI_V2G)
    elif mi_state not in ("absent", "same"):
        refusals.append("MI_STATE_UNKNOWN|%r" % mi_state)
    if census.get("parent_missing"):
        refusals.append("PARENT_MISSING|%s" % MI_PARENT)
    counts = {s: sum(1 for r in rows if r["state"] == s) for s in ("SWAP", "ALREADY", "FOREIGN")}
    return {"targets": rows, "refusals": refusals, "notes": notes, "counts": counts,
            "digest": plan_digest(rows, mi_state), "mi_state": mi_state}


def touched_packages(targets):
    """Packages an APPLY/REVERT writes for these targets (content, maps)."""
    content = sorted({t["package"] for t in targets if t["kind"] == "template"})
    maps = sorted({t["package"] for t in targets if t["kind"] == "level"})
    return content, maps


def make_record(run, plan, backup, backup_files, decided_by):
    swap = [t for t in plan["targets"] if t["state"] == "SWAP"]
    return {"schema_version": 1, "tool": TOOL, "run": run, "applied": False, "decided_by": decided_by,
            "mi": MI_V2G, "mi_parent": MI_PARENT, "mi_created": plan["mi_state"] == "absent",
            "backup": backup, "backup_files": backup_files, "digest": plan["digest"],
            "targets": [{k: t.get(k) for k in ("kind", "package", "binding", "guid", "actor_label", "actor_path",
                                                "component", "slots")}
                        | {"key": target_key(t), "before": list(t["overrides"]),
                           "effective_before": list(t.get("effective") or []), "after": list(t["after"])}
                        for t in swap],
            "skipped_already": [target_key(t) for t in plan["targets"] if t["state"] == "ALREADY"]}


def readback_problems(expected, live_rows, check_effective=True):
    """expected: {key: override list}; live_rows: {key: live row or None}."""
    p = []
    for key, want in sorted(expected.items()):
        row = live_rows.get(key)
        if row is None:
            p.append("TARGET_GONE|%s" % key)
            continue
        if list(row["overrides"]) != list(want):
            p.append("OVERRIDES|%s|read %r != %r" % (key, row["overrides"], want))
        if check_effective and want and all(w is not None for w in want) and len(want) == int(row["slots"]):
            if list(row.get("effective") or []) != list(want):
                p.append("EFFECTIVE|%s|read %r != %r" % (key, row.get("effective"), want))
    return p


def revert_plan(record, live_rows):
    """Per record target: RESTORE (live == after), SKIP (live == before), else DRIFT / GONE (refusals). Pure."""
    actions, refusals = [], []
    for t in record.get("targets") or []:
        live = live_rows.get(t["key"])
        if live is None:
            refusals.append("TARGET_GONE|%s" % t["key"])
            continue
        if list(live["overrides"]) == list(t["after"]):
            actions.append(("RESTORE", t))
        elif list(live["overrides"]) == list(t["before"]):
            actions.append(("SKIP", t))
        else:
            refusals.append("DRIFT|%s|live %r is neither after %r nor before %r"
                            % (t["key"], live["overrides"], t["after"], t["before"]))
    return actions, refusals


# ====================================================================== orchestration (adapter-driven)
def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as h:
        json.dump(data, h, indent=1, sort_keys=True, default=str, ensure_ascii=False)
    os.replace(tmp, path)


def _write_new_json(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as h:
        json.dump(data, h, indent=1, sort_keys=True, default=str, ensure_ascii=False)
        h.flush()
        os.fsync(h.fileno())


def _read_json(path):
    with open(path, "r", encoding="utf-8") as h:
        return json.load(h)


def gate_live(ue, mode, args, run):
    probs = []
    if mode not in MODES:
        probs.append("BAD_MODE|%r" % mode)
    if ue.pie_active():
        probs.append("PIE_ACTIVE (refusing; never ending it)")
    if ue.world_path() != EXPECTED_WORLD:
        probs.append("WRONG_WORLD|%s" % ue.world_path())
    if ue.sequencer_open():
        probs.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates spawnables and dirties the map)")
    zz = ue.zz_actors()
    if zz:
        probs.append("ZZ_ACTORS_PRESENT|%s" % zz[:5])
    d = ue.dirty()
    if mode in ("APPLY", "REVERT") and (d["content"] or d["maps"]):
        probs.append("DIRTY_AT_START|%s" % json.dumps(d))
    if mode in CONFIRM and (args.get("confirm") or "") != CONFIRM[mode]:
        probs.append("CONFIRM|need %r" % CONFIRM[mode])
    return probs, d


def gather(ue):
    rows, unhandled = [], []
    refs = ue.referencers(GC_PATH)
    for pkg in refs:
        classes = ue.package_classes(pkg)
        if "LevelSequence" in classes:
            r, u = ue.sequence_rows(pkg)
            rows += r
            unhandled += u
        elif "World" in classes and pkg == EXPECTED_WORLD:
            continue                                  # covered by the level scan below
        else:
            unhandled.append({"package": pkg, "why": "REFERENCER_KIND|%s" % classes})
    r, u = ue.level_rows()
    rows += r
    unhandled += u
    variants_path = os.path.join(ue.here(), VARIANTS_NAME)
    vprobs = variant_problems(_read_json(variants_path)) if os.path.isfile(variants_path) else ["variants file missing"]
    drop = ue.drop_mapping()
    parent_missing = not ue.asset_exists(MI_PARENT)
    mi = ue.read_mi(MI_V2G) if ue.asset_exists(MI_V2G) else None
    mi_state = "absent" if mi is None else ("same" if not mi_readback_problems(mi, drop) else "different")
    return {"referencers": refs, "rows": rows, "unhandled": unhandled, "gc_slots": ue.gc_slots(),
            "variant_problems": vprobs, "drop_mapping": drop, "mi_state": mi_state, "mi_read": mi,
            "parent_missing": parent_missing}


def _backup(ue, run, tag, content, include_map):
    backup = os.path.join(ue.project_dir(), "Backups", "PreVelvetV2G-%s%s" % (run, tag))
    os.makedirs(backup, exist_ok=False)
    files = []
    srcs = [ue.content_file(EXPECTED_WORLD, ".umap")] + [ue.content_file(p) for p in content]
    for src in srcs:
        if not os.path.isfile(src):
            raise Stop("BACKUP_SOURCE_MISSING|%s" % src)
        dst = os.path.join(backup, os.path.basename(src))
        if os.path.exists(dst):
            raise Stop("BACKUP_NAME_CLASH|%s" % dst)
        shutil.copy2(src, dst)
        if os.path.getsize(dst) != os.path.getsize(src):
            raise Stop("BACKUP_SIZE_MISMATCH|%s" % src)
        files.append(dst)
    return backup, files


def _live(ue, targets):
    return {target_key(t): ue.read_row(t) for t in targets}


def _save_scope(ue, content, maps, mi_new, run):
    d = ue.dirty()
    want_c = set(content) | ({MI_V2G} if mi_new else set())
    if set(d["content"]) != want_c or set(d["maps"]) != set(maps):
        raise Stop("FAILED|UNEXPECTED_DIRTY|have=%s|want content=%s maps=%s" % (json.dumps(d), sorted(want_c), maps))
    saves = {}
    for p in sorted(want_c):
        saves[p] = bool(ue.save_asset(p))
    for m in maps:
        saves[m] = bool(ue.save_map(m))
    return saves


def run_dry(ue, args, run, census):
    plan = make_plan(census, args)
    report = {"run": run, "mode": "DRY", "plan_digest": plan["digest"], "counts": plan["counts"],
              "refusals": plan["refusals"], "notes": plan["notes"], "referencers": census["referencers"],
              "unhandled": census["unhandled"], "gc_slots": census["gc_slots"], "mi_state": plan["mi_state"],
              "mi_read": census.get("mi_read"), "drop_mapping": census["drop_mapping"],
              "targets": [{k: t.get(k) for k in ("kind", "package", "binding", "guid", "actor_label", "component",
                                                  "slots", "component_num_materials", "cache", "overrides",
                                                  "effective", "state", "after")} for t in plan["targets"]],
              "touched": dict(zip(("content", "maps"), touched_packages(
                  [t for t in plan["targets"] if t["state"] == "SWAP"]))),
              "next": "copy plan_digest into args dry_digest, set mode APPLY + confirm '%s'" % CONFIRM["APPLY"]}
    _write_json(os.path.join(ue.here(), "velvet_v2g_dry_%s.json" % run), report)
    _write_json(os.path.join(ue.here(), DRY_NAME), report)
    tag = "VV2G_DRY_OK" if not plan["refusals"] else "VV2G_DRY_REFUSED"
    ue.log("%s|run=%s|targets=%d|swap=%d|already=%d|foreign=%d|refusals=%d|mi=%s|digest=%s|mutated=0|json=%s"
           % (tag, run, len(plan["targets"]), plan["counts"]["SWAP"], plan["counts"]["ALREADY"],
              plan["counts"]["FOREIGN"], len(plan["refusals"]), plan["mi_state"], plan["digest"], DRY_NAME))
    return report


def run_apply(ue, args, run, census):
    record_path = os.path.join(ue.here(), RECORD_NAME)
    if os.path.exists(record_path):
        raise Stop("RECORD_EXISTS|%s (REVERT first, or it is from an earlier apply)" % record_path)
    if not str(args.get("decided_by") or "").strip():
        raise Stop("NOT_DECIDED|args decided_by is empty")
    plan = make_plan(census, args)
    if plan["refusals"]:
        raise Stop("PLAN_REFUSED|%s" % "; ".join(plan["refusals"]))
    if args.get("dry_digest") != plan["digest"]:
        raise Stop("PLAN_CHANGED_SINCE_DRY|dry=%s|now=%s|rerun DRY" % (args.get("dry_digest"), plan["digest"]))
    swap = [t for t in plan["targets"] if t["state"] == "SWAP"]
    mi_new = plan["mi_state"] == "absent"
    if not swap and not mi_new:
        ue.log("VV2G_APPLY_NOOP|run=%s|every target already reads %s" % (run, MI_V2G))
        return {"status": "NOOP"}
    content, maps = touched_packages(swap)
    missing = ue.unloadable([MI_PARENT, DROP_MI])
    if missing:
        raise Stop("ASSET_LOAD|%s" % missing)
    # 0. backups + record, BEFORE any mutation
    backup, files = _backup(ue, run, "", content, bool(maps))
    record = make_record(run, plan, backup, files, args.get("decided_by"))
    _write_new_json(record_path, record)
    ue.event("record_written")
    try:
        # 1. the MI (create-only), gated by read-back
        if mi_new:
            ue.create_mi(MI_V2G, MI_PARENT, V2G_SCALARS, V2G_VECTORS)
        probs = mi_readback_problems(ue.read_mi(MI_V2G), census["drop_mapping"])
        if probs:
            raise Stop("FAILED|MI_READBACK|%s" % probs)
        # 2. overrides
        for t in swap:
            ue.set_overrides(t, t["after"])
        probs = readback_problems({target_key(t): t["after"] for t in swap}, _live(ue, swap))
        if probs:
            raise Stop("FAILED|READBACK_BEFORE_SAVE|%s" % probs)
        # 3. save only the touched packages
        saves = _save_scope(ue, content, maps, mi_new, run)
    except Stop as exc:
        raise Stop(str(exc) if str(exc).startswith("FAILED|") else "FAILED|" + str(exc))
    if not all(saves.values()):
        record["saves"] = saves
        _write_json(record_path, record)
        raise Stop("PARTIAL_SAVE|%s|run REVERT" % saves)
    after_dirty = ue.dirty()
    probs = []
    if after_dirty["content"] or after_dirty["maps"]:
        probs.append("DIRTY_AFTER_SAVE|%s" % json.dumps(after_dirty))
    probs += mi_readback_problems(ue.read_mi(MI_V2G), census["drop_mapping"])
    live = _live(ue, swap)
    probs += readback_problems({target_key(t): t["after"] for t in swap}, live)
    record["saves"] = saves
    record["snapshot_after"] = live
    if probs:
        _write_json(record_path, record)
        raise Stop("PARTIAL_SAVE|SAVED_READBACK|%s|run REVERT" % probs)
    record["applied"] = True
    _write_json(record_path, record)
    ue.log("VV2G_APPLY_OK|run=%s|mi=%s|mi_created=%d|targets=%d|saved=%d|maps_saved=%d|backup=%s|record=%s"
           % (run, MI_V2G, int(mi_new), len(swap), len(saves), len(maps), backup, RECORD_NAME))
    return {"status": "APPLIED", "saves": saves, "record": record_path}


def run_verify(ue, args, run, census):
    plan = make_plan(census, args)
    probs = [r for r in plan["refusals"] if not r.startswith("MI_")]
    probs += ["NOT_V2G|%s|%r" % (target_key(t), t["overrides"]) for t in plan["targets"] if t["state"] != "ALREADY"]
    probs += mi_readback_problems(census.get("mi_read"), census["drop_mapping"])
    report = {"run": run, "mode": "VERIFY", "problems": probs, "targets": len(plan["targets"])}
    _write_json(os.path.join(ue.here(), "velvet_v2g_verify_%s.json" % run), report)
    if probs:
        raise Stop("VERIFY_FAILED|%s" % probs)
    ue.log("VV2G_VERIFY_OK|run=%s|targets=%d|mi=%s" % (run, len(plan["targets"]), MI_V2G))
    return report


def run_revert(ue, args, run):
    record_path = os.path.join(ue.here(), RECORD_NAME)
    if not os.path.isfile(record_path):
        raise Stop("NO_RECORD|%s" % record_path)
    record = _read_json(record_path)
    targets = record.get("targets") or []
    live = {t["key"]: ue.read_row(t) for t in targets}
    actions, refusals = revert_plan(record, live)
    if refusals:
        raise Stop("REVERT_REFUSED|%s" % "; ".join(refusals))
    restore = [t for a, t in actions if a == "RESTORE"]
    befores = sorted({p for t in restore for p in t["before"] if p is not None})
    missing = ue.unloadable(befores)
    if missing:
        raise Stop("BEFORE_ASSET_UNLOADABLE|%s" % missing)
    suffix = ".reverted-%s" if record.get("applied") else ".unapplied-%s"
    if restore:
        content, maps = touched_packages(restore)
        backup, files = _backup(ue, run, "-revert", content, bool(maps))
        try:
            for t in restore:
                ue.set_overrides(t, t["before"])
            probs = readback_problems({t["key"]: t["before"] for t in restore}, {t["key"]: ue.read_row(t) for t in restore},
                                      check_effective=False)
            if probs:
                raise Stop("FAILED|REVERT_READBACK_BEFORE_SAVE|%s" % probs)
            saves = _save_scope(ue, content, maps, False, run)
        except Stop as exc:
            raise Stop(str(exc) if str(exc).startswith("FAILED|") else "FAILED|" + str(exc))
        if not all(saves.values()):
            raise Stop("PARTIAL_SAVE|%s|rerun REVERT" % saves)
        now = {t["key"]: ue.read_row(t) for t in restore}
        probs = readback_problems({t["key"]: t["before"] for t in restore}, now, check_effective=False)
        for t in restore:
            eff = (now.get(t["key"]) or {}).get("effective")
            if t.get("effective_before") and list(eff or []) != list(t["effective_before"]):
                probs.append("EFFECTIVE_NOT_RESTORED|%s|%r != %r" % (t["key"], eff, t["effective_before"]))
        d = ue.dirty()
        if d["content"] or d["maps"]:
            probs.append("DIRTY_AFTER_SAVE|%s" % json.dumps(d))
        if probs:
            raise Stop("PARTIAL_SAVE|REVERT_SAVED_READBACK|%s" % probs)
    else:
        backup, saves = None, {}
    report = {"run": run, "mode": "REVERT", "restored": [t["key"] for t in restore],
              "skipped": [t["key"] for a, t in actions if a == "SKIP"], "saves": saves, "backup": backup,
              "mi_left_in_place": MI_V2G, "record_was_applied": bool(record.get("applied"))}
    _write_json(os.path.join(ue.here(), "velvet_v2g_revert_%s.json" % run), report)
    os.replace(record_path, record_path + suffix % run)
    ue.log("VV2G_REVERT_OK|run=%s|restored=%d|skipped=%d|saved=%d|mi_left=%s|record=%s"
           % (run, len(restore), len(report["skipped"]), len(saves), MI_V2G, RECORD_NAME + suffix % run))
    return report


def execute(ue, args):
    """Mode dispatch with markers. Returns (status, payload)."""
    mode = str(args.get("mode") or "DRY").upper()
    run = args.get("run_id") or "VV2G-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        probs, _ = gate_live(ue, mode, args, run)
        if probs:
            raise Stop("GATES|%s" % "; ".join(probs))
        if mode == "REVERT":
            return "REVERTED", run_revert(ue, args, run)
        census = gather(ue)
        d0 = ue.dirty()
        if mode == "DRY":
            out = run_dry(ue, args, run, census)
        elif mode == "VERIFY":
            out = run_verify(ue, args, run, census)
        else:
            return "APPLIED", run_apply(ue, args, run, census)
        if ue.dirty() != d0:
            raise Stop("READ_ONLY_MODE_DIRTIED|%s" % json.dumps(ue.dirty()))
        return mode, out
    except Stop as exc:
        msg = str(exc)
        if msg.startswith("FAILED|"):
            ue.log_error("VV2G_FAILED|run=%s|%s|NOTHING SAVED: Don't-Save restart (never Save All), then REVERT "
                         "(it skips untouched targets and renames the record .unapplied)" % (run, msg[7:]))
            return "FAILED", msg
        if msg.startswith("PARTIAL_SAVE|"):
            ue.log_error("VV2G_PARTIAL_SAVE|run=%s|%s" % (run, msg))
            return "PARTIAL_SAVE", msg
        ue.log_error("VV2G_STOPPED|run=%s|mode=%s|%s|nothing written" % (run, mode, msg))
        return "STOPPED", msg
    except Exception as exc:  # noqa: BLE001
        ue.log_error("VV2G_FAILED|run=%s|exception %r|if anything is dirty: Don't-Save restart, never Save All" % (run, exc))
        return "FAILED", repr(exc)


# ====================================================================== the Unreal adapter (built inside main only)
class UnrealAdapter:
    def __init__(self):
        import unreal
        self.u = unreal
        self.mel = unreal.MaterialEditingLibrary
        self.eal = unreal.EditorAssetLibrary
        self.ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.handles = {}

    # environment
    def here(self):
        return os.path.join(self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_saved_dir()), "CodexConductor")

    def project_dir(self):
        return self.u.Paths.convert_relative_path_to_full(self.u.Paths.project_dir())

    def content_file(self, path, ext=".uasset"):                    # curtain_sleight.py:1268-1270
        return os.path.join(self.project_dir(), "Content", *path[len("/Game/"):].split("/")) + ext

    def log(self, msg):
        self.u.log(msg)

    def log_error(self, msg):
        self.u.log_error(msg)

    def event(self, name):
        pass

    def pie_active(self):
        return self.ed.get_game_world() is not None

    def world_path(self):
        w = self.ed.get_editor_world()
        return pk(w.get_outermost().get_name()) if w is not None else None

    def sequencer_open(self):                                          # curtain_sleight.py:2551
        return self.u.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None

    def _actors(self):
        return list(self.u.get_editor_subsystem(self.u.EditorActorSubsystem).get_all_level_actors())

    def zz_actors(self):
        return [str(a.get_actor_label()) for a in self._actors() if str(a.get_actor_label()).startswith("ZZ_")]

    def dirty(self):                                                   # curtain_sleight.py:1259-1261
        lib = self.u.EditorLoadingAndSavingUtils
        return {"content": sorted(pk(p.get_path_name()) for p in lib.get_dirty_content_packages()),
                "maps": sorted(pk(p.get_path_name()) for p in lib.get_dirty_map_packages())}

    # discovery
    def _registry(self):
        ar = self.u.AssetRegistryHelpers.get_asset_registry()
        return ar

    def referencers(self, pkg):                                        # wet_undo_all.py:113-115 [prec]
        opts = self.u.AssetRegistryDependencyOptions()
        for prop, val in (("include_hard_package_references", True), ("include_soft_package_references", True)):
            try:
                opts.set_editor_property(prop, val)
            except Exception:  # noqa: BLE001
                pass
        return sorted({pk(str(x)) for x in (self._registry().get_referencers(pkg, opts) or [])})

    def package_classes(self, pkg):
        out = []
        for ad in self._registry().get_assets_by_package_name(pkg) or []:
            try:
                out.append(str(ad.asset_class_path.asset_name))         # [inf] UE 5.1+ AssetData field
            except Exception:  # noqa: BLE001
                out.append(str(ad.get_editor_property("asset_class")))
        return out

    def asset_exists(self, path):
        return bool(self.eal.does_asset_exist(path))

    def unloadable(self, paths):
        return [p for p in paths if self.eal.load_asset(p) is None]

    def gc_slots(self):
        gc = self.eal.load_asset(GC_PATH)
        return len(list(gc.get_editor_property("materials"))) if gc is not None else None

    def drop_mapping(self):
        drop = self.eal.load_asset(DROP_MI)
        if drop is None:
            return {}
        return {k: float(self.mel.get_material_instance_scalar_parameter_value(drop, k)) for k in INHERITED_FROM_DROP}

    def _guid(self, b):
        return str(self.u.GuidLibrary.conv_guid_to_string(b.get_id()))

    def _row(self, base, comp):
        cache = comp.get_editor_property("geometry_cache")
        slots = len(list(cache.get_editor_property("materials"))) if cache is not None else 0
        try:
            num = int(comp.get_num_materials())
        except Exception:  # noqa: BLE001
            num = None
        overrides = [pk(m.get_path_name()) if m is not None else None
                     for m in (comp.get_editor_property("override_materials") or [])]
        effective = []
        for i in range(slots):
            try:
                m = comp.get_material(i)
                effective.append(pk(m.get_path_name()) if m is not None else None)
            except Exception:  # noqa: BLE001
                effective.append("<unreadable>")
        row = dict(base)
        row.update({"component": str(comp.get_name()), "cache": pk(cache.get_path_name()) if cache else None,
                    "slots": slots, "component_num_materials": num, "overrides": overrides, "effective": effective})
        return row

    def _template_comps(self, tmpl):
        if tmpl is None:
            return []
        if isinstance(tmpl, self.u.GeometryCacheActor):
            c = tmpl.get_editor_property("geometry_cache_component")  # fit_transition_drapes.py:136 [prec]
            return [c] if c is not None else []
        try:
            return list(tmpl.get_components_by_class(self.u.GeometryCacheComponent))
        except Exception:  # noqa: BLE001
            return []

    def _is_gc(self, comp):
        c = comp.get_editor_property("geometry_cache")
        return c is not None and pk(c.get_path_name()) == GC_PATH

    def sequence_rows(self, pkg):
        seq = self.eal.load_asset(pkg)
        if seq is None or not isinstance(seq, self.u.LevelSequence):
            return [], [{"package": pkg, "why": "NOT_LEVEL_SEQUENCE|%s" % (seq.get_class().get_name() if seq else None)}]
        rows, unhandled = [], []
        for b in seq.get_bindings():
            name, guid = str(b.get_display_name()), self._guid(b)
            track_hit = False
            for t in b.get_tracks():
                if t.get_class().get_name() != "MovieSceneGeometryCacheTrack":
                    continue
                for s in t.get_sections():
                    a = s.get_editor_property("params").get_editor_property("geometry_cache_asset")
                    track_hit = track_hit or (a is not None and pk(a.get_path_name()) == GC_PATH)
            try:
                tmpl = b.get_object_template()
            except Exception:  # noqa: BLE001
                tmpl = None
            hits = [c for c in self._template_comps(tmpl) if self._is_gc(c)]
            for c in hits:
                row = self._row({"kind": "template", "package": pkg, "binding": name, "guid": guid,
                                 "template_class": tmpl.get_class().get_name()}, c)
                self.handles[target_key(row)] = (seq, tmpl, c)
                rows.append(row)
            if track_hit and not hits:
                unhandled.append({"package": pkg, "binding": name, "guid": guid,
                                  "why": "GC_TRACK_WITHOUT_GC_TEMPLATE|template=%s"
                                         % (tmpl.get_class().get_name() if tmpl is not None else "possessable")})
        return rows, unhandled

    def level_rows(self):
        rows, unhandled = [], []
        for a in self._actors():
            try:
                comps = list(a.get_components_by_class(self.u.GeometryCacheComponent))
            except Exception:  # noqa: BLE001
                comps = []
            for c in comps:
                if not self._is_gc(c):
                    continue
                outer = pk(a.get_outermost().get_name())
                if outer != EXPECTED_WORLD:
                    unhandled.append({"package": outer, "why": "EXTERNAL_ACTOR|%s" % a.get_actor_label()})
                    continue
                row = self._row({"kind": "level", "package": EXPECTED_WORLD, "actor_label": str(a.get_actor_label()),
                                 "actor_path": str(a.get_path_name())}, c)
                self.handles[target_key(row)] = (a, None, c)
                rows.append(row)
        return rows, unhandled

    def read_row(self, t):
        """Re-find a target from its identity and return its live row (None if gone)."""
        if t["kind"] == "template":
            seq = self.eal.load_asset(t["package"])
            if seq is None:
                return None
            for b in seq.get_bindings():
                if self._guid(b) != t["guid"]:
                    continue
                try:
                    tmpl = b.get_object_template()
                except Exception:  # noqa: BLE001
                    tmpl = None
                for c in self._template_comps(tmpl):
                    if str(c.get_name()) == t["component"]:
                        row = self._row({"kind": "template", "package": t["package"], "binding": str(b.get_display_name()),
                                         "guid": t["guid"], "template_class": tmpl.get_class().get_name()}, c)
                        self.handles[target_key(row)] = (seq, tmpl, c)
                        return row
            return None
        for a in self._actors():
            if str(a.get_path_name()) != t["actor_path"]:
                continue
            for c in a.get_components_by_class(self.u.GeometryCacheComponent):
                if str(c.get_name()) == t["component"]:
                    row = self._row({"kind": "level", "package": EXPECTED_WORLD, "actor_label": str(a.get_actor_label()),
                                     "actor_path": t["actor_path"]}, c)
                    self.handles[target_key(row)] = (a, None, c)
                    return row
        return None

    # writes
    def set_overrides(self, t, paths):
        if self.read_row(t) is None:
            raise Stop("TARGET_GONE|%s" % target_key(t))
        owner, tmpl, comp = self.handles[target_key(t)]
        objs = []
        for p in paths:
            if p is None:
                objs.append(None)
                continue
            o = self.eal.load_asset(p)
            if o is None:
                raise Stop("ASSET_LOAD|%s" % p)
            objs.append(o)
        owner.modify()                                  # the sequence (template) or the level actor: dirties its package
        if tmpl is not None:
            tmpl.modify()
        comp.modify()
        comp.set_editor_property("override_materials", objs)   # return value not trusted; read-back is the gate

    def create_mi(self, path, parent_path, scalars, vectors):    # velvet_v2_build.py:380-387, :498-507 [prec VV2_OK]
        if self.eal.does_asset_exist(path):
            raise Stop("MI_APPEARED|%s" % path)
        folder, name = path.rsplit("/", 1)
        mi = self.u.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, self.u.MaterialInstanceConstant, self.u.MaterialInstanceConstantFactoryNew())
        if mi is None or not isinstance(mi, self.u.MaterialInstanceConstant):
            raise Stop("MI_CREATE|%s" % path)
        parent = self.eal.load_asset(parent_path)
        mi.modify()
        self.mel.set_material_instance_parent(mi, parent)
        for k, v in scalars.items():
            mi.modify()
            self.mel.set_material_instance_scalar_parameter_value(mi, k, float(v))     # bool unreliable
        for k, v in vectors.items():
            mi.modify()
            self.mel.set_material_instance_vector_parameter_value(mi, k, self.u.LinearColor(*[float(x) for x in v]))
        self.mel.update_material_instance(mi)

    def read_mi(self, path):
        mi = self.eal.load_asset(path)
        if mi is None:
            return None
        par = mi.get_editor_property("parent")
        out = {"parent": pk(par.get_path_name()) if par is not None else None, "scalars": {}, "vectors": {},
               "overridden": {}}
        for k in PARAM_SCALARS:
            out["scalars"][k] = float(self.mel.get_material_instance_scalar_parameter_value(mi, k))
        for k in PARAM_VECTORS:
            c = self.mel.get_material_instance_vector_parameter_value(mi, k)
            out["vectors"][k] = [float(c.r), float(c.g), float(c.b), float(c.a)]
        for k in PARAM_SCALARS + PARAM_VECTORS + PARAM_TEXTURES:
            out["overridden"][k] = bool(self.mel.is_material_instance_parameter_overridden(mi, k))  # build.py:321-322
        return out

    def save_asset(self, path):
        return self.eal.save_asset(path, only_if_is_dirty=False)

    def save_map(self, path):
        world = self.ed.get_editor_world()
        return self.u.EditorLoadingAndSavingUtils.save_map(world, path)       # opening_sequence_apply.py:848-852 [prec]


def main(args):
    ue = UnrealAdapter()
    return execute(ue, args)


if globals().get("VV2G_ARGS") is not None:
    main(globals()["VV2G_ARGS"])
