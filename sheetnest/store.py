"""SQLite library with optimistic revision checks; no silent stale-tab overwrite."""
import json
import sqlite3
from uuid import uuid4
from .core import document, validate


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, title TEXT, revision INTEGER, data TEXT, updated TEXT)')

    def list(self):
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT id,title,revision,updated FROM projects ORDER BY updated DESC,id')]

    def get(self, key):
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT revision,data FROM projects WHERE id=?', (key,)).fetchone()
        if row is None:
            raise ValueError('Project not found.')
        return {'id': key, 'revision': row[0], **json.loads(row[1])}

    def save(self, raw):
        doc = document(raw.get('document'))
        layout = validate(doc, raw.get('layout'))
        key = raw.get('id')
        revision = raw.get('revision', 0)
        if type(revision) is not int or revision < 0:
            raise ValueError('Invalid revision.')
        data = json.dumps({'document': doc, 'layout': layout})
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            if key:
                count = db.execute("UPDATE projects SET title=?,revision=revision+1,data=?,updated=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND revision=?",
                                   (doc['title'], data, key, revision)).rowcount
                if count != 1:
                    raise Conflict('This project changed in another tab. Reopen it before saving.')
            else:
                if revision != 0:
                    raise ValueError('A new project must have revision zero.')
                if db.execute('SELECT count(*) FROM projects').fetchone()[0] >= 100:
                    raise ValueError('The local library supports 100 projects.')
                key = uuid4().hex
                db.execute("INSERT INTO projects VALUES (?,?,1,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))", (key, doc['title'], data))
        return self.get(key)
