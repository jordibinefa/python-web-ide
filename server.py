#!/usr/bin/env python3
"""
Servidor HTTP local amb les capçaleres COOP/COEP necessàries per activar
SharedArrayBuffer (i per tant, input() interactiu al worker de Pyodide).

Ús: python3 server.py [port]   (port per defecte: 8080)
"""
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler


class COEPHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        super().end_headers()

    def log_message(self, fmt, *args):
        # Silencia les peticions als fitxers voluminosos de Pyodide
        if args and any(x in str(args[0]) for x in ('.wasm', '.data', 'pyodide-')):
            return
        super().log_message(fmt, *args)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(('', port), COEPHandler)
    print(f'Servidor a http://localhost:{port}/  (Ctrl+C per aturar)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nAturat.')
