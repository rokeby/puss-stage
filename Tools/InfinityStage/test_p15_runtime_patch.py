#!/usr/bin/env python3
"""Static positive/negative controls for the held P15 runtime patch."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "Scripts" / "patches" / "P15VideoTransitions"
CPP = (BUNDLE / "InfinityStageVideoTransitionSubsystem.cpp").read_text(encoding="utf-8")
HEADER = (BUNDLE / "InfinityStageVideoTransitionSubsystem.h").read_text(encoding="utf-8")
BUILD = (BUNDLE / "InfinityStage.Build.cs.patch").read_text(encoding="utf-8")

positive = {
    "single master clock": "GetCurrentMasterFrame" in CPP and "SequencePlayer->IsPlaying" in CPP,
    "scene only": "Segment.Type != EInfinityCueType::Scene" in CPP,
    "frame-zero mapping": "MasterFrame - SceneStart" in CPP,
    "jump and scrub seek": "Player->Seek(Wanted)" in CPP and "ErrorFrames > 0.5" in CPP,
    "missing file black": "P15_VIDEO_FILE_MISSING" in CPP and "Image->SetVisibility(EVisibility::Hidden)" in CPP,
    "open failure marker": "P15_VIDEO_OPEN_FAILED" in CPP,
    "fit presentation": "EStretch::ScaleToFit" in CPP,
    "exclusive audio": "bUeOwnsAudio ? 1.0f : 0.0f" in CPP,
    "runtime media deps": all(name in BUILD for name in ('"MediaAssets"', '"Slate"', '"SlateCore"')),
    "world auto-create": "UTickableWorldSubsystem" in HEADER,
}
negative = {
    "no second level-sequence player": "CreateLevelSequencePlayer" not in CPP,
    "no master transport mutation": all(token not in CPP for token in ("ScrubToMasterFrame", "PlayForwardToBoundary", "SetPlaybackPosition")),
    "no unconditional media audio": "SetVolumeMultiplier(1.0f)" not in CPP,
    "no editor-only execution": "IsTickableInEditor() const override { return false; }" in HEADER,
}

failed = [name for name, ok in {**positive, **negative}.items() if not ok]
if failed:
    raise SystemExit("P15_RUNTIME_PATCH_FAILED|" + ",".join(failed))
print("P15_RUNTIME_PATCH_OK|positive=%d|negative=%d" % (len(positive), len(negative)))
