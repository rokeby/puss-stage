"""Build the real site against mock services + real Code.gs; --browser-harness adds the automated runner."""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), 'site')
OUT = os.path.join(HERE, '_build')
shutil.rmtree(OUT, ignore_errors=True)
shutil.copytree(SITE, OUT)
with open(os.path.join(OUT, 'config.js'), 'w', encoding='utf-8', newline='\n') as f:
    for part in (os.path.join(HERE, 'mock_services.js'), os.path.join(os.path.dirname(HERE), 'apps_script', 'Code.gs')):
        with open(part, encoding='utf-8') as src:
            f.write(src.read() + '\n')
runner = os.path.join(HERE, 'browser_harness.js')
if '--browser-harness' in sys.argv and os.path.exists(runner):
    shutil.copy2(runner, os.path.join(OUT, 'browser_harness.js'))
    page = os.path.join(OUT, 'index.html')
    with open(page, encoding='utf-8') as f:
        html = f.read()
    html = html.replace('</body>', '<script src="browser_harness.js"></script>\n</body>')
    with open(page, 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)
print('CUEBOOK_TEST_BUILD_OK', OUT)
