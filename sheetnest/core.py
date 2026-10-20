"""Deterministic shelf packing and independently validated editable layouts.

Coordinates and dimensions are integer millimetres. This is a planning heuristic,
not an optimal nesting solver or a machine toolpath generator.
"""
from itertools import combinations
import re


def integer(value, name, low=1, high=10000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}.")
    return value


def text(value, name):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 100:
        raise ValueError(f"{name} must contain 1–100 characters.")
    return value.strip()


def document(raw):
    if not isinstance(raw, dict) or raw.get('version') != 1:
        raise ValueError('Expected a version 1 project.')
    stock = raw.get('stock')
    if not isinstance(stock, dict):
        raise ValueError('Stock dimensions are required.')
    result = {'version': 1, 'title': text(raw.get('title'), 'Project name'),
              'stock': {'width': integer(stock.get('width'), 'Sheet width'),
                        'height': integer(stock.get('height'), 'Sheet height'),
                        'count': integer(stock.get('count'), 'Sheet count', 1, 20)},
              'kerf': integer(raw.get('kerf'), 'Cut spacing', 0, 20), 'parts': []}
    if not isinstance(raw.get('parts'), list) or not 1 <= len(raw['parts']) <= 100:
        raise ValueError('Use 1–100 part definitions.')
    ids = set()
    for part in raw['parts']:
        if not isinstance(part, dict):
            raise ValueError('Each part must be an object.')
        key = text(part.get('id'), 'Part ID')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', key) or key in ids:
            raise ValueError('Part IDs must be unique letters, numbers, hyphens or underscores.')
        ids.add(key)
        if type(part.get('rotate')) is not bool:
            raise ValueError('Rotation must be true or false.')
        result['parts'].append({'id': key, 'name': text(part.get('name'), 'Part name'),
            'width': integer(part.get('width'), 'Part width'),
            'height': integer(part.get('height'), 'Part height'),
            'quantity': integer(part.get('quantity'), 'Quantity', 1, 200), 'rotate': part['rotate']})
    if sum(p['quantity'] for p in result['parts']) > 200:
        raise ValueError('At most 200 individual pieces are supported.')
    return result


def instances(doc):
    return {f"{p['id']}:{n+1}": p for p in doc['parts'] for n in range(p['quantity'])}


def validate(doc, layout):
    doc = document(doc)
    if not isinstance(layout, dict) or not isinstance(layout.get('placements'), list) or not isinstance(layout.get('unplaced'), list):
        raise ValueError('A layout needs placements and unplaced IDs.')
    expected, seen, placed = instances(doc), set(), []
    stock, gap = doc['stock'], doc['kerf']
    for item in layout['placements']:
        if not isinstance(item, dict):
            raise ValueError('Each placement must be an object.')
        key = item.get('id')
        if not isinstance(key, str) or key not in expected or key in seen:
            raise ValueError('Unknown or duplicate piece in layout.')
        seen.add(key)
        part = expected[key]
        rotated = item.get('rotated')
        if type(rotated) is not bool or (rotated and not part['rotate']):
            raise ValueError(f"Rotation is not allowed for {part['name']}.")
        w, h = (part['height'], part['width']) if rotated else (part['width'], part['height'])
        x, y = integer(item.get('x'), 'X position', 0), integer(item.get('y'), 'Y position', 0)
        sheet = integer(item.get('sheet'), 'Sheet index', 0, stock['count']-1)
        if x+w > stock['width'] or y+h > stock['height']:
            raise ValueError(f"{key} extends beyond sheet {sheet+1}.")
        placed.append({'id': key, 'name': part['name'], 'sheet': sheet, 'x': x, 'y': y,
                       'width': w, 'height': h, 'rotated': rotated})
    for a, b in combinations(placed, 2):
        if a['sheet'] == b['sheet'] and not (a['x']+a['width']+gap <= b['x'] or b['x']+b['width']+gap <= a['x']
                or a['y']+a['height']+gap <= b['y'] or b['y']+b['height']+gap <= a['y']):
            raise ValueError(f"{a['id']} and {b['id']} overlap or violate the {gap} mm spacing.")
    for key in layout['unplaced']:
        if not isinstance(key, str) or key not in expected or key in seen:
            raise ValueError('Unknown or duplicate unplaced piece.')
        seen.add(key)
    if seen != set(expected):
        raise ValueError('Every requested piece must be placed or reported as unplaced.')
    used = len({p['sheet'] for p in placed})
    area = sum(p['width']*p['height'] for p in placed)
    stock_area = used*stock['width']*stock['height']
    return {'placements': placed, 'unplaced': layout['unplaced'], 'sheets_used': used,
            'utilization': round(100*area/stock_area, 2) if stock_area else 0,
            'unused_area': stock_area-area}


def pack(raw):
    doc = document(raw)
    stock, gap = doc['stock'], doc['kerf']
    shelves = [[] for _ in range(stock['count'])]
    placements, unplaced = [], []
    pieces = sorted(instances(doc).items(), key=lambda pair: (-(pair[1]['width']*pair[1]['height']), pair[0]))
    for key, part in pieces:
        options = [(part['width'], part['height'], False)]
        if part['rotate'] and part['width'] != part['height']:
            options.append((part['height'], part['width'], True))
        options.sort(key=lambda o: (o[1], o[0]))
        found = None
        for index, rows in enumerate(shelves):
            for row in rows:
                for w, h, rotated in options:
                    if h <= row['height'] and row['next']+w <= stock['width']:
                        found = {'id': key, 'sheet': index, 'x': row['next'], 'y': row['y'], 'rotated': rotated}
                        row['next'] += w+gap
                        break
                if found:
                    break
            if not found:
                y = rows[-1]['y']+rows[-1]['height']+gap if rows else 0
                for w, h, rotated in options:
                    if w <= stock['width'] and y+h <= stock['height']:
                        rows.append({'y': y, 'height': h, 'next': w+gap})
                        found = {'id': key, 'sheet': index, 'x': 0, 'y': y, 'rotated': rotated}
                        break
            if found:
                break
        if found:
            placements.append(found)
        else:
            unplaced.append(key)
    return {'document': doc, 'layout': validate(doc, {'placements': placements, 'unplaced': unplaced})}
