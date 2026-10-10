"""Separate conductor-scheduled PIE probe for Job 99; never starts/stops PIE."""
import importlib.util
import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p99_s6_arrival_sun.py")
spec = importlib.util.spec_from_file_location("p99_s6_arrival_sun_probe", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.run_pie_probe()

