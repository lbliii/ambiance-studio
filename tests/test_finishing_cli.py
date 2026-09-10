"""Reusable looks: explicit remapping, atomic changes and typed mask closure."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import studio
from ambiance_studio import finishing, revisions, scene_authoring
from ambiance_studio.cli import init_project, parser, run, main


class FinishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.p = self.root/'film'
        reference = self.root/'reference.png'; Image.new('RGB', (12, 20), '#26425a').save(reference)
        init_project(self.p, reference, 'Independent look fixture', 'blank')
        assets = []
        for id, color in [('paint', '#ab8855'), ('other', '#5577aa'), ('mask', '#ffffff'), ('ported-mask', '#ffffff'), ('wrong-mask', '#777777')]:
            file = self.p/'assets'/f'{id}.png'; Image.new('RGBA', (12, 20), color).save(file)
            assets.append({'id': id, 'kind': 'plate', 'file': 'assets/'+file.name, 'width': 12, 'height': 20, 'sha256': studio.digest(file)})
        self.catalog = {'version': 1, 'assets': assets}; studio.write(self.p/'assets/catalog.json', self.catalog)
        def card(id, **extra):
            return {'id': id, 'name': id, 'asset': 'paint', 'x': .5, 'y': .5, 'width': .5, 'height': .5,
                    'anchor': [.5, .5], 'scale': 1, 'rotation': 0, 'opacity': 1, 'visible': True, 'blend': 'source-over', 'depth': 0, **extra}
        self.scene = studio.read(self.p/'scene/scene.json')
        self.scene['layers'] = [card('floor'), card('actor')]
        self.scene['groups'] = [{'id': 'set', 'x': 0, 'y': 0, 'scale': 1, 'depth': 0, 'pivot': [.5, .5]}]
        self.look = {'kind': finishing.LOOK, 'version': 1, 'finishing': {
            'version': 1, 'working_space': 'linear-srgb', 'output_space': 'srgb',
            'assets': {'paint': {'exposure': -.2}}, 'groups': {'set': {'saturation': .9}},
            'layers': {'actor': {'balance': [1.1, .95, .85]}}, 'grade': {'contrast': .95, 'mask_asset': 'mask'},
            'signals': [{'id': 'pulse', 'layer': 'actor', 'values': [1]}],
            'lights': [{'id': 'light', 'receivers': ['actor'], 'rect': [0, 0, 1, 1], 'anchor_layer': 'floor', 'mask_asset': 'mask', 'color': '#7788ff', 'gain': .3, 'signal': 'pulse'}],
            'shadows': [{'id': 'shadow', 'caster': 'actor', 'receiver': 'floor', 'mask_asset': 'mask', 'elevation': {'layer': 'actor', 'rest_y': .5, 'range': .1}}],
            'reflections': [{'id': 'reflection', 'caster': 'actor', 'receiver': 'floor', 'mask_asset': 'mask'}]
        }}
        studio.write(self.p/'scene/scene.json', self.scene)
        self.look_path = self.p/'look.json'; studio.write(self.look_path, self.look)

    def cli(self, *args): return run(parser().parse_args(['--project', str(self.p), *map(str, args)]))
    def apply(self): return self.cli('look', 'apply', self.look_path)
    def export(self):
        self.apply(); return self.cli('look', 'export', '--out', self.p/'looks/export')
    def bind(self, package, rename=False):
        doc = studio.read(package); binding = {'kind': finishing.BINDINGS, 'version': 1,
            'layers': {name: ('target-'+name if rename else name) for name in doc['requires']['layers']},
            'groups': {name: ('target-'+name if rename else name) for name in doc['requires']['groups']},
            'assets': {row['id']: ({'paint': 'other', 'mask': 'ported-mask'}.get(row['id'], row['id']) if rename else row['id']) for row in doc['requires']['assets']}}
        file = self.p/'bindings.json'; studio.write(file, binding); return file
    def target(self):
        scene = studio.read(self.p/'scene/scene.json'); scene.pop('finishing')
        for layer in scene['layers']: layer['id'] = 'target-'+layer['id']; layer['asset'] = 'other'
        scene['groups'][0]['id'] = 'target-set'; studio.write(self.p/'scene/scene.json', scene)

    def test_apply_dry_run_history_expected_hash_and_remove(self):
        before = (self.p/'scene/scene.json').read_bytes()
        result = self.cli('look', 'apply', self.look_path, '--dry-run')
        self.assertEqual((self.p/'scene/scene.json').read_bytes(), before); self.assertIn('finishing', result['scene'])
        with self.assertRaisesRegex(Exception, 'changed since expected'): self.cli('look', 'apply', self.look_path, '--expect-sha256', '0'*64)
        self.apply(); self.assertTrue(any((self.p/'.ambiance/scene-history').glob('*.json')))
        studio.write(self.look_path, {'kind': finishing.LOOK, 'version': 1, 'finishing': None})
        self.cli('look', 'apply', self.look_path); self.assertNotIn('finishing', studio.read(self.p/'scene/scene.json'))

    def test_check_detects_unpainted_mask_change_and_dependency_roles(self):
        self.apply(); report = self.cli('look', 'check')
        self.assertIn('mask', report['asset_roles']); self.assertIn('finishing-lights-mask', report['asset_roles']['mask'])
        self.assertEqual(finishing.used_asset_ids(studio.read(self.p/'scene/scene.json')), {'paint', 'mask'})
        (self.p/'assets/mask.png').write_bytes(b'changed mask with no layer')
        output = io.StringIO()
        with contextlib.redirect_stdout(output): code = main(['--project', str(self.p), 'look', 'check'])
        self.assertNotEqual(code, 0); self.assertFalse(json.loads(output.getvalue())['ok'])

    def test_export_import_remaps_relationships_and_grade_art_with_exact_mask(self):
        package = self.export()['package']; bindings = self.bind(package, True); self.target()
        before = (self.p/'scene/scene.json').read_bytes()
        draft = self.cli('look', 'import', package, '--bindings', bindings, '--dry-run')
        self.assertEqual((self.p/'scene/scene.json').read_bytes(), before)
        f = draft['scene']['finishing']
        self.assertIn('other', f['assets']); self.assertIn('target-set', f['groups']); self.assertIn('target-actor', f['layers'])
        self.assertEqual(f['signals'][0]['layer'], 'target-actor')
        self.assertEqual(f['lights'][0]['receivers'], ['target-actor']); self.assertEqual(f['lights'][0]['anchor_layer'], 'target-floor')
        self.assertEqual(f['shadows'][0]['elevation']['layer'], 'target-actor'); self.assertEqual(f['reflections'][0]['receiver'], 'target-floor')
        self.assertEqual(f['grade']['mask_asset'], 'ported-mask'); self.assertEqual(len(draft['import']['asset_substitutions']), 1)
        self.cli('look', 'import', package, '--bindings', bindings); self.assertEqual(studio.read(self.p/'scene/scene.json')['finishing'], f)

    def test_missing_colliding_and_wrong_mask_bindings_reject_without_save(self):
        package = self.export()['package']; path = self.bind(package); original = studio.read(path)
        before = (self.p/'scene/scene.json').read_bytes()
        for change in [lambda b: b['layers'].pop('actor'), lambda b: b['layers'].update(actor='floor'), lambda b: b['assets'].update(mask='wrong-mask')]:
            b = copy.deepcopy(original); change(b); studio.write(path, b)
            with self.assertRaises((ValueError, RuntimeError)): self.cli('look', 'import', package, '--bindings', path)
            self.assertEqual((self.p/'scene/scene.json').read_bytes(), before)

    def test_malformed_package_and_changed_input_during_import_fail(self):
        package = Path(self.export()['package']); path = self.bind(package)
        doc = studio.read(package); doc['requires']['layers'] = []; studio.write(package, doc)
        with self.assertRaisesRegex(ValueError, 'integrity changed'): self.cli('look', 'import', package, '--bindings', path)
        studio.write(package, finishing._seal({k: v for k, v in doc.items() if k != 'payload_sha256'}))
        with self.assertRaisesRegex(ValueError, 'requirements differ'): self.cli('look', 'import', package, '--bindings', path)
        doc['requires']['layers'] = ['actor', 'floor']; studio.write(package, finishing._seal({k: v for k, v in doc.items() if k != 'payload_sha256'}))
        from ambiance_studio import cli
        original = cli.scene_bridge
        def changed(*args, **kwargs):
            result = original(*args, **kwargs); path.write_bytes(path.read_bytes()+b' '); return result
        before = (self.p/'scene/scene.json').read_bytes()
        with patch.object(cli, 'scene_bridge', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed before save'):
            self.cli('look', 'import', package, '--bindings', path)
        self.assertEqual((self.p/'scene/scene.json').read_bytes(), before)

    def test_export_collision_and_dependency_change_do_not_promote(self):
        self.apply(); self.cli('look', 'export', '--out', self.p/'looks/export')
        marker = self.p/'looks/export/keep.txt'; marker.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'exists'): self.cli('look', 'export', '--out', marker.parent)
        self.assertEqual(marker.read_text(), 'keep')
        real = scene_authoring.verify_dependencies
        def changed(project, records):
            if any('look-export-scene' in r['roles'] for r in records):
                target = self.p/'assets/mask.png'; target.write_bytes(target.read_bytes()+b' ')
            return real(project, records)
        with patch.object(scene_authoring, 'verify_dependencies', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed before save'):
            self.cli('look', 'export', '--out', self.p/'looks/changed')
        self.assertFalse((self.p/'looks/changed').exists())

    def test_revision_capture_pins_mask_without_scene_layer_and_detects_change(self):
        self.apply(); selection = self.p/'selection.json'
        studio.write(selection, {'format': revisions.SELECTION, 'schema_version': 1, 'scene': 'scene/scene.json', 'catalog': 'assets/catalog.json'})
        revisions.capture(self.p, 'look-v1', selection)
        manifest = revisions.load(self.p, 'look-v1')
        self.assertTrue(any(r['path'] == 'assets/mask.png' and r['role'] == 'finishing-lights-mask' for r in manifest['dependencies']))
        context = revisions.render_context(self.p, 'look-v1')
        self.assertEqual({a['id'] for a in studio.read(context['catalog'])['assets']}, {'paint', 'mask'})
        (self.p/'assets/mask.png').write_bytes(b'changed standalone mask')
        checked = revisions.check(self.p, 'look-v1'); self.assertFalse(checked['ok'])
        self.assertTrue(any(r['path'] == 'assets/mask.png' for r in checked['changed']))

    def repaired_mask(self):
        from PIL import ImageDraw
        from ambiance_studio import edge_quality
        from tools import asset_tool
        source = self.p/'assets/original-mask.png'; image = Image.new('RGBA', (12, 20))
        ImageDraw.Draw(image).ellipse((2, 3, 9, 16), fill='white'); image.save(source)
        recipe = self.p/'assets/edge-recipe.json'
        studio.write(recipe, {'format': 'ambiance-edge-repair', 'version': 1,
            'layout': {'columns': 1, 'rows': 1, 'cell_width': 12, 'cell_height': 20, 'frame_count': 1}, 'alpha': {'feather_px': .5}})
        repaired = self.p/'assets/edge-prep'; edge_quality.edge_repair(source, recipe, repaired)
        compile_recipe = self.p/'assets/compile-edge.json'
        studio.write(compile_recipe, {'version': 1, 'id': 'repaired-mask', 'input': {'sheet': 'edge-prep/atlas.png', 'columns': 1, 'rows': 1, 'frame_count': 1},
            'edge_preparation': {'file': 'edge-prep/report.json', 'sha256': studio.digest(repaired/'report.json')},
            'registration': {'mode': 'fixed', 'point': [6, 10], 'target': [.5, .5]},
            'output': {'cell_size': [16, 24], 'columns': 1, 'padding': 2}})
        pack = self.p/'assets/compiled/repaired-mask'; asset_tool.build(compile_recipe, pack); asset_tool.admit(pack, self.p/'assets/catalog.json')
        self.look['finishing']['grade']['mask_asset'] = 'repaired-mask'; studio.write(self.look_path, self.look)
        return repaired

    def test_edge_preparation_snapshot_is_pinned_and_stales_revision(self):
        repaired = self.repaired_mask(); result = self.apply()
        self.assertTrue(any(r['file'] == 'assets/edge-prep/source-original.bin' for r in result['dependencies']))
        selection = self.p/'selection.json'; studio.write(selection, {'format': revisions.SELECTION, 'schema_version': 1,
            'scene': 'scene/scene.json', 'catalog': 'assets/catalog.json'})
        revisions.capture(self.p, 'edges-v1', selection)
        manifest = revisions.load(self.p, 'edges-v1')
        paths = {r['path'] for r in manifest['dependencies']}
        self.assertTrue({'assets/edge-prep/source-original.bin', 'assets/edge-prep/recipe.json', 'assets/original-mask.png', 'assets/edge-recipe.json'}.issubset(paths))
        snapshot = repaired/'source-original.bin'; snapshot.write_bytes(snapshot.read_bytes()+b' changed')
        self.assertFalse(revisions.check(self.p, 'edges-v1')['ok'])
        with self.assertRaises(ValueError): self.cli('look', 'check')

    def test_edge_preparation_provenance_cannot_be_relabelled_in_catalog(self):
        self.repaired_mask(); catalog = studio.read(self.p/'assets/catalog.json')
        asset = next(a for a in catalog['assets'] if a['id'] == 'repaired-mask')
        asset['provenance']['edge_preparation'] = {'file': 'different/report.json', 'sha256': '0'*64}
        studio.write(self.p/'assets/catalog.json', catalog)
        with self.assertRaisesRegex(ValueError, 'provenance differs'): self.apply()

    def rig_package(self):
        from PIL import ImageDraw
        catalog = studio.read(self.p/'assets/catalog.json')
        sheet = Image.new('RGBA', (48, 20)); draw = ImageDraw.Draw(sheet)
        for i in range(4): draw.ellipse((i*12+2, 2+i, i*12+9, 18), fill=['red', 'gold', 'orange', 'white'][i])
        path = self.p/'assets/gait.png'; sheet.save(path)
        catalog['assets'].append({'id': 'gait', 'kind': 'atlas', 'file': 'assets/gait.png', 'width': 48, 'height': 20,
            'sha256': studio.digest(path), 'atlas': {'columns': 4, 'rows': 1, 'cell_width': 12, 'cell_height': 20, 'frame_count': 4},
            'pivot': [.5, .8], 'sockets': {'ground': {'frames': [[.4, .9], [.45, .9], [.55, .9], [.6, .9]]}}})
        studio.write(self.p/'assets/catalog.json', catalog)
        scene = studio.read(self.p/'scene/scene.json'); floor, actor = scene['layers']
        mount = {**copy.deepcopy(actor), 'id': 'lantern-mount', 'x': .31, 'y': .4, 'width': .1, 'height': .15,
                 'sockets': {'flame': [.5, .1]}, 'opacity': .8, 'group': 'set'}; mount.pop('depth')
        actor.update(asset='gait', x=.005, y=.001, width=.05, height=.05, cycle_seconds=2, phase_frames=2,
            attach={'layer': 'lantern-mount', 'socket': 'flame'},
            motion={'x_amplitude': .002, 'y_amplitude': .001, 'cycles': 2, 'phase': .4, 'rotation_amplitude': .03},
            tracks={'cell': {'interpolation': 'hold', 'keys': [[0, 0], [.5, 2], [1.5, 1], [16, 0]]}}); actor.pop('depth')
        casket = {**copy.deepcopy(floor), 'id': 'casket', 'x': .55, 'y': .65, 'width': .25, 'height': .2,
            'sockets': {'rim': [.5, .5], 'ground': [.5, 1]},
            'tracks': {'y': {'interpolation': 'smoothstep', 'keys': [[0, .65], [8, .59], [16, .65]]}}}
        rim = {**copy.deepcopy(floor), 'id': 'rim', 'x': 0, 'y': 0, 'width': .25, 'height': .2, 'attach': {'layer': 'casket', 'socket': 'rim'}}; rim.pop('depth')
        scene['layers'] = [floor, mount, casket, actor, rim]
        scene['groups'][0].update(x=.02, scale=1.1)
        studio.write(self.p/'scene/scene.json', scene)
        self.look['finishing']['signals'][0]['values'] = [1, .8, .5, 1.2]
        self.look['finishing']['layers']['rim'] = {'contrast': 1.1}
        self.look['finishing']['shadows'].append({'id': 'casket-contact', 'caster': 'casket', 'receiver': 'floor',
            'elevation': {'layer': 'casket', 'rest_y': .65, 'range': .06}})
        studio.write(self.look_path, self.look); self.apply()
        result = self.cli('look', 'export', '--include-rig', '--out', self.p/'looks/rig')
        return Path(result['package']), studio.read(self.p/'scene/scene.json'), catalog

    def rig_target(self, package, source, catalog):
        doc = studio.read(package)
        for row in list(catalog['assets']):
            if row['id'] in ['paint', 'gait']: catalog['assets'].append({**copy.deepcopy(row), 'id': row['id']+'-copy'})
        studio.write(self.p/'assets/catalog.json', catalog)
        bindings = {'kind': finishing.BINDINGS, 'version': 1,
            'layers': {lid: 'target-'+lid for lid in doc['requires']['layers']},
            'groups': {gid: 'target-'+gid for gid in doc['requires']['groups']},
            'assets': {a['id']: ('ported-mask' if a['id'] == 'mask' else a['id']+'-copy') for a in doc['requires']['assets']}}
        path = self.p/'rig-bindings.json'; studio.write(path, bindings)
        target = copy.deepcopy(source); target.pop('finishing')
        for layer in target['layers']:
            layer['id'] = bindings['layers'][layer['id']]; layer.update(asset='other', x=.1, y=.2, depth=0)
            for key in ['attach', 'group', 'sockets', 'motion', 'tracks', 'cycle_seconds', 'phase_frames']: layer.pop(key, None)
        target['layers'].reverse()
        untouched = copy.deepcopy(target['layers'][0]); untouched['id'] = 'unbound-marker'; target['layers'].insert(1, untouched)
        target['groups'] = [{**source['groups'][0], 'id': 'target-set', 'x': -.1, 'scale': .8}]
        studio.write(self.p/'scene/scene.json', target)
        return path, bindings, target

    def test_rig_import_restores_lantern_cadence_casket_overlap_and_ancestor_geometry(self):
        from ambiance_studio.cli import scene_bridge
        package, source, catalog = self.rig_package(); path, bindings, before = self.rig_target(package, source, catalog)
        doc = studio.read(package)
        self.assertIn('lantern-mount', doc['requires']['layers'])  # Ancestor, not a direct finishing root.
        expected_sockets = next(a for a in catalog['assets'] if a['id'] == 'gait')['sockets']
        self.assertEqual(next(a for a in doc['requires']['assets'] if a['id'] == 'gait')['rig_metadata']['sockets'], expected_sockets)
        result = self.cli('look', 'import', package, '--bindings', path, '--include-rig', '--dry-run')
        candidate = result['scene']; self.assertEqual(studio.read(self.p/'scene/scene.json'), before)
        self.assertEqual(candidate['layers'][1]['id'], 'unbound-marker'); self.assertEqual(candidate['layers'][1], before['layers'][1])
        self.assertEqual([l['id'] for l in candidate['layers'] if l['id'] != 'unbound-marker'], [bindings['layers'][l['id']] for l in source['layers']])
        self.assertTrue(result['import']['rig']['restores_source_normalized_placement']); self.assertEqual(candidate['camera'], before['camera'])
        for time in [0, .5, 1.37, 8, 15.9]:
            old = {s['id']: s for s in scene_bridge('sample', source, catalog, {'time': time})}
            new = {s['id']: s for s in scene_bridge('sample', candidate, catalog, {'time': time})}
            for lid, target in bindings['layers'].items():
                for key in ['matrix', 'rect', 'cell', 'sockets', 'visible', 'opacity']: self.assertEqual(old[lid][key], new[target][key], (time, lid, key))
        self.cli('look', 'import', package, '--bindings', path, '--include-rig')
        self.assertEqual(studio.read(self.p/'scene/scene.json'), candidate)

    def test_rig_import_requires_flag_matching_clock_and_exact_image_socket_version(self):
        package, source, catalog = self.rig_package(); path, bindings, target = self.rig_target(package, source, catalog)
        before = (self.p/'scene/scene.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'requires explicit --include-rig'): self.cli('look', 'import', package, '--bindings', path)
        for field, value in [('width', 720), ('fps', 24), ('loop_seconds', 8)]:
            changed = copy.deepcopy(target); changed['canvas'][field] = value; studio.write(self.p/'scene/scene.json', changed)
            with self.assertRaisesRegex(ValueError, 'identical canvas'): self.cli('look', 'import', package, '--bindings', path, '--include-rig')
        (self.p/'scene/scene.json').write_bytes(before)
        for edit in [lambda a: a.update(sha256='0'*64), lambda a: a['sockets']['ground']['frames'][0].__setitem__(0, .2)]:
            changed = copy.deepcopy(catalog); edit(next(a for a in changed['assets'] if a['id'] == 'gait-copy')); studio.write(self.p/'assets/catalog.json', changed)
            with self.assertRaisesRegex(ValueError, 'Rig image version'): self.cli('look', 'import', package, '--bindings', path, '--include-rig')
            self.assertEqual((self.p/'scene/scene.json').read_bytes(), before)

    def test_rig_package_scope_rejects_unknown_fields_and_missing_ancestor(self):
        package, source, catalog = self.rig_package(); path, bindings, target = self.rig_target(package, source, catalog)
        original = studio.read(package)
        for edit in [lambda d: d['rig'].update(camera={}), lambda d: d['rig'].__setitem__('layers', [l for l in d['rig']['layers'] if l['id'] != 'lantern-mount'])]:
            changed = copy.deepcopy(original); edit(changed); studio.write(package, finishing._seal({k: v for k, v in changed.items() if k != 'payload_sha256'}))
            with self.assertRaises(ValueError): self.cli('look', 'import', package, '--bindings', path, '--include-rig')
            self.assertEqual(studio.read(self.p/'scene/scene.json'), target)


if __name__ == '__main__': unittest.main(verbosity=2)
