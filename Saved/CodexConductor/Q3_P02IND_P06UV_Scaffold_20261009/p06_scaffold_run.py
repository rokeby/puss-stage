import importlib.util, os
p=os.path.join(os.path.dirname(os.path.abspath(__file__)),"p06_scaffold_install.py");s=importlib.util.spec_from_file_location("p06_scaffold_install",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.main()
