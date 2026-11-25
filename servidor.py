import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import config

PUERTO = 8050


class Sitio(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/mapa.html"
        super().do_GET()

    def log_message(self, *args):
        pass


def servir():
    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), functools.partial(Sitio, directory=config.DIR_SALIDA))
    except OSError:
        raise SystemExit(f"El puerto {PUERTO} está ocupado: cierra el otro servidor y vuelve a correr python main.py")
    print(f"Mapa Leaflet disponible en: http://localhost:{PUERTO}/")
    print("Ctrl+C para detener el servidor")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
    finally:
        servidor.server_close()
