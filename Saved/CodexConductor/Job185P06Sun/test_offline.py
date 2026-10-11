from pathlib import Path

text = (Path(__file__).parent / "job185_p06_sun_probe.py").read_text(encoding="utf-8")
checks = {
    "owned pie required": 'NO_OWNED_PIE' in text,
    "exact P06": 'str(s.label) == "Passage 6"' in text,
    "sun atmosphere flag": '"atmosphere_sun_light"' in text,
    "source angle": '"light_source_angle"' in text,
    "sky runtime visibility": 'SkyAtmosphereComponent' in text,
    "camera exposure": 'auto_exposure_bias' in text,
    "restores transport": 'scrub_to_master_frame(u.FrameNumber(original))' in text,
    "no save": 'save_' not in text,
    "no editor mutation": 'set_editor_property' not in text,
}
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
if not all(checks.values()):
    raise SystemExit(1)

trial = (Path(__file__).parent / "job185_p06_sun_intensity_trial.py").read_text(encoding="utf-8")
assert 'set_editor_property("intensity", TRIAL_INTENSITY)' in trial
assert 'set_editor_property("intensity", state["original_intensity"])' in trial
assert 'save_' not in trial and 'editor_request_end_play' not in trial
print("PASS transient intensity trial restores and never saves")

apply = (Path(__file__).parent / "job185_p06_sun_intensity_apply.py").read_text(encoding="utf-8")
assert 'MovieSceneCompletionMode.RESTORE_STATE' in apply
assert 'set_property_name_and_path("Intensity", "Intensity")' in apply
assert 'save_asset(MASTER, only_if_is_dirty=True)' in apply and 'save_current_level' not in apply
assert 'EditorLoadingAndSavingUtils' in apply and 'ACTIVE_RECORD_EXISTS' in apply
print("PASS guarded master-only intensity APPLY/READBACK")
