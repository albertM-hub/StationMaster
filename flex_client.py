#!/usr/bin/env python3
"""
flex_client.py - Client TCP pour Flex-6500 via FlexAPI
Auteur : ON5AM — hamanalyst.org
Solution mètres : deux connexions TCP simultanées
  - Connexion 1 (principale) : état radio, slices, interlock
  - Connexion 2 (mètres)     : sub meter all → reçoit M| en temps réel
"""

import socket, threading, time, math
from dataclasses import dataclass
from typing import Optional, Callable

FLEX_IP   = "192.168.1.5"
FLEX_PORT = 4992

@dataclass
class RadioState:
    frequency:       float = 0.0
    mode:            str   = "?"
    tx_active:       bool  = False
    rx_ant:          str   = "?"
    tx_ant:          str   = "?"
    filter_lo:       int   = 0
    filter_hi:       int   = 3000
    smeter:          float = -140.0
    power_fwd:       float = 0.0
    swr:             float = 1.0
    alc:             float = 0.0
    panadapters:     int   = 0
    slices:          int   = 0
    connected:       bool  = False
    interlock_state: str   = "READY"
    pa_temp:         float = 0.0
    v13a:            float = 0.0
    v13b:            float = 0.0

    def freq_str(self):
        khz = int(self.frequency * 1000)
        return f"{khz//1000}.{khz%1000:03d}"

    def smeter_s(self):
        dbm = self.smeter
        # Standard ITU HF : S9 = -73 dBm, 6 dB par unité S
        if dbm <= -121: return "S1"
        if dbm >= -73:
            excess = int(dbm + 73)
            return "S9" if excess == 0 else f"S9+{excess}dB"
        s = min(9, round((dbm + 121) / 6) + 1)
        return f"S{max(1, s)}"


