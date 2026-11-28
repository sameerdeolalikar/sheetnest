import copy
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from sheetnest.core import pack, validate, document
from sheetnest.store import Store, Conflict


def sample():
    return {'version': 1, 'title': 'Synthetic panels', 'stock': {'width': 100, 'height': 80, 'count': 2}, 'kerf': 2,
            'parts': [{'id': 'panel', 'name': 'Panel', 'width': 40, 'height': 30, 'quantity': 4, 'rotate': True}]}


class CoreTests(unittest.TestCase):
    def test_packing_accounts_for_every_piece(self):
        result = pack(sample())
        self.assertEqual(len(result['layout']['placements']), 4)
        self.assertEqual(result['layout']['unplaced'], [])
        self.assertEqual(result['layout']['utilization'], 60)

    def test_oversized_parts_are_explicitly_unplaced(self):
        doc = sample(); doc['parts'][0]['width'] = 200
        self.assertEqual(len(pack(doc)['layout']['unplaced']), 4)

    def test_rotation_enables_fit(self):
        doc = sample(); doc['parts'][0].update(width=70, height=90, quantity=1)
        self.assertTrue(pack(doc)['layout']['placements'][0]['rotated'])
        doc['parts'][0]['rotate'] = False
        self.assertEqual(len(pack(doc)['layout']['unplaced']), 1)

    def test_collision_and_spacing_rejected(self):
        doc = sample(); layout = pack(doc)['layout']
        layout['placements'][1].update(x=40, y=0)
        with self.assertRaisesRegex(ValueError, 'spacing'):
            validate(doc, layout)

    def test_boundary_rejected(self):
        doc = sample(); layout = pack(doc)['layout']; layout['placements'][0]['x'] = 99
        with self.assertRaisesRegex(ValueError, 'beyond'):
            validate(doc, layout)

    def test_duplicate_and_missing_pieces_rejected(self):
        doc = sample(); layout = pack(doc)['layout']
        bad = copy.deepcopy(layout); bad['placements'].append(bad['placements'][0])
        with self.assertRaises(ValueError): validate(doc, bad)
        bad = copy.deepcopy(layout); bad['placements'].pop()
        with self.assertRaises(ValueError): validate(doc, bad)

    def test_untrusted_dimensions_are_recomputed(self):
        doc = sample(); layout = pack(doc)['layout']; layout['placements'][0]['width'] = 1
        self.assertEqual(validate(doc, layout)['placements'][0]['width'], 40)

    def test_bounds_and_integer_limits(self):
        for value in [-1, 0, 10001, 1.5, True, '20']:
            doc = sample(); doc['stock']['width'] = value
            with self.assertRaises(ValueError): document(doc)

    def test_project_version_requires_integer_one(self):
        self.assertEqual(document(sample())['version'], 1)
        for value in [True, False, 1.0, '1', None, 0, 2, [], {}]:
            with self.subTest(version=value):
                doc = sample(); doc['version'] = value
                with self.assertRaisesRegex(ValueError, 'version 1'):
                    pack(doc)
        doc = sample(); del doc['version']
        with self.assertRaisesRegex(ValueError, 'version 1'):
            document(doc)

    def test_invalid_version_save_preserves_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'data.sqlite3')
            saved = store.save(pack(sample()))
            before = store.list()
            for version in [True, 1.0]:
                with self.subTest(version=version):
                    bad = copy.deepcopy(saved)
                    bad['document']['version'] = version
                    with self.assertRaisesRegex(ValueError, 'version 1'):
                        store.save(bad)
                    self.assertEqual(store.get(saved['id']), saved)
                    self.assertEqual(store.list(), before)

    def test_deterministic_generated_layouts_validate(self):
        rng = random.Random(42)
        for _ in range(100):
            doc = sample(); doc['parts'] = [{'id': f'p{i}', 'name': f'Part {i}', 'width': rng.randint(5, 120), 'height': rng.randint(5, 90), 'quantity': rng.randint(1, 4), 'rotate': bool(i%2)} for i in range(8)]
            first = pack(doc); self.assertEqual(first, pack(doc)); validate(doc, first['layout'])

    def test_unpaired_surrogates_rejected_in_labels(self):
        for field in ['title', 'name', 'id']:
            for value in ['\ud800', 'Panel\udfff']:
                with self.subTest(field=field, value=repr(value)):
                    doc = sample()
                    target = doc if field == 'title' else doc['parts'][0]
                    target[field] = value
                    with self.assertRaisesRegex(ValueError, 'valid Unicode'):
                        pack(doc)

    def test_unicode_labels_roundtrip_and_failed_save_preserves_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'data.sqlite3')
            doc = sample()
            doc['title'] = 'Mått — 棚 🪵'
            doc['parts'][0]['name'] = 'Hylla — 板 🪵'
            saved = store.save(pack(doc))
            self.assertEqual(Store(store.path).get(saved['id']), saved)
            self.assertEqual(saved['document'], doc)
            before = store.list()
            for field in ['title', 'name']:
                with self.subTest(field=field):
                    bad = copy.deepcopy(saved)
                    target = bad['document'] if field == 'title' else bad['document']['parts'][0]
                    target[field] = '\ud800'
                    with self.assertRaisesRegex(ValueError, 'valid Unicode'):
                        store.save(bad)
                    self.assertEqual(store.get(saved['id']), saved)
                    self.assertEqual(store.list(), before)

    def test_storage_roundtrip_and_stale_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'data.sqlite3'); value = pack(sample())
            saved = store.save({'revision': 0, **value})
            self.assertEqual(Store(store.path).get(saved['id']), saved)
            updated = store.save(saved); self.assertEqual(updated['revision'], 2)
            with self.assertRaises(Conflict): store.save(saved)
            self.assertEqual(store.get(saved['id'])['revision'], 2)

    def test_failed_save_preserves_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'data.sqlite3'); saved = store.save({'revision': 0, **pack(sample())})
            bad = copy.deepcopy(saved); bad['layout']['placements'][0]['x'] = 999
            with self.assertRaises(ValueError): store.save(bad)
            self.assertEqual(store.get(saved['id']), saved)

    def test_out_of_range_revisions_leave_library_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'data.sqlite3')
            saved = store.save(pack(sample()))
            before = store.list()
            for revision in [-1, 2**63, 10**100]:
                with self.subTest(revision=revision):
                    with self.assertRaisesRegex(ValueError, 'Invalid revision'):
                        store.save({**saved, 'revision': revision})
                    self.assertEqual(store.get(saved['id']), saved)
                    self.assertEqual(store.list(), before)
            with self.assertRaises(Conflict):
                store.save({**saved, 'revision': 2**63 - 1})
            updated = store.save(saved)
            self.assertEqual(updated['revision'], 2)

    def test_revision_limit_save_preserves_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'data.sqlite3')
            saved = store.save(pack(sample()))
            with sqlite3.connect(store.path) as db:
                db.execute('UPDATE projects SET revision=? WHERE id=?', (2**63 - 2, saved['id']))
            previous = store.get(saved['id'])
            saved = store.save(previous)
            self.assertEqual(saved['revision'], 2**63 - 1)
            self.assertIs(type(saved['revision']), int)
            before = store.list()
            changed = copy.deepcopy(saved)
            changed['document']['title'] = 'Changed panels'
            with self.assertRaisesRegex(ValueError, 'revision limit'):
                store.save(changed)
            with self.assertRaises(Conflict):
                store.save(previous)
            self.assertEqual(Store(store.path).get(saved['id']), saved)
            self.assertEqual(store.list(), before)

    def test_malformed_project_ids_leave_library_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'data.sqlite3')
            value = pack(sample())
            saved = store.save(value)
            before = store.list()
            for key in [False, True, 0, 1, 1.5, '', '   ', [], ['project'], {}, {'id': saved['id']}]:
                with self.subTest(key=key):
                    with self.assertRaisesRegex(ValueError, 'Project ID'):
                        store.save({'id': key, 'revision': 0, **value})
                    self.assertEqual(store.list(), before)
                    self.assertEqual(store.get(saved['id']), saved)

    def test_null_project_id_creates_new_project(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'data.sqlite3')
            value = pack(sample())
            saved = store.save({'id': None, 'revision': 0, **value})
            self.assertEqual(saved['revision'], 1)
            self.assertEqual(store.get(saved['id']), {'id': saved['id'], 'revision': 1, **value})


if __name__ == '__main__':
    unittest.main()
