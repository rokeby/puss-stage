import importlib.util, os, sys
HERE=os.path.dirname(os.path.abspath(__file__));path=os.path.join(HERE,"job178_p06_sun_disc.py");name="job178_p06_sun_disc_live"
if name in sys.modules:del sys.modules[name]
spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);m.main()
