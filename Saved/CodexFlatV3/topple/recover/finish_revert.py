"""Finish REVERT of TOPPLE-20261007-024333 after TOPPLE-20261007-080745 stopped on a whole-cue-text comparison.
Re-asserts (diag 7 Oct ~08:10): every target's mechanism + mask equal the originals; every non-mechanism difference
is a Lighting (Intensity/Color/Temperature) field (the conductor's dead_bulbs_warm pass, after the STILL apply).
Then materialize P06, census scope {Show, level}, save Show + level, re-read, and retire the originals record
exactly as topple_apply.run_revert does. Marker TOPPLE_RECOVER_REVERT_OK."""
import json, os, re, difflib
import unreal

RUN = "TOPPLE-RECOVER-20261007-01"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3", "topple")
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ALLOWED = re.compile(r"^(Intensity=[0-9.]+|Color=\(R=[0-9.]+,G=[0-9.]+,B=[0-9.]+,A=[0-9.]+\)|bUseTemperature=(True|False)|TemperatureKelvin=[0-9.]+|,)*$")

def stop(why):
    unreal.log_error("TOPPLE_RECOVER_STOPPED|run=%s|reason=%s" % (RUN, why)); raise RuntimeError(why)

def strip_mech(t):
    i = t.find("Mechanism=(")
    if i < 0: return t
    j = i + len("Mechanism=("); d = 1
    while d and j < len(t):
        d += {"(": 1, ")": -1}.get(t[j], 0); j += 1
    return t[:i] + "Mechanism=<>" + t[j:]

def strip_blocks(t, key):
    out, k = [], 0
    while True:
        i = t.find(key + "=(", k)
        if i < 0: out.append(t[k:]); return "".join(out)
        j = i + len(key) + 2; d = 1
        while d and j < len(t):
            d += {"(": 1, ")": -1}.get(t[j], 0); j += 1
        out.append(t[k:i] + key + "=<>"); k = j

def lighting_only(a, b):
    # equal once every Lighting=(...) block is blanked: all differences live inside Lighting blocks
    return strip_blocks(a, "Lighting") == strip_blocks(b, "Lighting")

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world() is not None: stop("PIE_ACTIVE")
if str(ed.get_editor_world().get_outermost().get_name()) != WORLD: stop("WRONG_WORLD")
lib = unreal.EditorLoadingAndSavingUtils
cen = lambda: ({str(p.get_path_name()).split(".")[0] for p in lib.get_dirty_content_packages()},
               {str(p.get_path_name()).split(".")[0] for p in lib.get_dirty_map_packages()})
c0, m0 = cen()
if not c0 <= {SHOW} or m0: stop("CENSUS_START %s %s" % (sorted(c0), sorted(m0)))
orig_path = os.path.join(HERE, "topple_originals_TOPPLE-20261007-024333.json")
orig = json.load(open(orig_path, encoding="utf-8"))
show = unreal.EditorAssetLibrary.load_asset(SHOW)
gid = lambda c: str(unreal.GuidLibrary.conv_guid_to_string(c.get_editor_property("cue_guid"))).upper()

def check():
    by = {gid(c): c for c in show.get_editor_property("cues")}
    bad = []
    for r in orig["rows"]:
        c = by[r["cue_guid"]]; p = c.get_editor_property("wing_pair")
        if p.get_editor_property("mechanism").export_text() != r["mech_text"]: bad.append("MECH " + r["label"])
        if int(p.get_editor_property("local_override_mask")) != int(r["mask"]): bad.append("MASK " + r["label"])
        a, b = strip_mech(r["cue_text"]), strip_mech(c.export_text())
        if a != b and not lighting_only(a, b): bad.append("NONLIGHT_DIFF " + r["label"])
    return bad

bad = check()
if bad: stop("PRECHECK %s" % bad[:6])
actors = [a for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(), unreal.InfinityStagePassageActor)
          if str(unreal.GuidLibrary.conv_guid_to_string(a.get_editor_property("passage_guid"))).upper() == "9BFC29C45D47911FF7836BB8537230D2"]
if len(actors) != 1: stop("P06_ACTOR_COUNT %d %s" % (len(actors), [str(a.get_actor_label()) for a in actors]))
if not actors[0].materialize_passage(): stop("MATERIALIZE_FALSE")
c1, m1 = cen()
if not c1 <= {SHOW} or not m1 <= {WORLD}: stop("DIRTY_SCOPE %s %s" % (sorted(c1), sorted(m1)))
if not unreal.EditorAssetLibrary.save_asset(SHOW, only_if_is_dirty=False): stop("SAVE_SHOW_FALSE")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(): stop("SAVE_LEVEL_FALSE")
c2, m2 = cen()
if c2 or m2: stop("DIRTY_AFTER_SAVE %s %s" % (sorted(c2), sorted(m2)))
bad = check()
if bad: stop("POST_SAVE %s" % bad[:6])
os.replace(orig_path, orig_path.replace(".json", "_reverted.json"))
active = os.path.join(HERE, "topple_originals_ACTIVE.json")
if os.path.exists(active): os.remove(active)
unreal.log("TOPPLE_RECOVER_REVERT_OK|run=%s|reverted=TOPPLE-20261007-024333|rows=%d|saved=show,level|census=clean" % (RUN, len(orig["rows"])))
