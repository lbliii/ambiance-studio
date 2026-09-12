"""Inventory and reversible retirement of unreferenced generated artifact bundles."""
from .command_output import Output, add_output
from collections import defaultdict
import json
from pathlib import Path
import re
import time
import uuid

import studio
from . import revisions
from .project import project_lock

PLAN = 'ambiance-cleanup-plan'
RECEIPT = 'ambiance-cleanup-receipt'
MARKERS = {'render-report.json', 'compose-report.json', 'activity-report.json', 'benchmark.json', 'views-proof.json'}
METADATA = ('.ambiance/cleanup/', '.ambiance/trash/')


def add_parsers(group):
    group.add_parser('storage')
    sub = group.add_parser('cleanup').add_subparsers(dest='cleanup_action', required=True)
    q = sub.add_parser('plan'); q.add_argument('--keep-days', type=int, default=30); q.add_argument('--include', action='append', default=[]); add_output(q, Output.FILE, type=Path, required=True)
    q = sub.add_parser('apply'); q.add_argument('file', type=Path)
    q = sub.add_parser('restore'); q.add_argument('id')
    q = sub.add_parser('inspect'); q.add_argument('id')


def files(project):
    for path in project.rglob('*'):
        relative = str(path.relative_to(project))
        if any(part.startswith('.git') for part in path.relative_to(project).parts): continue
        if relative.startswith(METADATA): continue
        if path.is_symlink(): continue
        if path.is_file(): yield path


def audit(project):
    groups = defaultdict(lambda: {'files': 0, 'json_files': 0, 'bytes': 0}); duplicates = defaultdict(list); largest = []
    for path in files(project):
        relative = str(path.relative_to(project)); size = path.stat().st_size; group = relative.split('/')[0]
        row = groups[group]; row['files'] += 1; row['bytes'] += size
        if path.suffix == '.json':
            row['json_files'] += 1; duplicates[studio.digest(path)].append((relative, size))
        largest.append({'path': relative, 'bytes': size})
    duplicate_groups = [rows for rows in duplicates.values() if len(rows) > 1]
    return {'ok': True, 'format': 'ambiance-storage-overview', 'schema_version': 1,
            'groups': dict(sorted(groups.items())), 'files': sum(g['files'] for g in groups.values()),
            'json_files': sum(g['json_files'] for g in groups.values()), 'bytes': sum(g['bytes'] for g in groups.values()),
            'identical_json_groups': len(duplicate_groups), 'identical_json_extra_bytes': sum((len(g)-1)*g[0][1] for g in duplicate_groups),
            'largest': sorted(largest, key=lambda r: -r['bytes'])[:8],
            'meaning': 'Identical JSON can represent distinct captures or evidence. Duplication alone does not make it disposable.',
            'next': ['project', 'cleanup', 'plan', '--keep-days', '30', '--out', '.ambiance/cleanup/plans/cleanup-plan.json']}


def roots(project, selected):
    if selected:
        result = [studio.inside(project, value) for value in selected]
    else:
        result = [p for p in (project/'reports').glob('*') if p.is_dir()]
        result += [p for p in (project/'runs').glob('*/*') if p.is_dir()]
    valid = []
    for path in result:
        relative = path.relative_to(project)
        if relative.parts[0] not in ['reports', 'runs'] or len(relative.parts) < (3 if relative.parts[0] == 'runs' else 2):
            raise ValueError('Cleanup accepts generated report bundles or individual run attempts only')
        if path.is_symlink() or not path.is_dir() or not any((path/name).is_file() for name in MARKERS):
            if selected: raise ValueError('Bundle lacks a recognized generated-artifact receipt: '+str(relative))
            continue
        if any(p.is_symlink() for p in path.rglob('*')): raise ValueError('Cleanup refuses symlink-containing bundles')
        valid.append(path)
    if len(set(valid)) != len(valid) or any(a != b and a.is_relative_to(b) for a in valid for b in valid):
        raise ValueError('Cleanup bundles must be distinct and nonoverlapping')
    return sorted(valid)


def inventory(project, root):
    return [dict(path=str(p.relative_to(project)), sha256=studio.digest(p), bytes=p.stat().st_size)
            for p in sorted(root.rglob('*')) if p.is_file()]


