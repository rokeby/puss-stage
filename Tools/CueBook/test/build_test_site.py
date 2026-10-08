"""Builds Tools/CueBook/test/_build: the real site, with config.js replaced by the mock services + the REAL Code.gs."""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), 'site')
OUT = os.path.join(HERE, '_build')
shutil.rmtree(OUT, ignore_errors=True)
shutil.copytree(SITE, OUT)
with open(os.path.join(OUT, 'config.js'), 'w', encoding='utf-8', newline='\n') as f:
    for part in (os.path.join(HERE, 'mock_services.js'), os.path.join(os.path.dirname(HERE), 'apps_script', 'Code.gs')):
        with open(part, encoding='utf-8') as src:
            f.write(src.read() + '\n')
print('CUEBOOK_TEST_BUILD_OK', OUT)
