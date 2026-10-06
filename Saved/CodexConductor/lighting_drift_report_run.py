"""Entrypoint for lighting_drift_report.py via ExecuteProjectPythonFile (READ-ONLY; no args, no confirm).

runpy.run_path executes a fresh copy every call, so the editor's Python module cache cannot serve a stale
lighting_drift_report.py (ue58-python-stale-module-cache, 2 Oct)."""
import runpy

runpy.run_path("E:/PussStage/Saved/CodexConductor/lighting_drift_report.py", run_name="lighting_drift_report")