class FlexClient:
    def __init__(self, ip=FLEX_IP, port=FLEX_PORT):
        self.ip, self.port = ip, port
        self.state     = RadioState()
        self._seq      = 1
        self._running  = False
        self._lock     = threading.Lock()
        self._meter_map: dict = {}          # meter_id → name
        self._meter_scale: dict = {}        # meter_id → (low, high) pour scaling M|
        # Mapping seq → meter_id pour corréler R| avec meter get
        self._pending_meter_gets: dict = {}
        self._pending_meter_list: set = set()  # seq en attente de meter list
        self.on_update: Optional[Callable] = None
        # Connexion principale
        self._sock: Optional[socket.socket] = None
        # Connexion secondaire dédiée aux mètres
        self._meter_sock: Optional[socket.socket] = None

    # ── Connexion ────────────────────────────────────────────────
    def connect(self) -> bool:
        try:
            # Connexion principale
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5)
            self._sock.connect((self.ip, self.port))
            self._sock.settimeout(None)
            self.state.connected = True
            print(f"[OK] Connexion principale {self.ip}:{self.port}")

            self._running = True
            threading.Thread(target=self._read_loop,
                             args=(self._sock, "MAIN"), daemon=True).start()
            time.sleep(0.4)
            self._send(self._sock, "sub slice all")
            self._send(self._sock, "sub meter all")
            # Demander la liste des mètres pour peupler _meter_map et _meter_scale
            seq = self._send(self._sock, "meter list")
            self._pending_meter_list.add(seq)

            # Connexion secondaire pour les mètres
            time.sleep(0.3)
            self._connect_meter_client()

            # Threads de polling
            threading.Thread(target=self._static_meter_loop, daemon=True).start()
            threading.Thread(target=self._cat_loop,          daemon=True).start()
            return True
        except Exception as e:
            print(f"[ERREUR] Connexion : {e}")
            self.state.connected = False
            return False

    def _connect_meter_client(self):
        """Ouvre une 2e connexion TCP dédiée à la réception des mètres."""
        try:
            self._meter_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._meter_sock.settimeout(5)
            self._meter_sock.connect((self.ip, self.port))
            self._meter_sock.settimeout(None)
            print("[OK] Connexion mètres établie")
            threading.Thread(target=self._read_loop,
                             args=(self._meter_sock, "METER"), daemon=True).start()
            time.sleep(0.3)
            self._send(self._meter_sock, "sub meter all")
            # NE PAS demander meter get ici — le _meter_map n'est pas encore
            # construit. Le _static_meter_loop s'en chargera après 3s.
        except Exception as e:
            print(f"[WARN] Connexion mètres impossible : {e}")

    def _static_meter_loop(self):
        """Attend le meter list pour peupler _meter_map — pas de polling (bloqué firmware)."""
        time.sleep(3.0)
        if not self._meter_map:
            print("[StaticMeters] meter_map vide → nouvel essai 'meter list'")
            sock = self._meter_sock or self._sock
            if sock:
                seq = self._send(sock, "meter list")
                self._pending_meter_list.add(seq)
            time.sleep(1.5)
        print(f"[StaticMeters] {len(self._meter_map)} mètres identifiés")

    def _rigctld_get(self, sock, cmd: str) -> str:
        """Envoie une commande rigctld, retourne la valeur (draine aussi le RPRT final)."""
        try:
            sock.sendall((cmd + "\n").encode())
            buf = ""
            result = ""
            while True:
                try:
                    chunk = sock.recv(256).decode(errors="replace")
                    if not chunk: break
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line.startswith("RPRT"):
                            return result   # fin de réponse
                        if line and not result:
                            result = line   # première ligne non-vide = valeur
                except socket.timeout:
                    return result
        except Exception:
            return ""
        return result

    def _cat_loop(self):
        """rigctld AetherSDR port 4532 (priorité) → SmartSDR CAT port 5003 (fallback)."""
        import re as _re
        while self._running:
            # ── Essai 1 : rigctld (AetherSDR, protocole Hamlib) ────────────────
            try:
                sock = socket.socket()
                sock.settimeout(3)
                sock.connect(("127.0.0.1", 4532))
                sock.settimeout(0.5)
                print("[CAT] rigctld port 4532 ✅")
                print("[CAT] rigctld: RFPOWER_METER OK — S-meter non dispo (STRENGTH RPRT-11)")
                while self._running:
                    # Puissance TX mesurée : 0.0-1.0 → watts (Flex-6500 ≈ 100W max)
                    p = self._rigctld_get(sock, "l RFPOWER_METER")
                    if p:
                        try:
                            ratio = float(p)
                            tx = self.state.tx_active
                            new_pwr = round(ratio * 100.0, 1) if tx else 0.0
                            if new_pwr != self.state.power_fwd:
                                self.state.power_fwd = new_pwr
                                if self.on_update:
                                    self.on_update(self.state)
                        except ValueError:
                            pass
                    time.sleep(0.5)
            except ConnectionRefusedError:
                pass
            except Exception as e:
                print(f"[CAT] rigctld erreur : {e}")

            if not self._running: break

            # ── Essai 2 : SmartSDR CAT port 5003 (fallback) ─────────────────────
            try:
                sock = socket.socket()
                sock.settimeout(3)
                sock.connect(("127.0.0.1", 5003))
                sock.settimeout(2)
                print("[CAT] SmartSDR port 5003 ✅")
                sm_cmd = b"SM;"
                buf = ""
                _dbg = 0
                while self._running:
                    try:
                        sock.sendall(b"PC;" + sm_cmd)
                    except:
                        break
                    time.sleep(0.5)
                    try:
                        data = sock.recv(512).decode(errors="replace")
                        buf += data
                    except socket.timeout:
                        continue
                    except:
                        break
                    if _dbg < 4:
                        print(f"  [CAT5003 RAW] {repr(buf[:80])}")
                        _dbg += 1
                    changed = False
                    tx = (self.state.interlock_state == "TRANSMITTING")
                    while ";" in buf:
                        resp, buf = buf.split(";", 1)
                        resp = resp.strip()
                        if not resp: continue
                        if resp == "?":
                            sm_cmd = b"SM0;" if sm_cmd == b"SM;" else b"SM;"
                            continue
                        m = _re.match(r"PC(\d{3})", resp)
                        if m:
                            pct = int(m.group(1))
                            self.state.power_fwd = round(float(pct), 1) if tx else 0.0
                            changed = True; continue
                        m = _re.match(r"SM0?(\d+)", resp)
                        if m:
                            raw = int(m.group(1))
                            ratio = min(1.0, raw / 30.0)
                            self.state.smeter = round(-140.0 + ratio * 107.0, 1)
                            changed = True; continue
                    if changed and self.on_update:
                        self.on_update(self.state)
            except ConnectionRefusedError:
                pass
            except Exception as e:
                print(f"[CAT] SmartSDR erreur : {e}")
            time.sleep(5)

    def disconnect(self):
        self._running = False
        for s in (self._sock, self._meter_sock):
            if s:
                try: s.close()
                except: pass
        self.state.connected = False
        print("[INFO] Déconnecté")

    # ── Envoi commandes ──────────────────────────────────────────
    def _send(self, sock, cmd: str) -> int:
        with self._lock:
            seq = self._seq; self._seq += 1
        try:
            sock.sendall(f"C{seq}|{cmd}\n".encode())
        except Exception as e:
            print(f"[ERREUR] Envoi '{cmd}' : {e}")
        return seq

    def _send_meter_get(self, sock, meter_id: str):
        """Envoie 'meter get <id>' et enregistre seq → meter_id."""
        seq = self._send(sock, f"meter get {meter_id}")
        self._pending_meter_gets[seq] = meter_id
        return seq

    def send_command(self, cmd: str) -> int:
        return self._send(self._sock, cmd)

    # FlexAPI slice set bloqué côté client secondaire (erreur 5000002D) →
    # on passe par rigctld AetherSDR port 4532
    _FLEX_TO_HAMLIB_MODE = {
        "DIGU": "PKTUSB", "DIGL": "PKTLSB",
        "SAM":  "AM",     "NFM":  "FM", "DFM": "FM",
    }

    def _rigctld_set(self, cmd: str) -> bool:
        """Envoie une commande set à rigctld (nouvelle connexion), retourne True si RPRT 0."""
        try:
            s = socket.socket()
            s.settimeout(2)
            s.connect(("127.0.0.1", 4532))
            s.settimeout(1)
            s.sendall((cmd + "\n").encode())
            buf = ""
            while True:
                try:
                    chunk = s.recv(256).decode(errors="replace")
                    if not chunk: break
                    buf += chunk
                    if "\n" in buf:
                        line = buf.split("\n")[0].strip()
                        s.close()
                        return line == "RPRT 0"
                except socket.timeout:
                    break
            s.close()
        except Exception as e:
            print(f"[rigctld] '{cmd}' erreur: {e}")
        return False

    def set_frequency(self, freq_mhz: float, slice_id: int = 0):
        self._rigctld_set(f"F {int(freq_mhz * 1_000_000)}")

    def set_mode(self, mode: str, slice_id: int = 0):
        hmode = self._FLEX_TO_HAMLIB_MODE.get(mode, mode)
        self._rigctld_set(f"M {hmode} 0")

    def set_tx(self, active: bool):
        self.send_command(f"xmit {'1' if active else '0'}")

    def set_filter(self, lo: int, hi: int, slice_id: int = 0):
        self.send_command(f"slice set {slice_id} filter_lo={lo} filter_hi={hi}")

    # ── Lecture (commune aux deux connexions) ────────────────────
    def _read_loop(self, sock, label: str):
        buf = ""
        while self._running:
            try:
                data = sock.recv(4096).decode(errors="replace")
                if not data:
                    print(f"[INFO] {label} fermé par le radio")
                    if label == "MAIN":
                        self.state.connected = False
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._parse_line(line, label)
            except Exception as e:
                if self._running:
                    print(f"[ERREUR] {label} lecture : {e}")
                break

    # ── Parsing ──────────────────────────────────────────────────
    def _parse_line(self, line: str, label: str = ""):
        if not line: return
        p = line[0]

        if p in ("V", "H"): return

        # R<seq>|code|value — réponse à une commande
        if p == "R":
            parts = line.split("|", 3)
            if len(parts) >= 3:
                try:
                    seq_chk = int(line[1:].split("|")[0])
                    if seq_chk in self._pending_meter_list:
                        if parts[1] != "0":
                            print(f"  [meter list ERREUR] code={parts[1]} msg={parts[2] if len(parts)>2 else '?'!r}")
                            self._pending_meter_list.discard(seq_chk)
                            return
                except Exception: pass
            if len(parts) >= 3 and parts[1] == "0":
                try:
                    seq     = int(line[1:].split("|")[0])
                    val_str = parts[2].strip()
                    # Réponse à meter list
                    if seq in self._pending_meter_list:
                        self._pending_meter_list.discard(seq)
                        print(f"  [meter list R|] code={parts[1]} val={val_str[:200]!r}")
                        self._parse_meter_list_response(val_str)
                        return
                    # Réponse à meter get
                    meter_id = self._pending_meter_gets.pop(seq, None)
                    if meter_id and val_str:
                        tokens = val_str.split()
                        if len(tokens) >= 2 and tokens[0].isdigit():
                            self._parse_meter_get_response(tokens[0], tokens[1])
                        elif len(tokens) == 1:
                            self._parse_meter_get_response(meter_id, tokens[0])
                    elif meter_id:
                        print(f"  [R| meter get] seq={seq} id={meter_id} val_str vide!")
                except Exception as e:
                    print(f"[R|] parse error: {e} line={line!r}")
            elif len(parts) >= 2 and parts[1] != "0":
                try:
                    seq_chk = int(line[1:].split("|")[0])
                    if seq_chk in self._pending_meter_gets:
                        mid = self._pending_meter_gets.pop(seq_chk)
                        print(f"  [R| meter get ERREUR] seq={seq_chk} id={mid} code={parts[1]}")
                except Exception: pass
            return

        if p == "S":
            parts = line.split("|", 1)
            if len(parts) == 2:
                self._parse_status(parts[1])
            return

        if p == "M":
            parts = line.split("|", 1)
            if len(parts) == 2:
                self._parse_meters(parts[1])
            return

    def _parse_meter_get_response(self, meter_id: str, val_str: str):
        """Parse réponse à 'meter get <id>'."""
        try:
            try:
                raw = int(val_str, 16)
                if raw > 32767:
                    raw -= 65536
                if meter_id in self._meter_scale:
                    lo, hi = self._meter_scale[meter_id]
                    val = lo + (raw + 32768) * (hi - lo) / 65535.0
                else:
                    val = raw / 1000.0
            except ValueError:
                # La réponse est parfois un flottant décimal direct
                val = float(val_str)
            name = self._meter_map.get(meter_id, "")
            print(f"  [METER GET] id={meter_id}  nom={name or '?'}  val={val:.3f}")
            self._apply_meter(meter_id, val)
        except Exception as e:
            print(f"  [METER GET] parse error: {e} id={meter_id} val={val_str!r}")

    def _parse_status(self, payload: str):
        changed = False

        if payload.startswith("radio "):
            kv = self._kv(payload[6:])
            if "slices" in kv:      self.state.slices = int(kv["slices"]); changed = True
            if "panadapters" in kv: self.state.panadapters = int(kv["panadapters"]); changed = True

        elif payload.startswith("slice "):
            parts = payload.split(" ", 2)
            if len(parts) < 3: return
            kv = self._kv(parts[2])
            if "RF_frequency" in kv: self.state.frequency = float(kv["RF_frequency"]); changed = True
            if "mode"         in kv: self.state.mode = kv["mode"]; changed = True
            if "rxant"        in kv: self.state.rx_ant = kv["rxant"]; changed = True
            if "txant"        in kv: self.state.tx_ant = kv["txant"]; changed = True
            if "filter_lo"    in kv: self.state.filter_lo = int(float(kv["filter_lo"])); changed = True
            if "filter_hi"    in kv: self.state.filter_hi = int(float(kv["filter_hi"])); changed = True

        elif payload.startswith("interlock "):
            kv = self._kv(payload[10:])
            if "state" in kv:
                prev = self.state.interlock_state
                self.state.interlock_state = kv["state"]
                self.state.tx_active = (kv["state"] == "TRANSMITTING")
                # Reset puissance à 0 quand TX termine
                if kv["state"] in ("READY", "UNKEY_REQUESTED") and prev == "TRANSMITTING":
                    self.state.power_fwd = 0.0
                    self.state.swr = 1.0
                if kv["state"] != prev: changed = True

        elif payload.startswith("meter "):
            rest = payload[6:]
            if "removed" in rest: return
            print(f"  [S|meter DBG] {rest[:160]!r}")
            dot = rest.find(".")
            if dot == -1: return
            mid = rest[:dot]
            low_val = hi_val = None
            for chunk in rest.split("#"):
                chunk = chunk.strip()
                if ".nam=" in chunk:
                    name = chunk.split(".nam=", 1)[1].split()[0].strip()
                    self._meter_map[mid] = name
                if ".low=" in chunk:
                    try:
                        low_val = float(chunk.split(".low=", 1)[1].split()[0].strip())
                    except Exception: pass
                if ".hi=" in chunk:
                    try:
                        hi_val = float(chunk.split(".hi=", 1)[1].split()[0].strip())
                    except Exception: pass
            if low_val is not None and hi_val is not None:
                self._meter_scale[mid] = (low_val, hi_val)

        elif payload.startswith("display pan "):
            kv = self._kv(payload[12:])

        if changed and self.on_update:
            self.on_update(self.state)

    def _parse_meter_list_response(self, payload: str):
        """Parse réponse à 'meter list' : '1.nam=LEVEL 1.low=-150 1.hi=0 2.nam=FWDPWR ...'"""
        import re
        for m in re.finditer(r'(\d+)\.(nam|low|hi)=(-?[\d.]+|\w+)', payload):
            mid, key, val = m.group(1), m.group(2), m.group(3)
            if key == "nam":
                self._meter_map[mid] = val
            elif key == "low":
                try:
                    lo = float(val)
                    cur = self._meter_scale.get(mid, (0.0, 0.0))
                    self._meter_scale[mid] = (lo, cur[1])
                except Exception: pass
            elif key == "hi":
                try:
                    hi = float(val)
                    cur = self._meter_scale.get(mid, (0.0, 0.0))
                    self._meter_scale[mid] = (cur[0], hi)
                except Exception: pass
        print(f"[MeterList] {len(self._meter_map)} mètres: {self._meter_map}")
        print(f"[MeterList] scales: {self._meter_scale}")

    def _parse_meters(self, payload: str):
        """Format M| : supporte 'id hex id hex ...' ET 'id=hex id=hex ...'"""
        tokens = payload.split()
        if not tokens:
            return

        # Debug : affiche les 8 premiers paquets M| reçus
        if not hasattr(self, '_m_dbg'):
            self._m_dbg = 0
        if self._m_dbg < 8:
            print(f"  [M| DBG #{self._m_dbg}] {payload[:120]!r}")
            self._m_dbg += 1

        def _apply(mid, hexval):
            try:
                raw = int(hexval, 16)
                if raw > 32767: raw -= 65536
                if mid in self._meter_scale:
                    lo, hi = self._meter_scale[mid]
                    val = lo + (raw + 32768) * (hi - lo) / 65535.0
                else:
                    val = raw / 1000.0
                self._apply_meter(mid, val)
            except ValueError:
                pass

        if '=' in tokens[0]:
            # Format "id=hexval id=hexval ..."
            for token in tokens:
                if '=' not in token:
                    continue
                mid, hexval = token.split('=', 1)
                if mid.isdigit():
                    _apply(mid, hexval)
        else:
            # Format "id hexval id hexval ..."
            if not tokens[0].isdigit():
                return
            i = 0
            while i + 1 < len(tokens):
                mid    = tokens[i]
                hexval = tokens[i+1]
                i += 2
                if mid.isdigit():
                    _apply(mid, hexval)

    def _apply_meter(self, meter_id: str, value: float):
        name    = self._meter_map.get(meter_id, "")
        changed = False

        if name == "LEVEL":
            self.state.smeter = value; changed = True
        elif name == "FWDPWR":
            watts = round(10**((value-30)/10), 1) if value > -100 else 0.0
            self.state.power_fwd = watts; changed = True
        elif name == "SWR":
            self.state.swr = max(1.0, value); changed = True
        elif name == "ALC":
            self.state.alc = value; changed = True
        elif name == "+13.8A":
            self.state.v13a = value; changed = True
        elif name == "+13.8B":
            self.state.v13b = value; changed = True
        elif name == "PATEMP":
            self.state.pa_temp = value; changed = True

        if changed and self.on_update:
            self.on_update(self.state)

    @staticmethod
    def _kv(text: str) -> dict:
        result = {}
        for token in text.split():
            if "=" in token:
                k, v = token.split("=", 1)
                result[k] = v
        return result