"""Plain-Python controls for s3_cast_reveal_apply.plan."""
import sys

import s3_cast_reveal_apply as subject


W0, W1 = -5.8739, 4.1261
ROOT_KEYS = [[W0, -90.0], [W1, 0.0]]
FULL_LABELS = list(subject.ALL_TARGET_LABELS)


def main():
    failures = 0

    planned = subject.plan(FULL_LABELS, ROOT_KEYS, W0, W1)
    positive = (
        len(planned["reveals"]) == 9
        and planned["reveal_s"] == 4.6261
        and len(planned["removals"]) == 4
    )
    if positive:
        print("PASS positive control: 9 reveals at 4.6261 s and 4 removals")
    else:
        print("FAIL positive control: expected 9 reveals at 4.6261 s and 4 removals")
        failures += 1

    try:
        subject.plan([label for label in FULL_LABELS if label != "Shore03_M59 Clam"], ROOT_KEYS, W0, W1)
    except ValueError:
        print("PASS negative control a: FAIL observed as required (missing Shore actor refused)")
    else:
        print("FAIL negative control a: missing Shore actor was accepted")
        failures += 1

    try:
        subject.plan(FULL_LABELS + ["PointLight"], ROOT_KEYS, W0, W1)
    except ValueError:
        print("PASS negative control b: FAIL observed as required (duplicate PointLight refused)")
    else:
        print("FAIL negative control b: duplicate PointLight was accepted")
        failures += 1

    try:
        subject.plan(FULL_LABELS, [[-3.567, -90.0], [16.0, 0.0]], W0, W1)
    except ValueError:
        print("PASS negative control c: FAIL observed as required (old root keys refused)")
    else:
        print("FAIL negative control c: old root keys were accepted")
        failures += 1

    original_delay = subject.REVEAL_DELAY_S
    try:
        subject.REVEAL_DELAY_S = -0.5
        subject.plan(FULL_LABELS, ROOT_KEYS, W0, W1)
    except ValueError:
        print("PASS negative control d: FAIL observed as required (reveal before W1 refused)")
    else:
        print("FAIL negative control d: reveal before W1 was accepted")
        failures += 1
    finally:
        subject.REVEAL_DELAY_S = original_delay

    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
