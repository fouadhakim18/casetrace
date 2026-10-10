import json
import sqlite3
import uuid
from datetime import datetime, timezone
from .config import data_dir

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex

def connect():
    db = sqlite3.connect(data_dir() / 'casetrace.sqlite3', timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, payload TEXT NOT NULL)')
    return db

def save_case(case):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO cases VALUES (?,?)', (case['id'], json.dumps(case)))
    return case

def get_case(case_id):
    with connect() as db: row = db.execute('SELECT payload FROM cases WHERE id=?', (case_id,)).fetchone()
    if not row: raise KeyError('Case not found')
    return json.loads(row[0])

def list_cases():
    with connect() as db: rows = db.execute('SELECT payload FROM cases').fetchall()
    return sorted([json.loads(r[0]) for r in rows], key=lambda c: c['created_at'], reverse=True)

def save_run(run):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO runs VALUES (?,?,?)', (run['id'], run['case_id'], json.dumps(run)))

def get_run(run_id):
    with connect() as db: row = db.execute('SELECT payload FROM runs WHERE id=?', (run_id,)).fetchone()
    if not row: raise KeyError('Investigation not found')
    return json.loads(row[0])

def list_runs(case_id):
    with connect() as db: rows = db.execute('SELECT payload FROM runs WHERE case_id=? ORDER BY rowid DESC', (case_id,)).fetchall()
    return [json.loads(r[0]) for r in rows]

def mark_interrupted():
    with connect() as db:
        rows = db.execute('SELECT payload FROM runs').fetchall()
    for row in rows:
        run = json.loads(row[0])
        if run['status'] in ('running', 'queued'):
            run.update(status='interrupted', error='Server restarted. Start a new investigation; this trace is preserved.')
            save_run(run)
