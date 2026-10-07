"""Offline harness for klara_void_s6.py (7 Oct). System Python only - no Unreal, no MCP.

1. RE-DERIVES the [meas] facts from the package bytes (Content/Void_content/LS_Void.uasset, Content/L_KK_Void.umap,
   Content/InfinityStage/Dev/Sequences/LS_DevScene_06.uasset) with a minimal UE5 (file version 1018) reader, and
   asserts the args' her_offline_facts equal them (a stale args file fails the run).
2. Tests the pure maths/plan with + and - controls (every "exact" claim has a control that must FAIL).
3. Seeded mutations of the tool source: each must be caught by at least one test (proves the tests can fail).
Run: python test_klara_void_s6_offline.py   -> prints a summary; exit code 0 only if everything passes.
"""
import copy
import importlib.util
import json
import math
import os
import struct
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TOOL = os.path.join(HERE, "klara_void_s6.py")
ARGS = os.path.join(HERE, "klara_void_s6_args.json")
LS_VOID = os.path.join(PROJECT, "Content", "Void_content", "LS_Void.uasset")
L_VOID = os.path.join(PROJECT, "Content", "L_KK_Void.umap")
LS_S6 = os.path.join(PROJECT, "Content", "InfinityStage", "Dev", "Sequences", "LS_DevScene_06.uasset")
AUDIO_REC = os.path.join(PROJECT, "Saved", "CodexConductor", "scene_audio_import_S6_record.json")
DOCKS = os.path.join(PROJECT, "Saved", "CodexStructure", "scene_docks.json")