def analyze(project, selected, keep_days):
    if type(keep_days) is not int or not 0 <= keep_days <= 36500: raise ValueError('Keep-days must be an integer from 0 to 36500')
    candidates = []; protected = []; cutoff = time.time()-keep_days*86400
    for root in roots(project, selected):
        relative = str(root.relative_to(project)); contents = list(root.rglob('*'))
        if any(p.stat().st_mtime > cutoff for p in [root, *contents]):
            protected.append({'path': relative, 'reason': 'Inside retention period'}); continue
        if root.relative_to(project).parts[0] == 'runs':
            run = root.parent/'run.json'
            if not run.is_file() or studio.read(run).get('state') not in ['complete', 'failed', 'interrupted']:
                protected.append({'path': relative, 'reason': 'Run ownership/state requires inspection first'}); continue
        candidates.append({'path': relative, 'files': inventory(project, root)})
    # Every document outside the proposed bundles is a protection root. This is
    # intentionally conservative: captured references and loose authored notes
    # both protect evidence; no aesthetic or filename-based approval is inferred.
    all_files = list(files(project)); active = {c['path']: c for c in candidates}; blockers = {}
    if not candidates: return {'eligible': [], 'protected': protected}
    texts = []
    for path in all_files:
        if path.suffix.lower() not in ['.json', '.yaml', '.yml', '.md', '.txt']: continue
        try: text = path.read_text()
        except (OSError, UnicodeError):
            raise ValueError('Cannot establish cleanup reference closure: '+str(path.relative_to(project)))
        references = re.findall(r'\]\(([^)]+)\)', text)
        def strings(value):
            if isinstance(value, str): references.append(value)
            elif isinstance(value, dict):
                for child in value.values(): strings(child)
            elif isinstance(value, list):
                for child in value: strings(child)
        if path.suffix == '.json' and text.strip():
            try: strings(json.loads(text))
            except (ValueError, RecursionError): raise ValueError('Unreadable JSON prevents safe cleanup: '+str(path.relative_to(project)))
        elif path.suffix.lower() in ['.yaml', '.yml']:
            import yaml
            try:
                # Read scalar references without constructing objects or losing
                # duplicate mapping entries. Aliases can contain cycles.
                root_node = yaml.compose(text, Loader=yaml.SafeLoader); visited = set()
                def yaml_strings(node):
                    if node is None or id(node) in visited: return
                    visited.add(id(node))
                    if isinstance(node, yaml.ScalarNode): references.append(node.value)
                    elif isinstance(node, yaml.SequenceNode):
                        for child in node.value: yaml_strings(child)
                    elif isinstance(node, yaml.MappingNode):
                        for key, child in node.value: yaml_strings(key); yaml_strings(child)
                yaml_strings(root_node)
            except (yaml.YAMLError, RecursionError):
                raise ValueError('Unreadable YAML prevents safe cleanup: '+str(path.relative_to(project)))
        targets = set()
        for ref in references:
            if '://' in ref or '\n' in ref or len(ref) > 1000: continue
            ref = ref.strip('<>').split('#')[0]
            for base in [project, path.parent]:
                try: target = (base/ref).resolve()
                except (OSError, ValueError): continue
                if target.is_relative_to(project): targets.add(str(target.relative_to(project)))
        texts.append((str(path.relative_to(project)), text, set(re.findall(r'\b[0-9a-f]{64}\b', text)), targets))
    while True:
        changed = False
        for source, text, hashes, targets in texts:
            if any(source.startswith(name+'/') for name in active): continue
            for name, candidate in list(active.items()):
                if name in text or any(t == name or t.startswith(name+'/') for t in targets) or any(f['sha256'] in hashes or f['path'] in text for f in candidate['files']):
                    blockers[name] = source; del active[name]; changed = True
        if not changed: break
    for candidate in candidates:
        if candidate['path'] in blockers: protected.append({'path': candidate['path'], 'reason': 'Referenced by '+blockers[candidate['path']]})
    return {'eligible': list(active.values()), 'protected': protected}


def plan(project, selected, keep_days, out):
    project = project.resolve(); out = Path(out).resolve()
    if out.exists(): raise ValueError('Cleanup plan output must be fresh')
    if out.is_relative_to(project) and not out.is_relative_to(project/'.ambiance/cleanup/plans'):
        raise ValueError('Save project-local cleanup plans under .ambiance/cleanup/plans, or choose an external output file')
    with project_lock(project):
        result = analyze(project, selected, keep_days)
        data = revisions.seal({'format': PLAN, 'schema_version': 1, 'id': uuid.uuid4().hex,
            'project': str(project), 'created_utc': time.time(), 'keep_days': keep_days, **result,
            'operation': 'Move eligible bundles to project-local recoverable trash. No permanent deletion.'})
        studio.write(out, data)
    return {'ok': True, 'plan': str(out), 'sha256': studio.digest(out), 'eligible_bundles': len(data['eligible']),
            'eligible_files': sum(len(c['files']) for c in data['eligible']),
            'eligible_bytes': sum(f['bytes'] for c in data['eligible'] for f in c['files']),
            'protected_count': len(data['protected']), 'protected': data['protected'][:8], 'operation': data['operation']}


