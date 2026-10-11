from pathlib import Path

text = (Path(__file__).parent / "job185_s1_fade.py").read_text(encoding="utf-8")
checks = {
    "Puss-owned sequence only": 'SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"' in text,
    "proven UE58 root-track API": 'seq.add_track(unreal.MovieSceneFadeTrack)' in text,
    "linear display-rate keys": 'MovieSceneTimeUnit.DISPLAY_RATE' in text and 'MovieSceneKeyInterpolation.LINEAR' in text,
    "float-tolerant key readback": 'abs(float(a[1]) - float(b[1])) < 0.0001' in text,
    "fire hold timing": '[3870, 0.90]' in text,
    "near-black by 3880": '[3880, 0.985]' in text,
    "black by 3899": '[3899, 1.0]' in text,
    "clean guards": 'PRE_DIRTY|' in text and 'POST_SAVE_DIRTY' in text,
    "targeted save": 'save_asset(SCENE, only_if_is_dirty=True)' in text,
    "no Save All": 'save_all' not in text.lower(),
    "no Klara mutation": 'KLARA' not in text and 'L_Animals' not in text,
}
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
if not all(checks.values()):
    raise SystemExit(1)

stills = (Path(__file__).parent / "job185_s1_stills.py").read_text(encoding="utf-8")
assert 'FRAMES = [3600, 3700, 3800, 3850, 3880, 3899]' in stills
assert all(("185_" in line) for line in stills.splitlines() if 's1_frame' in line)
assert 'editor_request_end_play' not in stills and 'save_' not in stills
assert 'scrub_to_master_frame(u.FrameNumber(original))' in stills
print("PASS six-frame owned-PIE still driver")
