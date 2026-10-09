"""Project-Saved entry point for p96_editor.py."""
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
runpy.run_path(os.path.join(HERE, "p96_editor.py"), run_name="__main__")
