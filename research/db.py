import json
import sqlite3
from contextlib import contextmanager
from research.paths import ROOT, DB, timestamp

@contextmanager
def connect(path=None):
    path = path or DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize(path=None):
    with connect(path) as c:
        c.executescript((ROOT / 'database/schema.sql').read_text(encoding='utf-8'))
        c.execute('INSERT OR IGNORE INTO schema_migrations VALUES(1,?)', (timestamp(),))
        for topic in json.loads((ROOT / 'config/taxonomy.json').read_text(encoding='utf-8')):
            c.execute('INSERT INTO topics(name,parent,keywords) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET parent=excluded.parent,keywords=excluded.keywords', (topic['name'], topic.get('parent'), json.dumps(topic['keywords'], ensure_ascii=False)))
        for s in json.loads((ROOT / 'config/sources.json').read_text(encoding='utf-8')):
            c.execute('INSERT INTO sources(id,name,jurisdiction,tier,homepage,feed_url,enabled) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,jurisdiction=excluded.jurisdiction,tier=excluded.tier,homepage=excluded.homepage', (s['id'],s['name'],s['jurisdiction'],s['tier'],s['homepage'],s.get('feed_url'),int(s.get('enabled',False))))

def query(sql, params=(), path=None):
    with connect(path) as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]
