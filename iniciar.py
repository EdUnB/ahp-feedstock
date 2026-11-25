"""Start a separate local instance and open only its verified health endpoint."""
import json
import os
from pathlib import Path
import socket
import threading
import time
import urllib.request
from uuid import uuid4
import webbrowser


def main():
    import uvicorn
    os.chdir(Path(__file__).resolve().parent)
    os.environ['AHP_ENABLE_DRAFT'] = '1'
    instance_id = str(uuid4())
    os.environ['AHP_INSTANCE_ID'] = instance_id
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    print(f'\nAHP Feedstock v2.0 — abra {url}\nMantenha esta janela aberta. Ctrl+C encerra esta instancia.\n',flush=True)

    def open_when_ready():
        for _ in range(100):
            try:
                with urllib.request.urlopen(url+'/api/health', timeout=1) as response:
                    data = json.load(response)
                if data.get('instance_id') == instance_id:
                    webbrowser.open(url)
                    return
            except (OSError,ValueError):
                pass
            time.sleep(.2)
        print('Nao foi possivel abrir automaticamente. Confira as mensagens do servidor.',flush=True)

    threading.Thread(target=open_when_ready,daemon=True).start()
    uvicorn.run('app.server:app', host='127.0.0.1', port=port)


if __name__ == '__main__':
    main()
