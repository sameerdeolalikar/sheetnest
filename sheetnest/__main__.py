import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .core import pack, validate
from .store import Store, Conflict


def main():
    parser = argparse.ArgumentParser(description='Local SheetNest planning workspace')
    parser.add_argument('--data', default='.local-data/sheetnest.sqlite3')
    parser.add_argument('--port', type=int, default=7421)
    args = parser.parse_args()
    path = Path(args.data)
    path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(path)
    web = Path(__file__).resolve().parent.parent/'web'
    host = f'127.0.0.1:{args.port}'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, body, kind='application/json'):
            if kind == 'application/json':
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind+'; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def route(self, write=False):
            try:
                if self.headers.get('Host') != host:
                    return self.send(403, {'error': 'Use the printed loopback URL.'})
                path = urlsplit(self.path).path
                if not write:
                    assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
                    if path in assets:
                        name, kind = assets[path]
                        return self.send(200, (web/name).read_bytes(), kind)
                    if path == '/api/projects':
                        return self.send(200, store.list())
                    if path.startswith('/api/projects/'):
                        return self.send(200, store.get(path.rsplit('/', 1)[1]))
                    return self.send(404, {'error': 'Not found.'})
                if self.headers.get('Origin') != 'http://'+host or self.headers.get('X-Requested-With') != 'SheetNest':
                    return self.send(403, {'error': 'Request must come from the local workspace.'})
                size = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= size <= 256000:
                    return self.send(413, {'error': 'Request limit is 256 KB.'})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('Expected an object.')
                if path == '/api/plan':
                    result = pack(body)
                elif path == '/api/validate':
                    result = validate(body.get('document'), body.get('layout'))
                elif path == '/api/save':
                    result = store.save(body)
                else:
                    return self.send(404, {'error': 'Unknown operation.'})
                self.send(200, result)
            except Conflict as error:
                self.send(409, {'error': str(error)})
            except (ValueError, TypeError, KeyError) as error:
                self.send(400, {'error': str(error)})
            except (sqlite_error, OSError):
                self.send(500, {'error': 'Local storage is unavailable. Check disk access and try again.'})

        def do_GET(self):
            self.route()

        def do_POST(self):
            self.route(True)

    from sqlite3 import Error as sqlite_error
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'SheetNest: http://{host}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
