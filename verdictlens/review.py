"""Persistent blinded assignments and independent, append-only votes."""
import hashlib
import hmac
import json
import secrets
import sqlite3
from .core import LABELS, review_queue, validate_imported_report


class ReviewStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, dataset TEXT NOT NULL, report TEXT NOT NULL); CREATE TABLE IF NOT EXISTS votes (run TEXT, pair TEXT, reviewer TEXT, choice TEXT NOT NULL, PRIMARY KEY(run,pair,reviewer));')
        self.db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('blind_secret', secrets.token_hex(32)))
        self.db.commit()
        self.secret = self.db.execute('SELECT value FROM settings WHERE key=?', ('blind_secret',)).fetchone()[0].encode()

    def save_run(self, data, report):
        self.db.execute('INSERT OR IGNORE INTO runs VALUES (?,?,?)', (report['run_id'], json.dumps(data), json.dumps(report)))
        self.db.commit()

    def import_run(self, data, report):
        validate_imported_report(data, report)
        encoded_data, encoded_report = json.dumps(data), json.dumps(report)
        row = self.db.execute('SELECT dataset,report FROM runs WHERE id=?',
                              (report['run_id'],)).fetchone()
        if row:
            if json.loads(row[0]) == data and json.loads(row[1]) == report:
                return {'run_id': report['run_id'], 'status': 'already_present'}
            raise ValueError('run id already exists; immutable snapshot preserved')
        self.db.execute('INSERT INTO runs VALUES (?,?,?)',
                        (report['run_id'], encoded_data, encoded_report))
        self.db.commit()
        return {'run_id': report['run_id'], 'status': 'imported',
                'queued_pairs': len(review_queue(data, report))}

    def _load(self, run):
        row = self.db.execute('SELECT dataset,report FROM runs WHERE id=?', (run,)).fetchone()
        if row is None:
            raise ValueError('unknown run')
        return json.loads(row[0]), json.loads(row[1])

    def _reviewer(self, reviewer):
        if not isinstance(reviewer, str) or not 3 <= len(reviewer.strip()) <= 80:
            raise ValueError('reviewer pseudonym must be 3–80 characters')
        return hmac.new(self.secret, reviewer.strip().encode(), hashlib.sha256).hexdigest()

    def _token(self, run, pair):
        return hmac.new(self.secret, (run + '\0' + pair).encode(), hashlib.sha256).hexdigest()

    def _swap(self, run, pair, reviewer):
        return int(hmac.new(self.secret, (run + '\0' + pair + '\0' + reviewer).encode(), hashlib.sha256).hexdigest()[:8], 16) % 2 == 1

    def assignment(self, run, reviewer):
        key = self._reviewer(reviewer)
        data, report = self._load(run)
        voted = {x[0] for x in self.db.execute('SELECT pair FROM votes WHERE run=? AND reviewer=?', (run, key))}
        for p in review_queue(data, report):
            if p['id'] in voted:
                continue
            a, b = (p['b'], p['a']) if self._swap(run, p['id'], key) else (p['a'], p['b'])
            return {'token': self._token(run, p['id']), 'prompt': p['prompt'], 'a': a, 'b': b}
        return None

    def vote(self, run, reviewer, token, choice):
        if choice not in LABELS:
            raise ValueError('vote must be a/b/tie')
        key = self._reviewer(reviewer)
        data, report = self._load(run)
        p = next((p for p in review_queue(data, report) if hmac.compare_digest(self._token(run, p['id']), str(token))), None)
        if p is None:
            raise ValueError('unknown or ineligible review token')
        canonical = {'a': 'b', 'b': 'a', 'tie': 'tie'}[choice] if self._swap(run, p['id'], key) else choice
        try:
            self.db.execute('INSERT INTO votes VALUES (?,?,?,?)', (run, p['id'], key, canonical))
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError('reviewer already voted; original vote preserved') from exc

    def export(self, run):
        self._load(run)
        return [{'pair_id': p, 'reviewer_hash': r, 'choice': c} for p, r, c in self.db.execute('SELECT pair,reviewer,choice FROM votes WHERE run=? ORDER BY pair,reviewer', (run,))]

    def close(self):
        self.db.close()