def load_tool(src=None):
    spec = importlib.util.spec_from_file_location("klara_void_s6_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    if src is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(src, TOOL, "exec"), mod.__dict__)
    return mod


# =====================================================================================================================
# Minimal UE5 package reader (file version UE5 1018, editor packages). Enough for names/imports/exports/tagged props.
# =====================================================================================================================

class R:
    def __init__(self, b, o=0):
        self.b, self.o = b, o

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.o)[0]
        self.o += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.o)[0]
        self.o += 4
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.b, self.o)[0]
        self.o += 8
        return v

    def raw(self, n):
        v = self.b[self.o:self.o + n]
        self.o += n
        return v

    def fstr(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            return self.raw(-2 * n).decode("utf-16le")[:-1]
        return self.raw(n)[:-1].decode("latin1")


class Package:
    EXPORT_SIZE = 112        # measured for 1018: 28 int32 per export entry (DependsOffset - ExportOffset = 137 * 112)

    def __init__(self, path):
        self.b = open(path, "rb").read()
        r = R(self.b)
        assert r.u32() == 0x9E2A83C1, "not a UE package"
        r.i32(), r.i32(), r.i32()
        self.ue5 = r.i32()
        r.i32()
        r.raw(20)
        r.i32()
        n = r.i32()
        r.raw(20 * n)
        self.name = r.fstr()
        flags = r.u32()
        nc, no = r.i32(), r.i32()
        r.i32(), r.i32()
        if not flags & 0x80000000:
            r.fstr()
        r.i32(), r.i32()
        ec, eo, ic, io = r.i32(), r.i32(), r.i32(), r.i32()
        rn = R(self.b, no)
        self.names = []
        for _ in range(nc):
            self.names.append(rn.fstr())
            rn.u32()
        ri = R(self.b, io)
        self.imports = []
        for _ in range(ic):
            self.fname(ri), self.fname(ri)
            outer = ri.i32()
            nm = self.fname(ri)
            self.fname(ri), ri.i32()
            self.imports.append({"name": nm, "outer": outer})
        re_ = R(self.b, eo)
        self.exports = []
        for _ in range(ec):
            st = re_.o
            ci, _si, _ti, oi = re_.i32(), re_.i32(), re_.i32(), re_.i32()
            nm = self.fname(re_)
            re_.u32()
            ss, so = re_.i64(), re_.i64()
            re_.o = st + self.EXPORT_SIZE
            self.exports.append({"ci": ci, "outer": oi, "name": nm, "ss": ss, "so": so})

    def fname(self, r):
        i, num = r.i32(), r.i32()
        s = self.names[i] if 0 <= i < len(self.names) else "?%d" % i
        return s if num == 0 else "%s_%d" % (s, num - 1)

    def entry(self, idx):
        return self.exports[idx - 1] if idx > 0 else self.imports[-idx - 1]

    def path(self, idx):
        p = []
        while idx:
            e = self.entry(idx)
            p.append(e["name"])
            idx = e["outer"]
        return ".".join(reversed(p))

    def cls(self, i):
        return self.entry(self.exports[i - 1]["ci"])["name"]

    def find(self, path):
        hits = [i for i in range(1, len(self.exports) + 1) if self.path(i) == path]
        assert len(hits) == 1, (path, hits)
        return hits[0]

    def typename(self, r):
        nm = self.fname(r)
        inner = r.i32()
        return nm if not inner else nm + "(" + ",".join(self.typename(r) for _ in range(inner)) + ")"

    def tags(self, data, top=True):
        r = R(data)
        if top:
            ctl = r.raw(1)[0]
            if ctl & 2:
                r.raw(1)
        out = []
        while r.o < len(data):
            nm = self.fname(r)
            if nm == "None":
                break
            t = self.typename(r)
            size = r.i32()
            fl = r.raw(1)[0]
            ai = r.i32() if fl & 1 else 0
            if fl & 2:
                r.raw(16)
            if fl & 4:
                ext = r.raw(1)[0]
                if ext & 2:
                    r.raw(2)
            out.append({"name": nm, "index": ai, "type": t, "flags": fl, "value": r.raw(size)})
        return out

    def props(self, idx):
        e = self.exports[idx - 1]
        return self.tags(self.b[e["so"]:e["so"] + e["ss"]])


def vec3(v):
    return list(struct.unpack("<ddd", v[:24]))


def frange(v):
    lt, lo, ut, hi = v[0], struct.unpack_from("<i", v, 1)[0], v[5], struct.unpack_from("<i", v, 6)[0]
    return [lo if lt != 2 else None, hi if ut != 2 else None]


INTERP = {0: "RCIM_LINEAR", 1: "RCIM_CONSTANT", 2: "RCIM_CUBIC", 3: "RCIM_NONE"}
TMODE = {0: "RCTM_AUTO", 1: "RCTM_USER", 2: "RCTM_BREAK", 3: "RCTM_NONE"}
EXTRAP = {0: "RCCE_CYCLE", 1: "RCCE_CYCLE_WITH_OFFSET", 2: "RCCE_OSCILLATE", 3: "RCCE_LINEAR", 4: "RCCE_CONSTANT",
          5: "RCCE_NONE"}


def dchan(v):
    """FMovieSceneDoubleChannel native layout as measured: pre u8, post u8, Times (elemsize, n, int32[]), Values
    (elemsize=32, n, {double, 4 floats tangents, u8 interp, u8 tmode, u8 wmode, pad}), default double, bHasDefault."""
    r = R(v, 2)
    r.i32()
    nt = r.i32()
    times = [r.i32() for _ in range(nt)]
    es, nv = r.i32(), r.i32()
    keys = []
    for t in times[:nv]:
        st = r.o
        val = struct.unpack_from("<d", v, st)[0]
        at, lt, _aw, _lw = struct.unpack_from("<ffff", v, st + 8)
        keys.append({"t": t, "v": val, "arrive": at, "leave": lt, "interp": INTERP.get(v[st + 24]),
                     "tmode": TMODE.get(v[st + 25]), "wmode": None if v[st + 26] == 0 else v[st + 26]})
        r.o = st + es
    d = struct.unpack_from("<d", v, r.o)[0]
    has = struct.unpack_from("<i", v, r.o + 8)[0]
    return {"keys": keys, "default": d if has else None, "pre": EXTRAP.get(v[0]), "post": EXTRAP.get(v[1])}


def guid_hex(b):
    return b[:16].hex()


def derive_her():
    """Everything the args claim about her LS, re-read from bytes."""
    p = Package(LS_VOID)
    ms = p.find("LS_Void.MovieScene_0")
    out = {"possessables": [], "spawnables": [], "bindings": {}, "cuts": []}
    tracks_of = {}
    pos_rows = []
    for tag in p.props(ms):
        if tag["name"] == "Possessables":
            data = tag["value"]
            n = struct.unpack_from("<i", data, 0)[0]
            # array of tagged structs; walk element by element
            r = R(data, 4)
            for _ in range(n):
                start = r.o
                sub = p.tags(data[start:], top=False)
                row = {}
                consumed = 0
                for s in sub:
                    if s["name"] == "Guid":
                        row["guid"] = guid_hex(s["value"])
                    elif s["name"] == "Name":
                        row["name"] = R(s["value"]).fstr()
                    elif s["name"] == "ParentGuid":
                        g = guid_hex(s["value"])
                        row["parent_guid"] = None if g == "00" * 16 else g
                pos_rows.append(row)
                # advance: re-walk to find the 'None' terminator offset
                rr = R(data, start)
                while True:
                    nm = p.fname(rr)
                    if nm == "None":
                        break
                    p.typename(rr)
                    size = rr.i32()
                    fl = rr.raw(1)[0]
                    if fl & 1:
                        rr.i32()
                    if fl & 2:
                        rr.raw(16)
                    if fl & 4:
                        ext = rr.raw(1)[0]
                        if ext & 2:
                            rr.raw(2)
                    rr.raw(size)
                r.o = rr.o
        elif tag["name"] == "ObjectBindings":
            data = tag["value"]
            n = struct.unpack_from("<i", data, 0)[0]
            r = R(data, 4)
            for _ in range(n):
                start = r.o
                g, trks = None, []
                rr = R(data, start)
                while True:
                    nm = p.fname(rr)
                    if nm == "None":
                        break
                    p.typename(rr)
                    size = rr.i32()
                    fl = rr.raw(1)[0]
                    if fl & 1:
                        rr.i32()
                    if fl & 2:
                        rr.raw(16)
                    if fl & 4:
                        ext = rr.raw(1)[0]
                        if ext & 2:
                            rr.raw(2)
                    val = rr.raw(size)
                    if nm == "ObjectGuid":
                        g = guid_hex(val)
                    elif nm == "Tracks":
                        c = struct.unpack_from("<i", val, 0)[0]
                        trks = [struct.unpack_from("<i", val, 4 + 4 * k)[0] for k in range(c)]
                tracks_of[g] = trks
                r.o = rr.o
        elif tag["name"] == "PlaybackRange":
            out["playback_tick"] = frange(tag["value"])
        elif tag["name"] == "Spawnables":
            out["spawnables"] = ["present"]
    by_guid = {r["guid"]: r for r in pos_rows}
    for r in pos_rows:
        par = by_guid.get(r.get("parent_guid"), {}).get("name")
        trks = [p.cls(i) for i in tracks_of.get(r["guid"], [])]
        out["possessables"].append({"name": r["name"], "parent": par, "tracks": trks, "guid": r["guid"],
                                    "track_idx": tracks_of.get(r["guid"], [])})
    names_by_guid = {r["guid"]: r["name"] for r in pos_rows}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) == "MovieSceneCameraCutSection":
            cam, rng = None, None
            for tag in p.props(i):
                if tag["name"] == "CameraBindingID":
                    for s in p.tags(tag["value"], top=False):
                        if s["name"] == "Guid":
                            cam = names_by_guid.get(guid_hex(s["value"]))
                elif tag["name"] == "SectionRange":
                    rng = frange(tag["value"])
            out["cuts"].append([rng, cam])
        elif p.cls(i) == "MovieSceneAudioSection":
            for tag in p.props(i):
                if tag["name"] == "SectionRange":
                    out["audio_range_tick"] = frange(tag["value"])
                elif tag["name"] == "Sound":
                    out["audio_sound"] = p.path(struct.unpack_from("<i", tag["value"], 0)[0]).split(".")[0]
    out["cuts"].sort()
    # transform channels per possessable
    for row in out["possessables"]:
        for ti in row["track_idx"]:
            if p.cls(ti) != "MovieScene3DTransformTrack":
                continue
            sec = p.find(p.path(ti) + ".MovieScene3DTransformSection_0")
            ch = {}
            for tag in p.props(sec):
                if "MovieSceneDoubleChannel" in tag["type"]:
                    ch["%s[%d]" % (tag["name"], tag["index"])] = dchan(tag["value"])
            row["transform"] = {"x": ch["Translation[0]"], "y": ch["Translation[1]"], "z": ch["Translation[2]"],
                                "roll": ch["Rotation[0]"], "pitch": ch["Rotation[1]"], "yaw": ch["Rotation[2]"],
                                "scale": [ch["Scale[%d]" % k] for k in range(3)]}
    return out


