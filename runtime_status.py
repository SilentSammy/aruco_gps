"""Portable vision metadata and small atomic runtime snapshots for HTTP readers."""
import json
import os
from pathlib import Path
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


STATUS_FILE = 'vision-status.json'


def write_status(directory, status):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / STATUS_FILE
    temporary = directory / f'.vision-status-{os.getpid()}.tmp'
    temporary.write_text(json.dumps(dict(status, updated_at=time.time()), allow_nan=False),
                         encoding='utf-8')
    temporary.replace(target)


def read_status(directory, camera, max_age=3.0):
    try:
        status = json.loads((Path(directory) / STATUS_FILE).read_text(encoding='utf-8'))
        age = max(0., time.time() - status['updated_at'])
        vision = dict(status.get('vision', {}), status_age_s=age)
        vision['healthy'] = bool(vision.get('healthy')) and age < max_age
        if camera.get('session') and vision.get('stream_id') != camera['session']:
            vision.update(healthy=False, error='vision belongs to a different camera session')
        status['vision'] = vision
    except (OSError, ValueError, KeyError, TypeError):
        status = dict(setup=None, vision=dict(healthy=False, error='vision status unavailable'))
    status.update(schema='aruco-gps.status/v1', camera=camera,
                  healthy=bool(camera.get('healthy') and status['vision']['healthy']))
    return status


def send_status_response(handler, directory, camera):
    info = read_status(directory, camera)
    payload = json.dumps(info, allow_nan=False).encode()
    handler.send_response(200 if info['healthy'] else 503)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Content-Length', str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def serve_status(directory, bind='0.0.0.0', port=8080):
    """Expose metadata for direct capture, when there is no camera HTTP worker."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.split('?', 1)[0] != '/api/v1/status':
                self.send_error(404)
                return
            info = read_status(directory, {})
            send_status_response(self, directory,
                                 dict(healthy=info['vision']['healthy'], source=dict(kind='vision')))

    server = ThreadingHTTPServer((bind, port), Handler)
    server.daemon_threads = True
    Thread(target=server.serve_forever, daemon=True).start()
    return server
