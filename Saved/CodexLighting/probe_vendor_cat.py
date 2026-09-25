"""Read-only: the vendor CharBP_Cat_R class defaults — mesh component relative transform and skeletal mesh."""
import unreal
def vec(v): return [round(v.x,2), round(v.y,2), round(v.z,2)]
def rot(r): return [round(r.pitch,3), round(r.yaw,3), round(r.roll,3)]
out = {}
bp = unreal.EditorAssetLibrary.load_asset("/Game/CharacterPacks/AnimX/Cats/Realistic/CharBP_Cat_R")
cls = bp.generated_class()
cdo = unreal.get_default_object(cls)
out["class"] = cls.get_name(); out["parent"] = cls.get_super_class().get_name() if hasattr(cls, "get_super_class") else "?"
try:
    mesh = cdo.get_editor_property("mesh")
    out["mesh_rel_loc"] = vec(mesh.get_editor_property("relative_location")); out["mesh_rel_rot"] = rot(mesh.get_editor_property("relative_rotation"))
    out["mesh_rel_scale"] = vec(mesh.get_editor_property("relative_scale3d"))
    sk = mesh.get_editor_property("skeletal_mesh_asset"); out["skeletal_mesh"] = sk.get_path_name() if sk else None
    out["anim_mode"] = str(mesh.get_editor_property("animation_mode")); ac = mesh.get_editor_property("anim_class"); out["anim_class"] = ac.get_name() if ac else None
except Exception as exc:
    out["mesh_error"] = repr(exc)
# skeletal mesh import info: forward axis hints
try:
    sk = unreal.EditorAssetLibrary.load_asset("/Game/CharacterPacks/AnimX/Cats/Realistic/Mesh/SK_Cat_R")
    b = sk.get_bounds(); out["sk_bounds_origin"] = vec(b.origin); out["sk_bounds_extent"] = vec(b.box_extent)
    out["sk_bones"] = [str(sk.get_editor_property("skeleton").get_reference_pose().bone_names[i]) if False else "" for i in range(0)]
except Exception as exc:
    out["sk_error"] = repr(exc)
unreal.log("PUSS_VENDOR_CAT|" + str(out))
