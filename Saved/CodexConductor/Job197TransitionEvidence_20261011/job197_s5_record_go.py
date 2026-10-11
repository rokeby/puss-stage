import builtins
import unreal

name = "PUSS_JOB197_S5_RECORD_STATE"
state = getattr(builtins, name, None)
if not isinstance(state, dict) or state.get("status") != "ready" or state.get("run") != "J197-S5-RECORD-A2":
    raise RuntimeError("JOB197_S5_RECORD_GO_FAILED|state=%r" % state)
state["go"] = True
unreal.log("JOB197_S5_RECORD_GO_OK|run=%s" % state["run"])