def derive_level():
    p = Package(L_VOID)
    out = {}
    for i in range(1, len(p.exports) + 1):
        path = p.path(i)
        if path.count(".") != 3:
            continue
        actor, comp = path.split(".")[2], path.split(".")[3]
        row = out.setdefault(actor, {})
        for tag in p.props(i):
            if tag["name"] == "RelativeLocation":
                row.setdefault(comp, {})["loc"] = vec3(tag["value"])
            elif tag["name"] == "RelativeRotation":
                pit, yaw, rol = vec3(tag["value"])
                row.setdefault(comp, {})["rot"] = [rol, pit, yaw]
            elif tag["name"] == "RelativeScale3D":
                row.setdefault(comp, {})["scale"] = vec3(tag["value"])
            elif tag["name"] == "AttachParent":
                row.setdefault(comp, {})["attach"] = p.path(struct.unpack_from("<i", tag["value"], 0)[0])
            elif tag["name"] == "Intensity":
                row.setdefault(comp, {})["intensity"] = struct.unpack("<f", tag["value"])[0]
            elif tag["name"] == "Asset":
                row.setdefault(comp, {})["asset"] = p.path(struct.unpack_from("<i", tag["value"], 0)[0]).split(".")[0]
            elif tag["name"] == "StaticMesh":
                row.setdefault(comp, {})["mesh"] = p.path(struct.unpack_from("<i", tag["value"], 0)[0]).split(".")[0]
    for i in range(1, len(p.exports) + 1):
        path = p.path(i)
        if path.count(".") == 2:
            for tag in p.props(i):
                if tag["name"] == "ActorLabel":
                    out.setdefault(path.split(".")[2], {})["label"] = R(tag["value"]).fstr()
    return out


def derive_scene():
    p = Package(LS_S6)
    out = {"score": [], "subs": [], "shots": [], "markers": []}
    for i in range(1, len(p.exports) + 1):
        c = p.cls(i)
        props = {t["name"]: t for t in p.props(i)}
        if c == "MovieScene":
            out["playback_tick"] = frange(props["PlaybackRange"]["value"])
        elif c in ("MovieSceneAudioSection", "MovieSceneSubSection", "MovieSceneCinematicShotSection"):
            ref = props.get("Sound") or props.get("SubSequence")
            target = p.path(struct.unpack_from("<i", ref["value"], 0)[0]).split(".")[0]
            rng = frange(props["SectionRange"]["value"])
            key = {"MovieSceneAudioSection": "score", "MovieSceneSubSection": "subs", "MovieSceneCinematicShotSection": "shots"}[c]
            out[key].append({"start_tick": rng[0], "end_tick": rng[1], "target": target,
                             "active": "bIsActive" not in props})       # bIsActive serialised only when False (default True)
    return out


# =====================================================================================================================
# Offline facts for plan_void (bytes + records), the way DRY assembles them live
# =====================================================================================================================

def _row_tr(tr):
    if not tr:
        return None
    return {k: tr[k] for k in ("x", "y", "z", "yaw", "roll", "pitch")}


