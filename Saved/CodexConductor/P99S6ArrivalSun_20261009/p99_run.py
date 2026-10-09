import importlib.util, os
p=os.path.join(os.path.dirname(os.path.abspath(__file__)),"p99_s6_arrival_sun.py")
s=importlib.util.spec_from_file_location("p99_s6_arrival_sun",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.main()
