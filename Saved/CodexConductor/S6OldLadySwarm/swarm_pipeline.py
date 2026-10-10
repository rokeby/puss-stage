"""Pure pipeline ordering contract for Job 100 (no Unreal import)."""
from __future__ import annotations

import os


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HAND_SAMPLES = os.path.join(HERE, "hand_samples.json")
DRIVE_CURVES = os.path.join(PROJECT, "DerivedAssets", "S6OldLadySwarm", "s6_old_lady_swarm_drive.json")
STEP_IDS = ("EDITOR_READ_ONLY_HAND_SAMPLE", "OFFLINE_CURVE_GENERATION", "NON_PIE_DRY")
COMMANDS = (
    "Execute Saved/CodexConductor/S6OldLadySwarm/sample_hands.py via sample_hands_request.json; require S6_OLD_LADY_HAND_SAMPLE_OK",
    "python Tools/Mocap/s6_old_lady_swarm.py Saved/CodexConductor/S6OldLadySwarm/hand_samples.json --json DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_drive.json --png DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_curves.png",
    "Execute Saved/CodexConductor/S6OldLadySwarm/swarm_sequence.py via swarm_sequence_request.json in DRY; require S6_SWARM_SEQUENCE_DRY_OK",
)


def pipeline_state(hand_samples_exists, drive_curves_exists):
    if drive_curves_exists and not hand_samples_exists:
        raise ValueError("CURVES_WITHOUT_HAND_SAMPLES_PROVENANCE")
    if not hand_samples_exists:
        index = 0
    elif not drive_curves_exists:
        index = 1
    else:
        index = 2
    return {"next_step": STEP_IDS[index], "next_command": COMMANDS[index],
            "ready_for_dry": index == 2, "ordered_steps": list(STEP_IDS)}

