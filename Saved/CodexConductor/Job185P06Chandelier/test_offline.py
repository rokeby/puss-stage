from pathlib import Path

text = (Path(__file__).parent / "job185_chandelier_scale.py").read_text(encoding="utf-8")
checks = {
    "exact candle prefix": 'PREFIX = "P56_P75_P06_Chandelier_Body_Candle_"' in text,
    "exact niagara asset": 'FLAME_ASSET = "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_1"' in text,
    "exact 44 scope": 'len(candles) == 44' in text,
    "nine lights preserved": 'len(lights) == 9' in text,
    "clean precondition": '"PRE_DIRTY|"' in text,
    "level-only save": 'save_current_level()' in text,
    "attached actor dirtied": 'actor.modify()' in text,
    "blueprint sprite scale": 'set_editor_property("sprite_scale", target)' in text,
    "sprite scale readback": 'SPRITE_SCALE_READBACK' in text,
    "no save all": 'save_all' not in text.lower(),
    "no delete": 'destroy_actor' not in text and 'os.remove' not in text,
    "no swarm selector": 'gold' not in text.lower() and 'swarm' not in text.lower(),
}
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
if not all(checks.values()):
    raise SystemExit(1)

probe = (Path(__file__).parent / "job185_chandelier_pie_probe.py").read_text(encoding="utf-8")
assert 'get_editor_property("exposed_parameters")' in probe and 'get_parameters' in probe
assert 'set_' not in probe and 'save_' not in probe and 'destroy_' not in probe
print("PASS read-only PIE parameter probe")
