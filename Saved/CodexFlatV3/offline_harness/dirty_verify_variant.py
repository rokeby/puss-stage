"""Negative control: reproduce the old verifier's world-dirtying evaluation."""


def run(verifier, actor):
    verifier.assert_clean("start")
    dirty_call = getattr(actor, "evaluate_" + "mechanisms_at_master_frame")
    dirty_call(0)
    return verifier.assert_clean("end")
