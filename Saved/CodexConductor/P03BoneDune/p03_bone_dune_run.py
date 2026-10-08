"""MCP project-Python runner for p03_bone_dune_ue.py."""
import os
import runpy

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p03_bone_dune_ue.py")
runpy.run_path(path, run_name="__p03_bone_dune_runner__")
