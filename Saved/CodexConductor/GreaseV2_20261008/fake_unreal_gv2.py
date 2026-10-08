"""A small fake of the `unreal` API surface grease_v2_ue.py uses -- OFFLINE harness only (never imported in Unreal).

Models: Texture2D / Material / MaterialInstanceConstant objects persisted as JSON in <project>/Content/...uasset, an
in-memory dirty set (census), save_asset (writes the file, cleans), a Don't-Save restart (reload every object from
disk), list_assets, import_asset_tasks (creates a dirty Texture2D sized from the PNG header, with Interchange-like
defaults that differ from the live references), MaterialEditingLibrary MI getters/setters with override entries, and
fault injection (lying setters, side effects, interrupted saves, placeholder sizes).
"""
import json
import os
import struct
import types

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


class EnumVal:
    def __init__(self, enum, name):
        self.enum, self.name = enum, name

    def __eq__(self, other):
        return isinstance(other, EnumVal) and (self.enum, self.name) == (other.enum, other.name)

    def __hash__(self):
        return hash((self.enum, self.name))

    def __str__(self):
        return "<%s.%s>" % (self.enum, self.name)

    __repr__ = __str__


def enum_ns(enum, names):
    return types.SimpleNamespace(**{n: EnumVal(enum, n) for n in names})


TC = enum_ns("TextureCompressionSettings", ["TC_DEFAULT", "TC_MASKS", "TC_NORMALMAP"])
TG = enum_ns("TextureGroup", ["TEXTUREGROUP_WORLD", "TEXTUREGROUP_WORLD_NORMAL_MAP", "TEXTUREGROUP_8BIT_DATA"])
MIP = enum_ns("TextureMipGenSettings", ["TMGS_FROM_TEXTURE_GROUP", "TMGS_SIMPLE_AVERAGE", "TMGS_SHARPEN4"])
TF = enum_ns("TextureFilter", ["TF_DEFAULT", "TF_TRILINEAR", "TF_BILINEAR"])
TA = enum_ns("TextureAddress", ["TA_WRAP", "TA_CLAMP"])
ENUMS = {"compression_settings": TC, "lod_group": TG, "mip_gen_settings": MIP, "filter": TF, "address_x": TA,
         "address_y": TA}


def enc(v):
    return {"__enum__": v.name} if isinstance(v, EnumVal) else v


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    return list(struct.unpack(">II", head[16:24]))


