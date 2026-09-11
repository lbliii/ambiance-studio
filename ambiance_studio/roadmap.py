"""Validate roadmap references without treating planned capabilities as executable commands."""
import argparse
import json
import re
from pathlib import Path


def check_capabilities(root, cli_parser=None):
    """Check documented command routes by inspecting argparse; never run a command."""
    root = Path(root).resolve()
    data = json.loads((root / 'docs/CAPABILITIES.json').read_text())
    errors = []
    if data.get('format') != 'ambiance-capability-index' or data.get('schema_version') != 1:
        errors.append('Unsupported capability index format/version')
    if cli_parser is None:
        from .cli import parser
        cli_parser = parser()
    seen = set()
    for row in data.get('capabilities', []):
        id = row.get('id')
        if not isinstance(id, str) or not re.fullmatch(r'[a-z][a-z0-9-]+', id) or id in seen:
            errors.append('Capability IDs must be unique lowercase identifiers')
        seen.add(id)
        status = row.get('status')
        if status not in {'implemented', 'limited', 'planned'}:
            errors.append(str(id) + ': unsupported status')
        routes = row.get('public_cli', [])
        if status == 'planned' and routes:
            errors.append(str(id) + ': planned capability must not advertise callable routes')
            continue
        if status != 'planned' and not routes:
            errors.append(str(id) + ': implemented capability needs a public CLI route')
        for route in routes:
            current = cli_parser
            if not isinstance(route, list) or not route or any(not isinstance(x, str) for x in route):
                errors.append(str(id) + ': command route must be nonempty tokens'); continue
            for token in route:
                choices = [a.choices for a in current._actions if isinstance(a, argparse._SubParsersAction)]
                child = next((options[token] for options in choices if token in options), None)
                if child is None:
                    errors.append(str(id) + ': unregistered command route ' + ' '.join(route)); break
                current = child
        for ref in row.get('references', []):
            path = (root / ref).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                errors.append(str(id) + ': missing/escaped capability reference ' + str(ref))
        if not row.get('references') or not row.get('limits'):
            errors.append(str(id) + ': references and capability limits are required')
    if not seen:
        errors.append('Capability index is empty')
    return {'ok': not errors, 'count': len(seen), 'errors': errors,
            'limits': ['Routes are inspected without executing production operations.',
                       'Registered routes and references do not establish readiness or artistic approval.']}


def check(root):
    import yaml
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node, deep=False):
        pairs = loader.construct_pairs(node, deep=deep)
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate roadmap key: ' + str(key))
            result[key] = value
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    root = Path(root).resolve()
    source = root / 'docs/architecture/PRODUCTION-IMPROVEMENTS.yaml'
    plan = yaml.load(source.read_text(), Loader=UniqueLoader)
    errors = []
    if plan.get('format') != 'ambiance-improvement-roadmap' or plan.get('schema_version') != 1:
        errors.append('Unsupported roadmap format/version')
    tasks = plan.get('tasks', [])
    ids = [row.get('id') for row in tasks]
    if any(not isinstance(id, str) or not re.fullmatch(r'[A-Z]+-\d\d', id) for id in ids) or len(set(ids)) != len(ids):
        errors.append('Task IDs must be unique stable UPPERCASE-00 values')
    by_id = {row.get('id'): row for row in tasks}
    def reference(ref, context):
        if not isinstance(ref, str):
            errors.append(context + ': reference must be a repository path'); return
        path = (root / ref).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append(context + ': missing/escaped reference ' + ref)
    reference(plan.get('design'), 'design')
    for row in tasks:
        for dep in row.get('depends_on', []):
            if dep not in by_id:
                errors.append(row['id'] + ': unknown dependency ' + str(dep))
        for ref in row.get('source_specs', []):
            reference(ref, row['id'])
        if row.get('evidence'):
            reference(row['evidence'], row['id'])
    visiting, visited = set(), set()
    def visit(id):
        if id in visiting:
            errors.append('Dependency cycle at ' + id); return
        if id in visited:
            return
        visiting.add(id)
        for dep in by_id[id].get('depends_on', []):
            if dep in by_id:
                visit(dep)
        visiting.remove(id); visited.add(id)
    for id in by_id:
        visit(id)
    for key in ['core_tasks', 'follow_up_tasks']:
        for id in plan.get('completion', {}).get(key, []):
            if id not in by_id:
                errors.append('Unknown completion task: ' + id)
    return {'ok': not errors, 'task_count': len(tasks), 'errors': errors,
            'limits': ['Affected future paths may not exist; source/evidence references must.',
                       'Reference validation does not execute planned commands or certify implemented behavior.']}