def offline_facts(args):
    her_b = derive_her()
    scene_b = derive_scene()
    rec = json.load(open(AUDIO_REC, encoding="utf-8"))
    docks = json.load(open(DOCKS, encoding="utf-8"))
    entry = [e for e in docks["entry_cameras"] if e["label"].startswith("Scene 6")][0]
    tick, fps = 24000.0, 25.0
    tpf = int(tick / fps)
    scene = {"fps": fps, "tick": tick, "playback": [scene_b["playback_tick"][0] // tpf, scene_b["playback_tick"][1] // tpf],
             "label": "Scene 6 — External Sound", "camera_owner": None,
             "score": [{"track": "Scene Score", "start": s["start_tick"] // tpf, "end": s["end_tick"] // tpf,
                        "sound": s["target"], "active": s["active"]} for s in scene_b["score"]],
             "subs": [{"track": "Hangar Fold", "start": s["start_tick"] // tpf, "end": s["end_tick"] // tpf,
                       "sequence": s["target"], "active": s["active"]} for s in scene_b["subs"]],
             "markers": [{"label": m["label"], "scene_s": m["tick"] / tick} for m in rec["added_markers"]],
             "sections": []}
    off = args["her_offline_facts"]
    bindings = [{"name": r["name"], "kind": "possessable", "parent": r["parent"],
                 "class": [p.get("class") for p in off["possessables"] if p["name"] == r["name"] and not p.get("parent")][0]
                 if not r["parent"] else None, "transform": _row_tr(r.get("transform"))}
                for r in her_b["possessables"]]
    fc = off["first_cut_camera_pose"]
    her = {"tick": 24000.0, "fps": 30.0, "playback_tick": her_b["playback_tick"], "cuts": her_b["cuts"],
           "audio": {"sound": her_b["audio_sound"], "range_tick": her_b["audio_range_tick"]}, "bindings": bindings,
           "first_cut_camera": {"loc": fc["loc"], "rot": fc["rot"], "focal": 35.0, "binding": fc["binding"]}}
    return {"scene": scene, "her": her, "offline": off,
            "entry_camera": {"loc": entry["loc"], "rot": entry["rot"], "focal": 35.0}}


# =====================================================================================================================
# Tests. Each takes the tool module M.
# =====================================================================================================================

def _args():
    return json.load(open(ARGS, encoding="utf-8"))


def test_bytes_match_args(M):
    a = _args()["her_offline_facts"]
    her, lvl = derive_her(), derive_level()
    assert her["spawnables"] == [], "her LS has spawnables"
    tops = sorted((p["name"], p["parent"]) for p in her["possessables"])
    want = sorted((p["name"], p["parent"]) for p in a["possessables"])
    assert tops == want, (tops, want)
    assert her["playback_tick"] == a["playback_tick"], her["playback_tick"]
    assert [[c[0], c[1]] for c in her["cuts"]] == [[c[0], c[1]] for c in a["cuts"]], her["cuts"]
    assert her["audio_range_tick"] == a["audio"]["range_tick"] and her["audio_sound"] == a["audio"]["sound"]
    woman = [p for p in her["possessables"] if p["name"] == "BP_MHC_Elder_Female"][0]
    assert woman["tracks"] == [], "woman has tracks"
    assert lvl["BP_MHC_Elder_Female_C_1"]["Root"]["loc"] == a["woman_pose"]["loc"]
    assert [round(x, 6) for x in lvl["BP_MHC_Elder_Female_C_1"]["Root"]["rot"]] == a["woman_pose"]["rot"]
    cam5 = [p for p in her["possessables"] if p["name"] == "CineCameraActor5"][0]["transform"]
    pose = [cam5[k]["default"] for k in ("x", "y", "z", "roll", "pitch", "yaw")]
    assert all(not cam5[k]["keys"] for k in ("x", "y", "z", "roll", "pitch", "yaw"))
    assert [round(v, 6) + 0.0 for v in pose] == a["first_cut_camera_pose"]["loc"] + a["first_cut_camera_pose"]["rot"], pose
    sw = [p for p in her["possessables"] if p["name"] == "NS_BeeSwarm"][0]["transform"]
    first = [sw[k]["keys"][0]["v"] for k in ("x", "y", "z")]
    assert first == a["swarm"]["first_loc"], first
    assert [s["keys"][0]["v"] for s in sw["scale"]] == a["swarm"]["scale"]
    assert lvl["NiagaraActor_29"]["NiagaraComponent0"]["asset"] == "/Game/FX/NS_BeeSwarm"
    for sp in a["set_pieces"]["spots"]:
        lc = lvl[sp["level_object"]]["LightComponent0"]
        assert lc["loc"] == sp["loc"] and abs(lc["intensity"] - sp["intensity"]) < 1e-6, sp["label"]
        assert [round(x, 6) for x in lc.get("rot", [0.0, 0.0, 0.0])] == sp["rot"], (lc.get("rot"), sp["rot"])
    fl = a["set_pieces"]["floor"]
    smc = lvl["StaticMeshActor_0"]["StaticMeshComponent0"]
    assert smc["loc"] == fl["loc"] and smc["scale"] == fl["scale"] and smc["mesh"] == fl["mesh"]
    for name, row in lvl.items():                      # every camera root unattached -> its keys are absolute world
        if name.startswith("CineCameraActor_"):
            assert "attach" not in row.get("SceneComponent", {}), name
    labels = {r.get("label"): n for n, r in lvl.items()}
    for p in a["possessables"]:
        if not p.get("parent"):
            assert labels.get(p["name"]) == p["level_object"], (p["name"], labels.get(p["name"]))
    return "14 possessables, 0 spawnables, 10 cuts, poses = bytes"


def test_bytes_control(M):
    """- control: the comparison must notice a stale/mutated args fact."""
    a = _args()["her_offline_facts"]
    her = derive_her()
    bad = copy.deepcopy(a)
    bad["cuts"][0][1] = "CineCameraActor"
    assert [[c[0], c[1]] for c in her["cuts"]] != [[c[0], c[1]] for c in bad["cuts"]]
    bad2 = copy.deepcopy(a)
    bad2["woman_pose"]["loc"][0] += 1.0
    assert derive_level()["BP_MHC_Elder_Female_C_1"]["Root"]["loc"] != bad2["woman_pose"]["loc"]
    return "mutated facts detected"


def test_scene_bytes(M):
    s = derive_scene()
    assert s["playback_tick"] == [0, 4656000], s["playback_tick"]
    assert [(x["start_tick"], x["end_tick"]) for x in s["score"]] == [(99840, 4611840)]
    assert s["score"][0]["target"] == "/Game/InfinityStage/Audio/ScenesAudio/Score/SW_S6_The_Void_Live"
    assert [x["target"] for x in s["subs"]] == ["/Game/InfinityStage/RigAtmos/LS_S6_HangarRise"]
    assert [x["target"] for x in s["shots"]] == ["/Game/Scenes/LS_Void"]
    assert all(x["active"] for x in s["score"] + s["subs"] + s["shots"])
    return "LS_DevScene_06 on disk: 194 s, score [104,4804), rise [0,775), shot -> /Game/Scenes/LS_Void"


def test_placement_exact(M):
    f = offline_facts(_args())
    r = M.solve_arrival(f["her"]["first_cut_camera"], f["entry_camera"], "match_entry_yaw")
    assert r["seamless"] and r["residual"]["pos_cm"] < 1e-6, r
    t = r["transform"]
    assert [round(x, 4) for x in t["loc"]] == [29339.28, 399920.0, 135.0] and t["yaw"] == 0.0, t
    # - control: a yaw-mismatched entry must NOT read seamless under translation-only placement
    e2 = dict(f["entry_camera"], rot=[0.0, 0.0, 30.0])
    r2 = M.solve_arrival(f["her"]["first_cut_camera"], e2, "match_entry_translation")
    assert not r2["seamless"] and abs(r2["residual"]["yaw_deg"] - 30.0) < 1e-9
    r3 = M.solve_arrival(f["her"]["first_cut_camera"], e2, "match_entry_yaw")
    assert r3["seamless"], r3
    return "T=(29339.28, 399920, 135) yaw 0; residual 0"


def test_floor_placement(M):
    f = offline_facts(_args())
    r = M.solve_arrival(f["her"]["first_cut_camera"], f["entry_camera"], "match_entry_floor", 0.0, -40.0)
    assert abs(r["transform"]["loc"][2] - 40.0) < 1e-9 and abs(r["residual"]["dz_cm"] + 95.0) < 1e-9, r
    return "floor option: her floor at z=0, camera drops 95 cm at the seam"


def test_rotator_yaw_composition(M):
    """World-Z yaw theta composed onto FRotator(r, p, y) == FRotator(r, p, y + theta) (the re-key's rotation claim)."""
    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    worst, worst_ctrl = 0.0, 0.0
    for (r, p, y) in ((-33.0, 31.0, 7.0), (4.0, 0.0, 17.0), (0.0, -90.0, -1.0), (12.5, 47.0, 146.0)):
        for th in (30.0, -146.0, 90.0):
            c, s = math.cos(math.radians(th)), math.sin(math.radians(th))
            rz = [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]
            lhs = mul(rz, M.rotator_matrix(r, p, y))
            rhs = M.rotator_matrix(r, p, y + th)
            ctl = M.rotator_matrix(r + th, p, y)                 # - control: adding to roll is wrong
            worst = max(worst, max(abs(lhs[i][j] - rhs[i][j]) for i in range(3) for j in range(3)))
            worst_ctrl = max(worst_ctrl, max(abs(lhs[i][j] - ctl[i][j]) for i in range(3) for j in range(3)))
    assert worst < 1e-12, worst
    assert worst_ctrl > 0.1, worst_ctrl
    return "max err %.1e (control %.2f)" % (worst, worst_ctrl)


def _swarm():
    her = derive_her()
    return [p for p in her["possessables"] if p["name"] == "NS_BeeSwarm"][0]["transform"]


def test_swarm_rekey_translate_exact(M):
    sw = _swarm()
    assert all(k["interp"] == "RCIM_LINEAR" for ax in ("x", "y", "z") for k in sw[ax]["keys"])
    assert [k["t"] for k in sw["x"]["keys"]] != [k["t"] for k in sw["y"]["keys"]], "X/Y share times (fact changed)"
    t = {"loc": [29339.28, 399920.0, 135.0], "yaw": 0.0}
    out = M.rekey_rigid(sw, t)
    assert not out["problems"] and out["method"] == "translate"
    for tick in range(0, 5585600, 4000):
        for i, ax in enumerate("xyz"):
            a = M.eval_linear(sw[ax]["keys"], sw[ax]["default"], tick) + t["loc"][i]
            b = M.eval_linear(out[ax]["keys"], out[ax]["default"], tick)
            assert abs(a - b) < 1e-9
    return "her swarm curve translated exactly (1397 samples x 3 axes)"


def test_swarm_rekey_union_rotated_exact(M):
    sw = _swarm()
    t = {"loc": [100.0, -50.0, 7.0], "yaw": 37.0}
    out = M.rekey_rigid(sw, t)
    assert not out["problems"] and out["method"] == "rotate_union_linear", out["method"]
    worst = 0.0
    for tick in range(0, 5585600, 2000):
        x = M.eval_linear(sw["x"]["keys"], sw["x"]["default"], tick)
        y = M.eval_linear(sw["y"]["keys"], sw["y"]["default"], tick)
        w = M.rigid_point(t, [x, y, 0.0])
        nx = M.eval_linear(out["x"]["keys"], None, tick)
        ny = M.eval_linear(out["y"]["keys"], None, tick)
        worst = max(worst, abs(nx - w[0]), abs(ny - w[1]))
    assert worst < 1e-8, worst
    # - control: rotating each axis at its OWN key times (no union) is not exact on this curve
    c, s = math.cos(math.radians(37.0)), math.sin(math.radians(37.0))
    naive_x = [dict(k, v=c * k["v"] - s * M.eval_linear(sw["y"]["keys"], None, k["t"]) + 100.0) for k in sw["x"]["keys"]]
    err = 0.0
    for tick in range(0, 5585600, 2000):
        x = M.eval_linear(sw["x"]["keys"], None, tick)
        y = M.eval_linear(sw["y"]["keys"], None, tick)
        err = max(err, abs(M.eval_linear(naive_x, None, tick) - M.rigid_point(t, [x, y, 0.0])[0]))
    assert err > 1.0, err
    return "union re-key exact (err %.1e); naive control off by %.1f cm" % (worst, err)


def test_cubic_same_times_exact(M):
    keys = [{"t": 0, "v": 0.0, "interp": "RCIM_CUBIC", "tmode": "RCTM_USER", "arrive": 0.0, "leave": 0.002},
            {"t": 24000, "v": 100.0, "interp": "RCIM_CUBIC", "tmode": "RCTM_USER", "arrive": 0.001, "leave": -0.003},
            {"t": 60000, "v": -40.0, "interp": "RCIM_CUBIC", "tmode": "RCTM_USER", "arrive": 0.0, "leave": 0.0}]
    ykeys = [dict(k, v=k["v"] * 0.5 + 10.0, arrive=k["arrive"] * 2.0, leave=-k["leave"]) for k in keys]
    ch = {"x": {"keys": keys, "default": None, "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"},
          "y": {"keys": ykeys, "default": None, "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"},
          "z": {"keys": [], "default": 5.0}, "yaw": {"keys": [], "default": 10.0}}
    t = {"loc": [1.0, 2.0, 3.0], "yaw": 63.0}
    out = M.rekey_rigid(ch, t)
    assert not out["problems"] and out["method"] == "rotate_same_times"
    worst = 0.0
    for f in range(0, 60000, 500):
        seg = 0 if f < 24000 else 1
        x = M.eval_hermite(keys[seg], keys[seg + 1], f)
        y = M.eval_hermite(ykeys[seg], ykeys[seg + 1], f)
        w = M.rigid_point(t, [x, y, 0.0])
        worst = max(worst, abs(M.eval_hermite(out["x"]["keys"][seg], out["x"]["keys"][seg + 1], f) - w[0]),
                    abs(M.eval_hermite(out["y"]["keys"][seg], out["y"]["keys"][seg + 1], f) - w[1]))
    assert worst < 1e-9, worst
    assert abs(out["yaw"]["default"] - 73.0) < 1e-12 and abs(out["z"]["default"] - 8.0) < 1e-12
    # - control: different X/Y key times on CUBIC curves must refuse (no exact rotation exists)
    bad = copy.deepcopy(ch)
    bad["y"]["keys"][1]["t"] = 30000
    assert M.rekey_rigid(bad, t)["problems"]
    return "cubic rotate exact (err %.1e); cubic differing times refused" % worst


def test_defaults_only_cameras(M):
    her = derive_her()
    t = {"loc": [10.0, 20.0, 30.0], "yaw": 90.0}
    for p in her["possessables"]:
        if p["name"].startswith("CineCamera"):
            tr = p["transform"]
            out = M.rekey_rigid(tr, t)
            assert out["method"] == "rotate_defaults" and not out["problems"]
            w = M.rigid_point(t, [tr["x"]["default"], tr["y"]["default"], tr["z"]["default"]])
            assert abs(out["x"]["default"] - w[0]) < 1e-9 and abs(out["y"]["default"] - w[1]) < 1e-9
            assert abs(out["yaw"]["default"] - (tr["yaw"]["default"] + 90.0)) < 1e-12
    return "5 static cameras re-keyed via defaults"


def test_plan_default(M):
    a = _args()
    f = offline_facts(a)
    plan = M.plan_void(f, a)
    assert not plan["refusals"], plan["refusals"]
    assert plan["section"] == [104, 5923], plan["section"]
    assert plan["length"]["frames"] == 5819 and abs(plan["her_len_s"] - 232.7333333) < 1e-6
    assert plan["planned_end"] == 5923 and abs(plan["planned_end_s"] - 236.92) < 1e-9
    assert plan["extend_mode"] == {"scene_label": "Scene 6 — External Sound", "new_end_s": 236.92, "dry_run": True}
    assert all(m["lines_up"] for m in plan["markers"]), plan["markers"]
    assert plan["glimmer"]["spawn"] == [25, 154], plan["glimmer"]["spawn"]
    gp = plan["glimmer"]["pose"]["loc"]
    assert abs(gp[0] - 31643.0368359375) < 1e-6 and abs(gp[1] - 400033.37096405029) < 1e-6
    assert plan["timeline"]["hangar_off"] == [0, 5923] and plan["timeline"]["ours_off"] == [0, 5923]
    assert plan["woman_world"]["loc"] == [30909.28, 400020.0, 95.0] and plan["woman_world"]["rot"][2] == 146.0
    assert sorted(r["name"] for r in plan["rebuild"]) == sorted(
        ["NS_BeeSwarm", "CineCameraActor", "CineCameraActor2", "CineCameraActor3", "CineCameraActor4",
         "CineCameraActor5", "BP_MHC_Elder_Female"])
    assert len([p for p in plan["set_pieces"]]) == 4      # 2 spots, floor, directional
    assert plan["end_alternatives"]["her_last_cut"]["end"] == 104 + 5385
    assert abs(plan["her_cut_span_scene_s"][1] - (104 / 25.0 + 215.3666667)) < 1e-6
    return "S=104, end 5923 (236.92 s), markers aligned, glimmer [25,154)"


def test_plan_controls(M):
    a = _args()
    f = offline_facts(a)
    b = copy.deepcopy(a)
    b["scene"]["start_option"] = "scene_start"
    p = M.plan_void(f, b)
    assert any(r.startswith("GLIMMER_NO_LEAD") for r in p["refusals"]), p["refusals"]
    assert not any(m["lines_up"] for m in p["markers"] if m.get("track_s") is not None)
    assert any("at_frame 104" in w for w in p["warnings"]), p["warnings"]
    b["glimmer"]["enabled"] = False
    p = M.plan_void(f, b)
    assert not p["refusals"] and p["section"] == [0, 5819]
    c = copy.deepcopy(a)
    c["scene"]["mute_sounds"] = ["/Game/Nope"]
    c["scene"]["start_option"], c["scene"]["at_frame"] = "at_frame", 104
    assert any(r.startswith("NOTHING_TO_MUTE") for r in M.plan_void(f, c)["refusals"])
    f2 = copy.deepcopy(f)
    f2["her"]["bindings"] = [x for x in f2["her"]["bindings"] if x["name"] != "NS_BeeSwarm"]
    assert any(r.startswith("HER_BINDINGS_DRIFTED") for r in M.plan_void(f2, a)["refusals"])
    f3 = copy.deepcopy(f)
    f3["scene"]["subs"] = []
    assert any(r.startswith("RISE_SECTION_COUNT") for r in M.plan_void(f3, a)["refusals"])
    return "no-lead refused, markers off at S=0, drift/mute/rise refusals fire"


def test_validate_and_gates(M):
    a = _args()
    assert M.validate_args(a) == []
    for mut, want in ((("mode", "NOPE"), "MODE_INVALID"),):
        b = copy.deepcopy(a)
        b[mut[0]] = mut[1]
        assert any(r.startswith(want) for r in M.validate_args(b))
    b = copy.deepcopy(a)
    b["scene"]["scene_sequence"] = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
    assert "TARGET_IS_THE_MASTER" in M.validate_args(b)
    b = copy.deepcopy(a)
    b["scene"]["copy_path"] = b["scene"]["her_sequence"]
    assert "COPY_PATH_IS_AN_ORIGINAL" in M.validate_args(b)
    b = copy.deepcopy(a)
    b["glimmer"]["start_s"] = -1
    assert "GLIMMER_START_S_INVALID" in M.validate_args(b)
    ok = {"mode": "APPLY", "confirm": "APPLY KLARAVOIDS6", "decided_by": "x", "census": {"content": [], "maps": []}}
    assert M.live_gates(ok) == []
    assert M.live_gates(dict(ok, confirm="APPLY KLARAVOID"))
    assert M.live_gates(dict(ok, pie=True))
    assert M.live_gates(dict(ok, census={"content": ["/Game/X"], "maps": []}))
    assert M.live_gates(dict(ok, record_exists="r.json"))
    assert M.live_gates(dict(ok, copy_exists="/Game/InfinityStage/KlaraHookin/LS_Void_S6"))
    assert M.live_gates({"mode": "REVERT", "confirm": "REVERT KLARAVOIDS6", "census": {}})
    assert M.live_gates({"mode": "DRY", "census": {}}) == []
    return "args + gates refuse what they should"


def test_import_without_unreal(M):
    assert M.unreal is None
    assert M.channel_base("Location.Y_183") == "Location.Y" and M.is_ours("Klara Void S6 - Hangar Off: S6 Hangar Root")
    assert not M.is_ours("S6 Hangar Root")
    return "imports cleanly, main() not run"


def test_yaw_keys_and_compose(M):
    ch = {"x": {"keys": [], "default": 1.0}, "y": {"keys": [], "default": 0.0}, "z": {"keys": [], "default": 0.0},
          "yaw": {"keys": [{"t": 0, "v": 10.0, "interp": "RCIM_LINEAR"}, {"t": 100, "v": 20.0, "interp": "RCIM_LINEAR"}],
                  "default": None}}
    out = M.rekey_rigid(ch, {"loc": [0.0, 0.0, 0.0], "yaw": 90.0})
    assert [k["v"] for k in out["yaw"]["keys"]] == [100.0, 110.0], out["yaw"]
    assert abs(out["x"]["default"]) < 1e-12 and abs(out["y"]["default"] - 1.0) < 1e-12
    w = M.compose_pose({"loc": [5.0, 0.0, 1.0], "yaw": 90.0}, [1570.0, 100.0, -40.0], [0.0, 0.0, 146.0])
    assert [round(v, 9) for v in w["loc"]] == [-95.0, 1570.0, -39.0] and w["rot"] == [0.0, 0.0, 236.0], w
    # - control: yaw 0 leaves the woman's heading alone
    assert M.compose_pose({"loc": [0.0, 0.0, 0.0], "yaw": 0.0}, [1.0, 2.0, 3.0], [0.0, 0.0, 146.0])["rot"][2] == 146.0
    return "yaw keys += theta; compose rotates position and heading"


TESTS = [test_yaw_keys_and_compose, test_bytes_match_args, test_bytes_control, test_scene_bytes, test_placement_exact, test_floor_placement,
         test_rotator_yaw_composition, test_swarm_rekey_translate_exact, test_swarm_rekey_union_rotated_exact,
         test_cubic_same_times_exact, test_defaults_only_cameras, test_plan_default, test_plan_controls,
         test_validate_and_gates, test_import_without_unreal]

MUTATIONS = [
    ("rot2 sign", "return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)",
     "return x * math.cos(a) + y * math.sin(a), x * math.sin(a) + y * math.cos(a)"),
    ("ceil -> floor", "frames = int(math.ceil(exact - FRAME_EPS))", "frames = int(math.floor(exact + FRAME_EPS))"),
    ("yaw not added", "k[\"v\"] += yaw", "k[\"v\"] += 0.0"),
    ("union disabled", "if _all_linear_const(out[\"x\"]) and _all_linear_const(out[\"y\"]):", "if False:"),
    ("translation dropped", "d = float(t[\"loc\"][i])", "d = 0.0"),
    ("solve yaw sign", "yaw = wrap(entry_cam[\"rot\"][2] - her_cam[\"rot\"][2])", "yaw = wrap(her_cam[\"rot\"][2] - entry_cam[\"rot\"][2])"),
    ("start ignores score", "return int(act[0][\"start\"]), \"our S6 score land frame", "return int(act[0][\"start\"]) + 1, \"our S6 score land frame"),
    ("glimmer overlap ignored", "g1 = section[0] + ceil_frames(gl.get(\"overlap_s\", 0.0), fps)", "g1 = section[0]"),
    ("confirm word", "CONFIRM_WORD = \"KLARAVOIDS6\"", "CONFIRM_WORD = \"KLARAVOID\""),
    ("compose yaw dropped", "float(rot[2]) + float(t[\"yaw\"])]", "float(rot[2])]"),
    ("rotator yaw/roll swap", "sy, cy = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))",
     "sy, cy = math.sin(math.radians(roll)), math.cos(math.radians(roll))"),
    ("drift check off", "if want and want != got:", "if False:"),
]


def run_all(M, quiet=False):
    results = []
    for t in TESTS:
        try:
            msg = t(M)
            results.append((t.__name__, True, msg))
        except Exception as exc:  # noqa: BLE001
            results.append((t.__name__, False, "%s: %s" % (type(exc).__name__, exc) if quiet else traceback.format_exc()))
    return results


def main():
    for p in (LS_VOID, L_VOID, LS_S6, AUDIO_REC, DOCKS):
        if not os.path.isfile(p):
            print("MISSING INPUT (cannot run byte tests): %s" % p)
            return 2
    M = load_tool()
    res = run_all(M)
    for name, ok, msg in res:
        print("%s %-40s %s" % ("PASS" if ok else "FAIL", name, msg if ok else "\n" + msg))
    passed = sum(1 for r in res if r[1])
    src = open(TOOL, encoding="utf-8").read()
    caught = 0
    for label, a, b in MUTATIONS:
        if src.count(a) != 1:
            print("MUTATION %-28s NOT APPLICABLE (pattern count %d)" % (label, src.count(a)))
            continue
        try:
            mm = load_tool(src.replace(a, b))
            r = run_all(mm, quiet=True)
            failed = [n for n, ok, _m in r if not ok]
        except Exception as exc:  # noqa: BLE001
            failed = ["import: %s" % exc]
        caught += bool(failed)
        print("MUTATION %-28s %s %s" % (label, "CAUGHT by" if failed else "MISSED", failed[:3]))
    print("SUMMARY tests %d/%d passed; mutations caught %d/%d" % (passed, len(res), caught, len(MUTATIONS)))
    return 0 if passed == len(res) and caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