def make(state):
    """state: project (str), objects (dict path->spec, the initial disk content), faults (dict)."""
    u = types.ModuleType("unreal")
    faults = state.setdefault("faults", {})
    u.logs = state.setdefault("logs", [])
    state.setdefault("dirty", set())
    state.setdefault("saves", [])
    state.setdefault("calls", {})
    mem = {}

    def count(name):
        state["calls"][name] = state["calls"].get(name, 0) + 1

    def cfile(path):
        return os.path.join(state["project"], "Content", *path[len("/Game/"):].split("/")) + ".uasset"

    class Obj:
        def __init__(self, path):
            self.path = path

        def get_path_name(self):
            return self.path + "." + self.path.rsplit("/", 1)[1]

        def get_name(self):
            return self.path.rsplit("/", 1)[1]

        def modify(self):
            state["dirty"].add(self.path)

    class Texture2D(Obj):
        def __init__(self, path, props, size):
            super().__init__(path)
            self.props, self.size = dict(props), list(size)

        def blueprint_get_size_x(self):
            ph = faults.get("placeholder")
            return 32 if ph and self.path in ph and ph[self.path] > 0 else self.size[0]

        def blueprint_get_size_y(self):
            ph = faults.get("placeholder")
            if ph and self.path in ph and ph[self.path] > 0:
                ph[self.path] -= 1
                return 32
            return self.size[1]

        def get_editor_property(self, k):
            return self.props[k]

        def set_editor_property(self, k, v):
            if k not in self.props:
                raise AttributeError(k)
            state["dirty"].add(self.path)
            if faults.get("tex_setter_lies") == (self.path.rsplit("/", 1)[1], k):
                return
            self.props[k] = v
            if k == "lod_group":                       # model of the INFERRED PostEditChange re-derivation
                self.props["filter"] = TF.TF_DEFAULT

        def dump(self):
            return {"cls": "Texture2D", "props": {k: enc(v) for k, v in self.props.items()}, "size": self.size}

    class Material(Obj):
        def __init__(self, path, scalars, textures):
            super().__init__(path)
            self.scalars, self.textures = dict(scalars), dict(textures)

        def dump(self):
            return {"cls": "Material", "scalars": self.scalars, "textures": self.textures}

    class MaterialInstanceConstant(Obj):
        def __init__(self, path, parent, scalars, textures):
            super().__init__(path)
            self.parent, self.scalars, self.textures = parent, dict(scalars), dict(textures)

        def get_editor_property(self, k):
            if k == "parent":
                return load(self.parent)
            if k == "texture_parameter_values":
                return [types.SimpleNamespace(parameter_info=types.SimpleNamespace(name=n), parameter_value=load(v))
                        for n, v in self.textures.items()]
            if k == "scalar_parameter_values":
                return [types.SimpleNamespace(parameter_info=types.SimpleNamespace(name=n), parameter_value=v)
                        for n, v in self.scalars.items()]
            raise AttributeError(k)

        def dump(self):
            return {"cls": "MaterialInstanceConstant", "parent": self.parent, "scalars": self.scalars,
                    "textures": self.textures}

    def build(path, d):
        if d["cls"] == "Texture2D":
            props = {k: (getattr(ENUMS[k], v["__enum__"]) if isinstance(v, dict) else v) for k, v in d["props"].items()}
            return Texture2D(path, props, d["size"])
        if d["cls"] == "Material":
            return Material(path, d["scalars"], d["textures"])
        return MaterialInstanceConstant(path, d["parent"], d["scalars"], d["textures"])

    def write_disk(obj):
        f = cfile(obj.path)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(obj.dump(), fh, sort_keys=True)

    def load(path):
        if path is None:
            return None
        path = str(path).split(".", 1)[0]
        if path in mem:
            return mem[path]
        f = cfile(path)
        if not os.path.isfile(f):
            return None
        with open(f, encoding="utf-8") as fh:
            mem[path] = build(path, json.load(fh))
        return mem[path]

    def restart_dont_save():
        mem.clear()
        state["dirty"].clear()
        state["restarts"] = state.get("restarts", 0) + 1

    def disk_seed(path, d):
        obj = build(path, d)
        write_disk(obj)

    for p, d in state.get("objects", {}).items():
        disk_seed(p, d)
    u._restart = restart_dont_save
    u._load = load
    u._mem = mem

    u.Texture2D, u.Material, u.MaterialInstanceConstant = Texture2D, Material, MaterialInstanceConstant
    u.TextureCompressionSettings = TC
    u.Paths = types.SimpleNamespace(convert_relative_path_to_full=lambda p: p,
                                    project_dir=lambda: state["project"] + "/")

    class UnrealEditorSubsystem:
        def get_editor_world(self):
            name = faults.get("world", WORLD)
            return types.SimpleNamespace(get_outermost=lambda: types.SimpleNamespace(get_name=lambda: name))

        def get_game_world(self):
            return object() if faults.get("pie") else None

    u.UnrealEditorSubsystem = UnrealEditorSubsystem
    u.get_editor_subsystem = lambda cls: cls()

    class Pkg:
        def __init__(self, p):
            self.p = p

        def get_path_name(self):
            return self.p

    u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        get_dirty_map_packages=lambda: [Pkg(WORLD)] if faults.get("map_dirty") else [],
        get_dirty_content_packages=lambda: [Pkg(p) for p in sorted(state["dirty"])])

    def does_asset_exist(p):
        return load(p) is not None

    def save_asset(p, only_if_is_dirty=True):
        count("save_asset")
        n = faults.get("raise_on_save")
        if n is not None:
            faults["raise_on_save"] = n - 1
            if n - 1 < 0:
                faults.pop("raise_on_save")
                raise RuntimeError("simulated editor exception during save (interrupt)")
        obj = load(p)
        if obj is None:
            return False
        write_disk(obj)
        state["dirty"].discard(p)
        state["saves"].append(p)
        return True

    def list_assets(d, recursive=True, include_folder=False):
        root = os.path.join(state["project"], "Content", *d[len("/Game/"):].split("/"))
        out = set()
        if os.path.isdir(root):
            for f in os.listdir(root):
                if f.endswith(".uasset"):
                    out.add(d + "/" + f[:-7])
        out |= {p for p in mem if p.rsplit("/", 1)[0] == d}
        return [p + "." + p.rsplit("/", 1)[1] for p in sorted(out)]

    u.EditorAssetLibrary = types.SimpleNamespace(does_asset_exist=does_asset_exist, load_asset=load,
                                                 save_asset=save_asset, list_assets=list_assets)
    u.load_asset = load

    class AssetImportTask:
        def __init__(self):
            self.props = {}

        def set_editor_property(self, k, v):
            self.props[k] = v

    class AssetTools:
        def import_asset_tasks(self, tasks):
            for t in tasks:
                count("import")
                p = t.props["destination_path"] + "/" + t.props["destination_name"]
                if load(p) is not None and not t.props.get("replace_existing"):
                    continue
                normal = "Normal" in p
                props = {"srgb": True, "compression_settings": TC.TC_NORMALMAP if normal else TC.TC_DEFAULT,
                         "lod_group": TG.TEXTUREGROUP_WORLD, "mip_gen_settings": MIP.TMGS_FROM_TEXTURE_GROUP,
                         "filter": TF.TF_DEFAULT, "lod_bias": 0, "never_stream": False, "max_texture_size": 0,
                         "virtual_texture_streaming": False, "address_x": TA.TA_WRAP, "address_y": TA.TA_WRAP,
                         "flip_green_channel": bool(normal)}       # Interchange-like guess the tool must override
                mem[p] = Texture2D(p, props, png_size(t.props["filename"]))
                state["dirty"].add(p)
                if faults.get("import_dirties"):
                    state["dirty"].add(faults["import_dirties"])

    u.AssetImportTask = AssetImportTask
    u.AssetToolsHelpers = types.SimpleNamespace(get_asset_tools=lambda: AssetTools())

    def parent_chain_default(m, n, kind):
        while isinstance(m, MaterialInstanceConstant):
            store = m.textures if kind == "t" else m.scalars
            if n in store:
                return store[n]
            m = load(m.parent)
        return (m.textures if kind == "t" else m.scalars)[n]

    def root_material(m):
        while isinstance(m, MaterialInstanceConstant):
            m = load(m.parent)
        return m

    def side_effects(mi):
        se = faults.get("scalar_side_effect")
        if se and mi.get_name() == se[0]:
            mi.scalars[se[1]] = se[2]
        other = faults.get("dirty_other_on_set")
        if other:
            state["dirty"].add(other)

    def set_tex(mi, n, tex):
        count("set_tex")
        state["dirty"].add(mi.path)
        lie = faults.get("tex_param_setter_lies")
        if lie and (lie is True or mi.get_name() == lie):
            return True
        mi.textures[n] = tex.path.split(".", 1)[0] if tex is not None else None
        side_effects(mi)
        return True

    def set_override(mi, n, b, *a):
        count("set_override")
        state["dirty"].add(mi.path)
        if faults.get("override_clear_lies"):
            return True
        if not b:
            mi.textures.pop(n, None)
            mi.scalars.pop(n, None)
        return True

    def get_tex(mi, n, *a):
        v = parent_chain_default(mi, n, "t")
        return load(v)

    u.MaterialEditingLibrary = types.SimpleNamespace(
        get_scalar_parameter_names=lambda m: sorted(root_material(m).scalars),
        get_texture_parameter_names=lambda m: sorted(root_material(m).textures),
        get_material_default_texture_parameter_value=lambda m, n: load(m.textures.get(n)),
        get_material_instance_texture_parameter_value=get_tex,
        set_material_instance_texture_parameter_value=set_tex,
        is_material_instance_parameter_overridden=lambda mi, n, *a: (n in mi.textures or n in mi.scalars)
        if not faults.get("probe_lies") else False,
        set_material_instance_parameter_override=set_override,
        get_material_instance_scalar_parameter_value=lambda mi, n, *a: float(parent_chain_default(mi, n, "s")),
        update_material_instance=lambda mi: count("update"),
    )
    u.SystemLibrary = types.SimpleNamespace(collect_garbage=lambda: count("gc"))
    u.log = lambda m: u.logs.append(("log", m))
    u.log_warning = lambda m: u.logs.append(("warning", m))
    u.log_error = lambda m: u.logs.append(("error", m))
    return u
