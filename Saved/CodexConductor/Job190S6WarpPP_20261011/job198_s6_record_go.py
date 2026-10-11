import builtins
import unreal

name = "PUSS_JOB198_S6_RECORD_STATE"
state = getattr(builtins, name, None)
if not isinstance(state, dict) or state.get("status") != "ready" or state.get("run") != "J198-S6-RECORD-A3":
    raise RuntimeError("JOB198_S6_RECORD_GO_FAILED|state=%r" % state)
state["go"] = True
unreal.log("JOB198_S6_RECORD_GO_OK|run=%s" % state["run"])
