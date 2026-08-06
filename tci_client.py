"""
tci_client.py — Client TCI (protocole Expert Electronics / AetherSDR) pour Station Master.

Étape 0 du plan SSTV (voir docs/plans/2026-08-06-sstv-tab-design.md) : connexion et
réception brute (texte/binaire), sans hypothèse ferme sur le format exact des trames
audio binaires — le format n'a pas été vérifié sur ce déploiement AetherSDR précis
(port par défaut supposé 5001, à confirmer via config.ini [TCI]). Le parsing du
format audio interviendra à l'Étape 1, une fois de vraies trames capturées via le
mode `--dump` ci-dessous.

Exécuté seul (`python3 tci_client.py`), ce module se connecte, logue chaque message
reçu et sauvegarde les trames binaires brutes dans un dossier pour inspection
manuelle (hexdump) — objectif : valider la connectivité et découvrir le format réel
avant d'écrire un parseur.
"""

import asyncio
import queue
import threading

try:
    import websockets

    _WEBSOCKETS_OK = True
except ImportError:
    _WEBSOCKETS_OK = False


class TCIClient:
    """Connexion TCI en arrière-plan (thread dédié + boucle asyncio privée).

    Communique avec le reste de l'appli (thread Tkinter) via des files
    thread-safe, comme les autres threads réseau de Station Master (CAT,
    cluster, solar) — voir CLAUDE.md section Threads/réseau. La boucle
    asyncio de `websockets` tourne entièrement dans ce thread ; aucun autre
    module de l'appli n'a besoin d'être asyncio.
    """

    def __init__(self, host, port):
        self.host = host
        self.port = int(port)

        self.text_queue = queue.Queue()
        self.binary_queue = queue.Queue()
        self.status_queue = (
            queue.Queue()
        )  # ("connected"|"disconnected"|"error", détail)

        self._thread = None
        self._loop = None
        self._ws = None
        self._running = False
        self._send_queue = None  # asyncio.Queue, créée dans la boucle du thread

    @property
    def connected(self):
        return self._ws is not None and self._running

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if not _WEBSOCKETS_OK:
            self.status_queue.put(
                (
                    "error",
                    "Le module 'websockets' n'est pas installé (voir requirements.txt).",
                )
            )
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._loop and self._ws is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            except Exception:
                pass

    def send_text(self, line: str):
        """Envoie une commande texte au serveur TCI (ex: 'vfo:0,0,14074000;')."""
        self._enqueue_send(line)

    def send_audio(self, payload: bytes):
        """Envoie une trame audio binaire brute au serveur TCI (TX)."""
        self._enqueue_send(payload)

    def _enqueue_send(self, item):
        if self._loop is None or self._send_queue is None:
            return
        self._loop.call_soon_threadsafe(self._send_queue.put_nowait, item)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except Exception as e:
            self.status_queue.put(("error", str(e)))
        finally:
            self._running = False
            self._loop.close()

    async def _main(self):
        uri = f"ws://{self.host}:{self.port}"
        self._send_queue = asyncio.Queue()
        try:
            async with websockets.connect(uri, max_size=None) as ws:
                self._ws = ws
                self.status_queue.put(("connected", uri))
                sender = asyncio.create_task(self._sender_loop(ws))
                receiver = asyncio.create_task(self._receiver_loop(ws))
                done, pending = await asyncio.wait(
                    {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                for task in done:
                    exc = task.exception()
                    if exc:
                        raise exc
        except Exception as e:
            self.status_queue.put(("error", f"Connexion TCI échouée ({uri}) : {e}"))
        finally:
            self._ws = None
            self.status_queue.put(("disconnected", None))

    async def _sender_loop(self, ws):
        while True:
            item = await self._send_queue.get()
            await ws.send(item)

    async def _receiver_loop(self, ws):
        async for message in ws:
            if isinstance(message, (bytes, bytearray)):
                self.binary_queue.put(bytes(message))
            else:
                self.text_queue.put(message)


if __name__ == "__main__":
    import argparse
    import configparser
    import os
    import time

    parser = argparse.ArgumentParser(
        description=(
            "Connexion TCI de test : logue les messages reçus et dumpe les trames "
            "binaires brutes dans un dossier pour inspection manuelle (hexdump)."
        )
    )
    parser.add_argument("--host", default=None, help="Défaut : config.ini [TCI] Host")
    parser.add_argument(
        "--port", type=int, default=None, help="Défaut : config.ini [TCI] Port"
    )
    parser.add_argument("--dump-dir", default="tci_dump")
    parser.add_argument(
        "--duration", type=float, default=30.0, help="Durée d'écoute (s)"
    )
    args = parser.parse_args()

    host, port = args.host, args.port
    if host is None or port is None:
        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini"))
        host = host or cfg.get("TCI", "Host", fallback="127.0.0.1")
        port = port or cfg.getint("TCI", "Port", fallback=5001)

    os.makedirs(args.dump_dir, exist_ok=True)

    client = TCIClient(host, port)
    client.start()

    print(f"[tci_client] Connexion à ws://{host}:{port} (durée : {args.duration}s)...")
    start = time.time()
    frame_count = 0
    try:
        while time.time() - start < args.duration:
            try:
                kind, detail = client.status_queue.get(timeout=0.1)
                print(f"[status] {kind} : {detail}")
            except queue.Empty:
                pass
            try:
                line = client.text_queue.get_nowait()
                print(f"[text] {line}")
            except queue.Empty:
                pass
            try:
                payload = client.binary_queue.get_nowait()
                frame_count += 1
                path = os.path.join(
                    args.dump_dir, f"frame_{frame_count:04d}_{len(payload)}o.bin"
                )
                with open(path, "wb") as f:
                    f.write(payload)
                print(f"[binary] {len(payload)} octets -> {path}")
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
        print(
            f"[tci_client] Arrêt. {frame_count} trame(s) binaire(s) dumpée(s) "
            f"dans {args.dump_dir}/"
        )
