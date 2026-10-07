"""PIE-ONLY temporary glint light for the gloss4 v4 test (Gary 7 Oct: "Add test glint, re-shoot").
Python cannot spawn into the PIE world (GameplayStatics deferred spawn not exposed, measured 7 Oct), so this
BORROWS one PointLight actor of the PIE copy that sits far from P04 (|y - 240000| > 20000 cm) and moves it to
W&T's proposal W010: passage-local (4290, 382.95, 40) cm; P04 passage-local == world (x, y - 240000, z)
[measured: base stills manifest PSTILLS-P04-20261007-000620-gloss4_base]. PIE copy only: reverts when PIE ends.
Never touches the editor world; no save."""
import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_game_world()
if world is None:
    raise RuntimeError("GLOSS4_GLINT_FAILED|no PIE")
cands = []
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PointLight):
    p = a.get_actor_location()
    if abs(p.y - 240000.0) > 20000.0:
        cands.append(a)
if not cands:
    raise RuntimeError("GLOSS4_GLINT_FAILED|no far PointLight to borrow")
a = cands[0]
was = a.get_actor_location()
c = a.point_light_component
c.set_mobility(unreal.ComponentMobility.MOVABLE)
a.set_actor_location(unreal.Vector(4290.0, 240000.0 + 382.95, 200.0), False, True)
c.set_visibility(True)
c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
c.set_intensity(30000.0)
c.set_attenuation_radius(1500.0)
c.set_source_radius(3.0)
c.set_cast_shadows(False)
c.set_light_color(unreal.LinearColor(1.0, 0.85, 0.65, 1.0))
got = a.get_actor_location()
unreal.log("GLOSS4_GLINT_SPAWNED|borrowed=%s|from=%.0f,%.0f,%.0f|loc=%.1f,%.1f,%.1f|cd=%.0f|atten=%.0f|vis=%s" % (
    a.get_name(), was.x, was.y, was.z, got.x, got.y, got.z, c.get_editor_property("intensity"),
    c.get_editor_property("attenuation_radius"), c.is_visible()))
