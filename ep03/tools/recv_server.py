"""Tiny local receiver: the ElevenLabs page POSTs library sound blobs here; saved to sfx_lib/<name>."""
import http.server, pathlib, urllib.parse
OUT = pathlib.Path(__file__).resolve().parent / 'sfx_lib'; OUT.mkdir(exist_ok=True)


class H(http.server.BaseHTTPRequestHandler):
    def cors(self):
        self.send_header('Access-Control-Allow-Origin', 'https://elevenlabs.io')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')

    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()

    def do_POST(self):
        name = urllib.parse.unquote(self.path.strip('/')).replace('/', '_').replace('\\', '_')[:120] or 'unnamed'
        data = self.rfile.read(int(self.headers['Content-Length']))
        (OUT / name).write_bytes(data)
        print('saved', name, len(data), flush=True)
        self.send_response(200); self.cors(); self.end_headers(); self.wfile.write(b'ok')


http.server.HTTPServer(('127.0.0.1', 8765), H).serve_forever()
