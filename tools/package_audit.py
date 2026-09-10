#!/usr/bin/env python3
"""Check package links, skill entry points, and the bundled example's asset integrity."""
from pathlib import Path
import json
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
errors=[];links=0;skills=[]
sys.path.insert(0,str(ROOT))
from ambiance_studio import __version__
versions={'package.json':json.loads((ROOT/'package.json').read_text())['version'],
          'package-lock.json':json.loads((ROOT/'package-lock.json').read_text())['version'],
          'pyproject.toml':re.search(r'^version\s*=\s*"([^"]+)"',(ROOT/'pyproject.toml').read_text(),re.M)[1]}
for name,version in versions.items():
    if version!=__version__:errors.append(f'{name}: version {version} differs from CLI {__version__}')
for name in ['studio/studio.mjs','editor/editor.mjs']:
    check=subprocess.run(['node','--check',str(ROOT/name)],capture_output=True,text=True)
    if check.returncode:errors.append(f'{name}: {check.stderr}')
for md in ROOT.rglob('*.md'):
    if any(part in ['archive','projects','__pycache__','node_modules','.venv'] for part in md.relative_to(ROOT).parts): continue
    body=md.read_text()
    for target in re.findall(r'\]\(([^\n)]+)\)',body):
        target=target.strip().strip('<>')
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) or target.startswith('#'): continue
        target=target.split('#')[0]
        if not target: continue
        path=(md.parent/target).resolve();links+=1
        if not path.is_relative_to(ROOT) or not path.exists(): errors.append(f'{md.relative_to(ROOT)}: broken/local-external link {target}')
for skill in sorted((ROOT/'.agents/skills').glob('*/SKILL.md')):
    text=skill.read_text();front=re.match(r'^---\n(.*?)\n---\n',text,re.S)
    if not front: errors.append(f'{skill.parent.name}: missing frontmatter');continue
    name=re.search(r'^name:\s*([a-z0-9-]+)\s*$',front[1],re.M)
    desc=re.search(r'^description:\s*"(.+)"\s*$',front[1],re.M)
    if not name or name[1]!=skill.parent.name: errors.append(f'{skill.parent.name}: name mismatch')
    if not desc or len(desc[1])>1024: errors.append(f'{skill.parent.name}: missing/oversized description')
    if '[TODO:' in text: errors.append(f'{skill.parent.name}: unfinished scaffold')
    if not (skill.parent/'agents/openai.yaml').is_file(): errors.append(f'{skill.parent.name}: missing UI metadata')
    skills.append(skill.parent.name)
result=subprocess.run([sys.executable,str(ROOT/'kit.py'),'check'],capture_output=True,text=True)
if result.returncode: errors.append('Bundled asset/scene check failed: '+result.stdout+result.stderr)
try: asset_report=json.loads(result.stdout)
except ValueError: asset_report=None
report=dict(ok=not errors,skills=skills,local_links_checked=links,
            bundled_asset_check=asset_report,errors=errors,
            limits=['No independent agent behavior trial or film review is implied.',
                    'This lightweight frontmatter check supplements the authoring-time skill validator.'])
print(json.dumps(report,indent=2));sys.exit(0 if report['ok'] else 1)
