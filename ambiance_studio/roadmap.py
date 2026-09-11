"""Validate roadmap references without treating planned capabilities as executable commands."""
import re
from pathlib import Path


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
