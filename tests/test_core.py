import copy
from pathlib import Path
import random
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

    def test_deterministic_generated_layouts_validate(self):
        rng = random.Random(42)
        for _ in range(100):
            doc = sample(); doc['parts'] = [{'id': f'p{i}', 'name': f'Part {i}', 'width': rng.randint(5, 120), 'height': rng.randint(5, 90), 'quantity': rng.randint(1, 4), 'rotate': bool(i%2)} for i in range(8)]
            first = pack(doc); self.assertEqual(first, pack(doc)); validate(doc, first['layout'])

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


if __name__ == '__main__':
    unittest.main()
