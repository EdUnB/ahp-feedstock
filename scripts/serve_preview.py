from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path
class Handler(SimpleHTTPRequestHandler):
 def translate_path(self,path):
  if path.startswith('/ahp-feedstock/'):
   path=path[len('/ahp-feedstock'):]
  return super().translate_path(path)
root=Path(__file__).resolve().parents[1]/'dist'
ThreadingHTTPServer(('127.0.0.1',8012),partial(Handler,directory=str(root))).serve_forever()
