"""Narrow fulfillment edits; authored scope and artistic review are separate."""
import copy
import hashlib
import json
from . import planning, revisions
from .project import project_lock, locations
from .errors import CommandError
import studio


def fulfill(project, patch, expected, dry_run=False):
    project = project.resolve()
    revisions.fields(patch, {'format', 'schema_version', 'parts'}, 'fulfillment patch')
    if patch.get('format') != 'ambiance-fulfillment' or patch.get('schema_version') != 1 or not isinstance(patch.get('parts'), list) or not patch['parts']:
        raise ValueError('Expected ambiance-fulfillment schema_version 1 with parts')
    with project_lock(project):
        path = project/'plans/asset-inventory.json'; before = path.read_bytes(); previous = hashlib.sha256(before).hexdigest()
        if previous != expected: raise CommandError('Inventory changed; inspect and rebase the patch.', 'stale_input', 2)
        candidate = json.loads(before); scene_path, catalog_path = locations(project)
        inputs = {p: studio.digest(p) for p in [path, scene_path, catalog_path, project/'ambiance-project.json']}
        seen = set(); changes = []
        for update in patch['parts']:
            revisions.fields(update, {'item', 'part', 'values'}, 'fulfillment update')
            key = (update.get('item'), update.get('part'))
            if not all(isinstance(k, str) for k in key) or key in seen: raise ValueError('Unique stable item/part IDs required')
            seen.add(key)
            items = [i for i in candidate['items'] if i['id'] == key[0]]
            parts = [p for p in items[0].get('required_parts', []) if isinstance(p, dict) and p.get('id') == key[1]] if len(items) == 1 else []
            if len(parts) != 1: raise ValueError('Unknown or legacy fulfillment part: '+str(key))
            values = update.get('values'); revisions.fields(values, {'stage', 'files', 'asset_id', 'layer_ids'}, 'fulfillment values')
            if not values: raise ValueError('Fulfillment values cannot be empty')
            old = copy.deepcopy(parts[0]); parts[0].update(values)
            changes.append({'item': key[0], 'part': key[1], 'before': old, 'after': copy.deepcopy(parts[0])})
        checked = planning.evaluate(project, candidate, studio.read(catalog_path), studio.read(scene_path), path,
                                   {str(p.relative_to(project)): h for p, h in inputs.items()})
        if not checked['ok']: raise ValueError('Invalid fulfillment: '+'; '.join(checked['errors']))
        for name, digest in checked['evidence_bindings'].items(): inputs[studio.inside(project, name)] = digest
        if any(studio.digest(p) != h for p, h in inputs.items()): raise CommandError('Fulfillment inputs changed.', 'stale_input', 2)
        result = dict(ok=True, dry_run=dry_run, previous_sha256=previous, changes=changes, summary=checked['summary'])
        if dry_run: return result
        backup = project/'.ambiance/inventory-history'/f'{previous}.json'
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists() and backup.read_bytes() != before: raise ValueError('Inventory history changed')
        if not backup.exists():
            with backup.open('xb') as file: file.write(before)
        studio.write(path, candidate)
        result.update(path=str(path), sha256=studio.digest(path), snapshot=str(backup))
        return result