def receipt_path(project, id):
    return studio.inside(project, '.ambiance/cleanup/'+revisions.identifier(id)+'.json')


def apply(project, path):
    project = project.resolve(); path = Path(path).resolve(); data = revisions.read_sealed(path, PLAN)
    if data['project'] != str(project): raise ValueError('Cleanup plan belongs to another project')
    if not data['eligible']: return {'ok': True, 'moved_bundles': 0, 'meaning': 'Nothing eligible under this plan.'}
    with project_lock(project):
        destination = project/'.ambiance/trash'/data['id']; receipt = receipt_path(project, data['id'])
        if destination.exists() or receipt.exists(): raise ValueError('Cleanup already started; inspect/restore its receipt')
        # The plan itself must not act as a new evidence root when saved locally.
        current = analyze(project, [c['path'] for c in data['eligible']], data['keep_days'])
        if current['eligible'] != data['eligible']: raise ValueError('Cleanup inputs, age or references changed; make a fresh plan')
        saved = dict(format=RECEIPT, schema_version=1, id=data['id'], project=str(project), state='moving', bundles=data['eligible'])
        studio.write(receipt, revisions.seal(saved)); destination.mkdir(parents=True)
        moved = []
        try:
            for candidate in data['eligible']:
                source = studio.inside(project, candidate['path']); target = studio.inside(destination, candidate['path'])
                target.parent.mkdir(parents=True, exist_ok=True); source.rename(target); moved.append((source, target))
        except BaseException:
            for source, target in reversed(moved): target.rename(source)
            saved['state'] = 'rolled-back'; studio.write(receipt, revisions.seal(saved)); raise
        saved['state'] = 'quarantined'; studio.write(receipt, revisions.seal(saved))
    return {'ok': True, 'id': data['id'], 'moved_bundles': len(moved), 'receipt': str(receipt),
            'restore_argv': ['./ambiance', '--project', str(project), 'project', 'cleanup', 'restore', data['id']],
            'meaning': 'Recoverable project-local trash; disk space is retained until explicitly purged outside this command.'}


def restore(project, id):
    project = project.resolve()
    with project_lock(project):
        path = receipt_path(project, id); saved = revisions.read_sealed(path, RECEIPT)
        if saved['project'] != str(project) or saved['state'] not in ['moving', 'quarantined', 'restoring']: raise ValueError('Cleanup is not recoverable in this state')
        pending = []
        for bundle in saved['bundles']:
            target = studio.inside(project, bundle['path']); source = studio.inside(project/'.ambiance/trash'/id, bundle['path'])
            expected = {f['path'][len(bundle['path'])+1:]: (f['sha256'], f['bytes']) for f in bundle['files']}
            if not source.exists() and saved['state'] in ['moving', 'restoring']:
                actual = {str(p.relative_to(target)): (studio.digest(p), p.stat().st_size) for p in target.rglob('*') if p.is_file()}
                if actual != expected: raise ValueError('Partially restored bundle differs: '+bundle['path'])
                continue
            if target.exists(): raise ValueError('Restore destination is occupied: '+bundle['path'])
            actual = {str(p.relative_to(source)): (studio.digest(p), p.stat().st_size) for p in source.rglob('*') if p.is_file()}
            if actual != expected: raise ValueError('Quarantined bundle changed: '+bundle['path'])
            pending.append((source, target))
        saved['state'] = 'restoring'; studio.write(path, revisions.seal(saved))
        for source, target in pending: target.parent.mkdir(parents=True, exist_ok=True); source.rename(target)
        saved['state'] = 'restored'; studio.write(path, revisions.seal(saved))
    return {'ok': True, 'id': id, 'restored_bundles': len(pending), 'receipt': str(path)}


def run(args, project):
    if args.action == 'storage': return audit(project)
    if args.cleanup_action == 'plan': return plan(project, args.include, args.keep_days, args.out)
    if args.cleanup_action == 'apply': return apply(project, args.file)
    if args.cleanup_action == 'restore': return restore(project, args.id)
    return {'ok': True, 'receipt': revisions.read_sealed(receipt_path(project, args.id), RECEIPT)}
