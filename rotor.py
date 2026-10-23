"""
rotor.py — Interface Python pour contrôleur de rotor GS-232 (Yaesu GS-232A/B,
émulation K3NG Arduino, etc.)
ON5AM — hamanalyst.org

Règles de sécurité :
  - le port n'est ouvert que par open() (appelé au clic sur « Connecter ») ;
  - un seul programme à la fois sur le port (vérif /proc + verrou exclusif) ;
  - close() envoie toujours S avant de fermer ;
  - aucune méthode ne déclenche de mouvement d'elle-même : seul l'appelant
    (les boutons GO / CCW / CW) le fait.
"""

import fcntl
import os
import re
import termios
import time

import serial

# ─── Commandes GS-232 (terminées par CR) ─────────────────────────────────────
CMD_STOP = b"S\r"  # stop tous axes
CMD_CCW = b"L\r"  # rotation anti-horaire continue
CMD_CW = b"R\r"  # rotation horaire continue
CMD_READ = b"C\r"  # lecture azimut — ne fait pas bouger l'antenne

# Réponses possibles à C : GS-232B « AZ=123 », GS-232A « +0123 »
_RE_AZ = re.compile(rb"(?:AZ=|\+)\s*(\d{1,4})")


class RotorError(Exception):
    pass


def port_users(port: str) -> list:
    """
    Liste des processus qui ont déjà ce port ouvert (lecture /proc).
    Retourne [(pid, nom), ...]. Liste vide si personne ou si /proc illisible.
    """
    try:
        target = os.path.realpath(port)
    except OSError:
        return []
    me = os.getpid()
    users = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        fd_dir = f"/proc/{pid}/fd"
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue  # processus d'un autre utilisateur ou disparu
        for fd in fds:
            try:
                if os.readlink(os.path.join(fd_dir, fd)) == target:
                    try:
                        with open(f"/proc/{pid}/comm") as f:
                            name = f.read().strip()
                    except OSError:
                        name = "?"
                    users.append((int(pid), name))
                    break
            except OSError:
                continue
    return users


class Rotor:
    """
    Contrôleur GS-232 sur port série.

    Non thread-safe : à n'utiliser que depuis un seul thread (le thread série
    de tab_rotor). max_az = 360 ou 450 selon le contrôleur (overlap).
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        max_az: int = 360,
        timeout: float = 0.5,
        settle_s: float = 2.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.max_az = max_az
        self.timeout = timeout
        self.settle_s = settle_s  # attente après ouverture (reset Arduino)
        self._ser: serial.Serial = None

    # ── Connexion ─────────────────────────────────────────────────────────────
    def open(self):
        users = port_users(self.port)
        if users:
            noms = ", ".join(f"{n} (PID {p})" for p, n in users)
            raise RotorError(f"Port déjà utilisé par : {noms}")
        try:
            # exclusive=True → flock : refuse si un autre programme a verrouillé
            self._ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
                exclusive=True,
            )
        except serial.SerialException as e:
            msg = str(e)
            if "Errno 2" in msg or "No such file" in msg:
                raise RotorError("Port introuvable — câble débranché ?") from e
            if "Errno 13" in msg or "Permission" in msg:
                raise RotorError("Accès refusé (groupe dialout ?)") from e
            if "Errno 16" in msg or "busy" in msg.lower() or "lock" in msg.lower():
                raise RotorError("Port occupé par un autre programme") from e
            raise RotorError(msg[:60]) from e
        # TIOCEXCL : plus aucun autre open() possible tant qu'on tient le port
        try:
            fcntl.ioctl(self._ser.fileno(), termios.TIOCEXCL)
        except (OSError, AttributeError):
            pass
        # L'ouverture du port (DTR) redémarre souvent l'Arduino K3NG : laisser
        # le firmware démarrer avant la première commande, puis jeter son bavardage
        time.sleep(self.settle_s)
        self._ser.reset_input_buffer()

    def close(self):
        """Envoie S puis ferme le port — toujours, même après une erreur."""
        if self._ser is None:
            return
        acked = False
        try:
            # Attendre le OK : sans lui, close() peut jeter le S encore dans la
            # puce CH340 (flush() rend la main avant l'envoi réel) → GO non arrêté
            acked = self._stop_ack()
            if not acked:
                print("[ROTOR] ⚠ S de fermeture non confirmé par le contrôleur")
        except Exception as e:
            print(f"[ROTOR] ⚠ S de fermeture : {e}")
        finally:
            # Lever TIOCEXCL, sinon le tty peut rester verrouillé après fermeture
            try:
                fcntl.ioctl(self._ser.fileno(), termios.TIOCNXCL)
            except (OSError, AttributeError, ValueError):
                pass
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        return acked

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    # ── Commandes ─────────────────────────────────────────────────────────────
    def _write(self, data: bytes):
        if not self.is_open:
            raise RotorError("Port non connecté")
        self._ser.write(data)
        self._ser.flush()

    def _stop_ack(self, tries: int = 2, wait_s: float = 1.0) -> bool:
        """Envoie S et attend le « OK » du firmware ON5AM ; renvoie S si rien.
        Retourne True si le contrôleur a confirmé l'arrêt."""
        for _ in range(tries):
            self._ser.reset_input_buffer()   # jeter une réponse C en retard
            self._ser.write(CMD_STOP)
            self._ser.flush()
            buf = b""
            deadline = time.monotonic() + wait_s
            while time.monotonic() < deadline:
                buf += self._ser.read(self._ser.in_waiting or 1)
                if b"OK" in buf:
                    return True
        return False

    def stop(self) -> bool:
        """S avec accusé de réception. True = arrêt confirmé par le contrôleur."""
        if not self.is_open:
            raise RotorError("Port non connecté")
        return self._stop_ack()

    def ccw(self):
        self._write(CMD_CCW)

    def cw(self):
        self._write(CMD_CW)

    def goto(self, az: int):
        """Envoie Mxxx. Lève RotorError si az hors plage 0..max_az."""
        az = int(az)
        if not 0 <= az <= self.max_az:
            raise RotorError(f"Azimut hors plage (0–{self.max_az}°)")
        self._write(f"M{az:03d}\r".encode("ascii"))
        # Certains contrôleurs répondent (CR / écho) : on vide pour ne pas
        # polluer la prochaine lecture C
        self._ser.reset_input_buffer()

    def read_az(self):
        """Lecture azimut (commande C). Retourne un int, ou None si pas de réponse."""
        if not self.is_open:
            raise RotorError("Port non connecté")
        self._ser.reset_input_buffer()
        self._ser.write(CMD_READ)
        self._ser.flush()
        line = self._ser.read_until(b"\r")
        m = _RE_AZ.search(line)
        return int(m.group(1)) if m else None
