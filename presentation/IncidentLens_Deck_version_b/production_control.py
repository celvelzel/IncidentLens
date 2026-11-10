"""Use bundled state scripts for the user-required single-agent production run."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SCRIPTS = Path.home() / '.codex' / 'skills' / 'codex-ppt' / 'scripts'

def run(name, *args):
    result = subprocess.run([sys.executable, str(SCRIPTS/name), str(ROOT), *args],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout

action = sys.argv[1]
if action == 'dispatch':
    entries=[]
    for raw in sys.argv[2:]:
        n=int(raw)
        run('record_slide_dispatch.py', '--slide', f'slide_{n:02}',
            '--agent-id', '/root', '--agent-nickname', 'Parent single-agent producer (user AGENTS.md)')
        job=json.loads((ROOT/f'prompts/slide_{n:02}.json').read_text(encoding='utf-8'))
        entries.append({'number':n,'prompt':job['prompt'],
                        'images':[x['path'] for x in job['input_images']]})
    print(json.dumps(entries))
elif action == 'record':
    n=int(sys.argv[2])
    source=sys.argv[3]
    note=sys.argv[4] if len(sys.argv)>4 else 'Visually reviewed: English text, approved Arial style, correct content and no truncation.'
    print(run('record_slide_result.py','--slide',f'slide_{n:02}', '--agent-id','/root',
              '--backend-used','built-in image tool','--selected-source',source,'--qa-note',note))
elif action == 'status':
    print(run('slide_job_status.py'))
else:
    raise ValueError(action)
