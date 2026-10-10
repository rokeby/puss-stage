import importlib.util, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(HERE, "job178_stagefront_uplights.py")
name = "job178_stagefront_uplights_live"
if name in sys.modules: del sys.modules[name]
spec = importlib.util.spec_from_file_location(name, path)
module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
module.main()
