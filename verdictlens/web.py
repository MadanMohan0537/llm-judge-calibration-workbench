from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from .core import DEFAULT_RUBRIC, evaluate, validate_dataset
from .review import ReviewStore


def make_server(data, database, port=8788):
    validate_dataset(data)
    store = ReviewStore(database)
    class Handler(BaseHTTPRequestHandler):
        def send(self, value, status=200, content_type='application/json'):
            raw = value.encode() if isinstance(value, str) else json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            for key, val in [('Content-Type', content_type+'; charset=utf-8'), ('Content-Length', str(len(raw))), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')]:
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(raw)

        def allowed(self):
            host = f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host') == host and self.headers.get('Origin') in (None, 'http://'+host)

        def do_GET(self):
            if not self.allowed():
                return self.send({'error': 'loopback host/origin required'}, 403)
            parsed = urlparse(self.path)
            q = parse_qs(parsed.query)
            try:
                if parsed.path == '/':
                    self.send(Path(__file__).with_name('workbench.html').read_text(), content_type='text/html')
                elif parsed.path == '/api/config':
                    self.send({'rubric': DEFAULT_RUBRIC, 'pairs': len(data['pairs']), 'provenance': data.get('provenance', 'not supplied')})
                elif parsed.path == '/api/assignment':
                    self.send(store.assignment(q['run'][0], q['reviewer'][0]))
                elif parsed.path == '/api/votes':
                    self.send(store.export(q['run'][0]))
                else:
                    self.send({'error': 'not found'}, 404)
            except (ValueError, KeyError) as exc:
                self.send({'error': str(exc)}, 400)

        def do_POST(self):
            if not self.allowed():
                return self.send({'error': 'loopback host/origin required'}, 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 65536:
                    return self.send({'error': 'request must be 1–65536 bytes'}, 413)
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    return self.send({'error': 'JSON content type required'}, 415)
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('JSON object required')
                if self.path == '/api/evaluate':
                    reports = []
                    for kind in ('mock-evidence', 'mock-length'):
                        report = evaluate(data, body.get('rubric', DEFAULT_RUBRIC), kind)
                        store.save_run(data, report)
                        reports.append(report)
                    self.send(reports)
                elif self.path == '/api/vote':
                    store.vote(body['run'], body['reviewer'], body['token'], body['choice'])
                    self.send({'saved': True})
                else:
                    self.send({'error': 'not found'}, 404)
            except (ValueError, KeyError, TypeError) as exc:
                self.send({'error': str(exc)}, 400)

        def log_message(self, *_):
            pass
    server = HTTPServer(('127.0.0.1', port), Handler)
    server.store = store
    return server
