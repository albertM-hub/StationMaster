#!/usr/bin/env python3
"""
test_swr_flex.py — Test autonome des compteurs SWR / FWDPWR / REFPWR du Flex-6500
Auteur : ON5AM — hamanalyst.org

Ce script NE FAIT QU'ÉCOUTER. Il n'envoie JAMAIS d'ordre d'émission (pas de
« xmit », pas de « transmit », pas de « slice set ») : la porteuse se déclenche
à la main depuis AetherSDR, sur charge fictive, à faible puissance.

Commandes envoyées à la radio (toutes en lecture) :
    client udpport <port>   → demande que les compteurs soient envoyés à ce PC
    sub meter all           → abonnement aux descriptions + valeurs des compteurs
    sub tx all              → abonnement à l'état d'émission (lecture seule)
    meter list              → liste des compteurs (nom, source, unité, bornes)

Pourquoi l'UDP : dans l'API SmartSDR (firmware v2/v3), les VALEURS des compteurs
ne passent pas par la connexion TCP 4992 sous forme de lignes texte « M| ».
Elles arrivent en paquets VITA-49 UDP (classe 0x8002) envoyés au port UDP que
le client a déclaré. La connexion TCP ne transporte que les DESCRIPTIONS
(S|meter …) : nom, source, unité, bornes.

Utilisation :
    python3 test_swr_flex.py                  # affichage continu
    python3 test_swr_flex.py --dump           # + liste complète → flex_meters_dump.txt
    python3 test_swr_flex.py --dump fichier.txt --ip 192.168.1.5
    python3 test_swr_flex.py --csv essai_40m.csv
    Ctrl+C pour arrêter.

Sortie écran :
    - au repos : une seule ligne d'état, réécrite sur place ;
    - début d'émission : nouvelle ligne « ▶ DÉBUT » ;
    - pendant l'émission : une nouvelle ligne par seconde avec le SWR brut
      (entier reçu de la radio) ET converti (brut / 128), FWD, REF, ALC ;
    - fin d'émission : ligne « ■ FIN » avec durée, SWR max, FWD max, REF max.
Journal : swr_log.csv (heure, état TX, SWR brut, SWR converti, FWD dBm, REF dBm),
une ligne par seconde.
"""

import argparse
import csv
import os
import re
import socket
import struct
import sys
import threading
import time
from datetime import datetime

FLEX_IP = "192.168.1.5"
FLEX_TCP_PORT = 4992
FLEX_UDP_PORT = 4991  # port UDP de la radio (pour l'enregistrement v3)
VITA_METER_CLASS = 0x8002  # code de classe des paquets compteurs

# Mots interdits : garde-fou, aucune commande contenant l'un d'eux ne part.
COMMANDES_INTERDITES = (
    "xmit",
    "transmit set",
    "tune",
    "mox",
    "slice set",
    "atu",
    "amplifier",
    "interlock",
)


class FlexMeterTest:
    def __init__(self, ip: str):
        self.ip = ip
        self.sock: socket.socket | None = None
        self.udp: socket.socket | None = None
        self.seq = 1
        self.handle = ""  # identifiant client donné par la radio (ligne H)
        self.version = ""  # version du protocole (ligne V)
        self.lock = threading.Lock()
        # id → dict(nam, src, num, unit, low, hi, desc, fps)
        self.meters: dict[str, dict] = {}
        # id → (valeur convertie, valeur brute, heure)
        self.values: dict[str, tuple[float, int, float]] = {}
        self.tx_state = "?"  # état interlock (READY / TRANSMITTING …)
        self.paquets_udp = 0
        self.lignes_m_tcp = 0  # lignes « M| » texte (ancien format) reçues
        self.reponses: dict[int, str] = {}
        self.running = True

    # ── Envoi TCP, avec garde-fou anti-émission ────────────────────────────
    def send(self, cmd: str) -> int:
        low = cmd.lower()
        if any(mot in low for mot in COMMANDES_INTERDITES):
            raise RuntimeError(f"Commande refusée par le garde-fou : {cmd!r}")
        with self.lock:
            seq = self.seq
            self.seq += 1
        self.sock.sendall(f"C{seq}|{cmd}\n".encode())
        return seq

    # ── Connexion ──────────────────────────────────────────────────────────
    def connect(self):
        self.sock = socket.create_connection((self.ip, FLEX_TCP_PORT), timeout=5)
        self.sock.settimeout(None)
        threading.Thread(target=self._tcp_loop, daemon=True).start()

        # Socket UDP locale sur un port libre choisi par le système
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("", 0))
        self.udp.settimeout(1.0)
        udp_port = self.udp.getsockname()[1]
        threading.Thread(target=self._udp_loop, daemon=True).start()

        # Attendre V (version) et H (handle)
        t0 = time.time()
        while not self.handle and time.time() - t0 < 3:
            time.sleep(0.05)
        print(
            f"[TCP] Connecté à {self.ip}:{FLEX_TCP_PORT}  "
            f"version={self.version or '?'}  handle={self.handle or '?'}"
        )

        # 1) Méthode classique : déclarer notre port UDP
        seq = self.send(f"client udpport {udp_port}")
        rep = self._attendre_reponse(seq)
        print(f"[UDP] Port local {udp_port} — « client udpport » → {rep}")
        # 2) Firmware v3+ : udpport peut être refusé → enregistrement par paquet UDP
        if not rep.startswith("0"):
            if self.handle:
                msg = f"client udp_register handle=0x{self.handle}".encode()
                for _ in range(3):
                    self.udp.sendto(msg, (self.ip, FLEX_UDP_PORT))
                    time.sleep(0.1)
                print("[UDP] Enregistrement « udp_register » envoyé (firmware v3)")
            else:
                print("[UDP] Handle inconnu : impossible de s'enregistrer en UDP")

        self.send("sub meter all")
        self.send("sub tx all")
        self.send("meter list")

    def _attendre_reponse(self, seq: int, delai: float = 2.0) -> str:
        t0 = time.time()
        while time.time() - t0 < delai:
            if seq in self.reponses:
                return self.reponses.pop(seq)
            time.sleep(0.05)
        return "pas de réponse"

    # ── Réception TCP : descriptions des compteurs, état TX ────────────────
    def _tcp_loop(self):
        buf = ""
        while self.running:
            try:
                data = self.sock.recv(8192)
            except OSError:
                break
            if not data:
                print("\n[TCP] Connexion fermée par la radio")
                self.running = False
                break
            buf += data.decode(errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                self._tcp_line(line.strip())

    def _tcp_line(self, line: str):
        if not line:
            return
        c = line[0]
        if c == "V":
            self.version = line[1:]
        elif c == "H":
            self.handle = line[1:]
        elif c == "R":
            # R<seq>|<code hex>|<message>
            parts = line[1:].split("|", 2)
            try:
                seq = int(parts[0])
            except ValueError:
                return
            code = parts[1] if len(parts) > 1 else "?"
            msg = parts[2] if len(parts) > 2 else ""
            self.reponses[seq] = code + (f" {msg}" if msg else "")
            # La réponse à « meter list » contient aussi les descriptions
            if code == "0" and ".nam=" in msg:
                self._parse_desc(msg)
        elif c == "S":
            payload = line.split("|", 1)[1] if "|" in line else ""
            if payload.startswith("meter "):
                self._parse_desc(payload[6:])
            elif payload.startswith("interlock "):
                m = re.search(r"\bstate=(\S+)", payload)
                if m:
                    self.tx_state = m.group(1)
        elif c == "M":
            # Ancien format texte : signalé, pour savoir si la radio l'utilise
            self.lignes_m_tcp += 1

    def _parse_desc(self, texte: str):
        """Lit « 7.src=TX-#7.num=1#7.nam=SWR#7.unit=SWR#7.low=1.0#7.hi=999.0#… »."""
        if "removed" in texte:
            return
        for mid, cle, val in re.findall(r"(\d+)\.(\w+)=([^#\s]*)", texte):
            self.meters.setdefault(mid, {})[cle] = val

    # ── Réception UDP : valeurs des compteurs (VITA-49) ────────────────────
    def _udp_loop(self):
        while self.running:
            try:
                data, _ = self.udp.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            self._vita(data)

    def _vita(self, data: bytes):
        if len(data) < 8:
            return
        w0 = struct.unpack_from(">I", data, 0)[0]
        has_class = (w0 >> 27) & 1
        tsi = (w0 >> 22) & 3
        tsf = (w0 >> 20) & 3
        taille = (w0 & 0xFFFF) * 4
        off = 8  # en-tête + stream id
        code_classe = None
        if has_class:
            if len(data) < off + 8:
                return
            code_classe = struct.unpack_from(">I", data, off + 4)[0] & 0xFFFF
            off += 8
        if tsi:
            off += 4
        if tsf:
            off += 8
        if code_classe != VITA_METER_CLASS:
            return  # pas un paquet compteurs
        self.paquets_udp += 1
        fin = min(len(data), taille if taille else len(data))
        maintenant = time.time()
        # Charge utile : paires (id uint16, valeur int16), big-endian
        while off + 4 <= fin:
            mid, raw = struct.unpack_from(">Hh", data, off)
            off += 4
            k = str(mid)
            self.values[k] = (self._convertir(k, raw), raw, maintenant)

    def _convertir(self, mid: str, raw: int) -> float:
        """Conversion brute → unité, comme FlexLib (Meter.cs)."""
        unite = self.meters.get(mid, {}).get("unit", "").lower()
        if unite in ("dbm", "dbfs", "db", "swr"):
            return raw / 128.0
        if unite in ("volts", "amps"):
            return raw / 256.0
        if unite in ("degc", "degf"):
            return raw / 64.0
        return float(raw)  # watts, %, rpm : valeur directe

    # ── Utilitaires d'affichage ────────────────────────────────────────────
    def chercher(self, nom: str):
        """Renvoie (id, valeur convertie, valeur brute, âge) du compteur portant ce nom.
        Les compteurs de source TX passent en priorité. (None…) si aucune valeur reçue.
        """
        candidats = [mid for mid, d in self.meters.items() if d.get("nam") == nom]
        candidats.sort(key=lambda m: not self.meters[m].get("src", "").startswith("TX"))
        for mid in candidats:
            if mid in self.values:
                v, raw, t = self.values[mid]
                return mid, v, raw, time.time() - t
        return (candidats[0] if candidats else None), None, None, None

    def dump(self, chemin: str):
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(f"# Compteurs Flex — {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(
                f"# Radio {self.ip}  protocole={self.version}  état TX={self.tx_state}\n"
            )
            f.write(
                f"# Paquets UDP compteurs reçus : {self.paquets_udp}"
                f"   lignes M| TCP : {self.lignes_m_tcp}\n\n"
            )
            f.write(
                f"{'id':>4}  {'nom':<14}{'source':<10}{'num':<5}{'unité':<8}"
                f"{'bas':>9}{'haut':>9}  {'valeur':>10}  {'brut':>7}  description\n"
            )
            for mid in sorted(self.meters, key=int):
                d = self.meters[mid]
                v = self.values.get(mid)
                val = f"{v[0]:10.3f}" if v else f"{'—':>10}"
                brut = f"{v[1]:7d}" if v else f"{'—':>7}"
                f.write(
                    f"{mid:>4}  {d.get('nam', '?'):<14}{d.get('src', '?'):<10}"
                    f"{d.get('num', '?'):<5}{d.get('unit', '?'):<8}"
                    f"{d.get('low', '?'):>9}{d.get('hi', '?'):>9}  {val}  {brut}  "
                    f"{d.get('desc', '')}\n"
                )
        print(f"\n[DUMP] {len(self.meters)} compteurs écrits dans {chemin}")

    def close(self):
        self.running = False
        for s in (self.sock, self.udp):
            try:
                s.close()
            except Exception:
                pass


def dbm_vers_watts(dbm):
    if dbm is None:
        return None
    return 10 ** ((dbm - 30) / 10)


def main():
    ap = argparse.ArgumentParser(description="Test SWR Flex-6500 (lecture seule)")
    ap.add_argument("--ip", default=FLEX_IP)
    ap.add_argument(
        "--dump",
        nargs="?",
        const="flex_meters_dump.txt",
        default=None,
        help="sauver la liste complète des compteurs (défaut flex_meters_dump.txt)",
    )
    ap.add_argument(
        "--csv",
        default="swr_log.csv",
        help="journal CSV, une ligne par seconde (défaut swr_log.csv, ouvert en ajout)",
    )
    args = ap.parse_args()

    t = FlexMeterTest(args.ip)
    try:
        t.connect()
    except OSError as e:
        print(f"[ERREUR] Connexion impossible à {args.ip}:{FLEX_TCP_PORT} : {e}")
        sys.exit(1)

    time.sleep(2.0)
    print(f"[INFO] {len(t.meters)} compteurs décrits. Compteurs TX trouvés :")
    for nom in ("FWDPWR", "REFPWR", "SWR", "ALC", "HWALC"):
        mids = [m for m, d in t.meters.items() if d.get("nam") == nom]
        for m in mids:
            d = t.meters[m]
            print(
                f"    {nom:<7} id={m:<4} src={d.get('src', '?'):<6} unité={d.get('unit', '?')}"
                f"  bornes {d.get('low', '?')}…{d.get('hi', '?')}"
            )
        if not mids:
            print(f"    {nom:<7} absent")
    print("\nDéclenchez la porteuse dans AetherSDR (charge fictive, faible puissance).")
    print("Ctrl+C pour arrêter.\n")

    # Journal CSV : une ligne par seconde, en émission comme au repos.
    # Ouvert en ajout : plusieurs essais successifs s'enchaînent dans le même fichier.
    csv_neuf = not os.path.exists(args.csv) or os.path.getsize(args.csv) == 0
    csv_f = open(args.csv, "a", newline="", encoding="utf-8")
    csv_w = csv.writer(csv_f)
    if csv_neuf:
        csv_w.writerow(
            ["heure", "etat_tx", "swr_brut", "swr_converti", "fwd_dbm", "ref_dbm"]
        )
    print(f"[CSV] Journal : {os.path.abspath(args.csv)}\n")

    emission_prec = False  # état TX au tour précédent
    num_emission = 0  # compteur d'émissions depuis le lancement
    debut_tx = 0.0
    max_swr = max_fwd = max_ref = None  # maxima de l'émission en cours
    dernier_csv = 0.0  # instant de la dernière écriture CSV (1/s)

    def fmt(v, f):
        return "—" if v is None else format(v, f)

    def maxi(a, b):
        return b if a is None else (a if b is None else max(a, b))

    try:
        while t.running:
            _, swr, swr_raw, age_s = t.chercher("SWR")
            _, fwd, _, _ = t.chercher("FWDPWR")
            _, ref, _, _ = t.chercher("REFPWR")
            _, alc, _, _ = t.chercher("ALC")
            emission = t.tx_state == "TRANSMITTING"
            maintenant = time.time()
            heure = datetime.now().strftime("%H:%M:%S")

            # ── Début d'émission : nouvelle ligne, remise à zéro des maxima ──
            if emission and not emission_prec:
                num_emission += 1
                debut_tx = maintenant
                max_swr = max_fwd = max_ref = None
                dernier_csv = 0.0  # loguer tout de suite
                print(f"\r{' ' * 120}\r", end="")
                print(f"{heure}  ▶ DÉBUT émission n°{num_emission}")

            # Maxima mesurés à chaque tour (0,1 s) pendant l'émission
            if emission:
                max_swr = maxi(max_swr, swr)
                max_fwd = maxi(max_fwd, fwd)
                max_ref = maxi(max_ref, ref)

            # ── Fin d'émission : nouvelle ligne avec le bilan ──
            if emission_prec and not emission:
                duree = maintenant - debut_tx
                fw, rw = dbm_vers_watts(max_fwd), dbm_vers_watts(max_ref)
                print(
                    f"{heure}  ■ FIN émission n°{num_emission}  ({duree:.1f} s, "
                    f"état {t.tx_state})  SWR max={fmt(max_swr, '.2f')}:1  "
                    f"FWD max={fmt(max_fwd, '.1f')} dBm ({fmt(fw, '.1f')} W)  "
                    f"REF max={fmt(max_ref, '.1f')} dBm ({fmt(rw, '.2f')} W)"
                )
            emission_prec = emission

            # ── Une fois par seconde : CSV + ligne d'émission ──
            if maintenant - dernier_csv >= 1.0:
                dernier_csv = maintenant
                csv_w.writerow(
                    [
                        heure,
                        t.tx_state,
                        "" if swr_raw is None else swr_raw,
                        "" if swr is None else f"{swr:.3f}",
                        "" if fwd is None else f"{fwd:.2f}",
                        "" if ref is None else f"{ref:.2f}",
                    ]
                )
                csv_f.flush()
                if emission:
                    # Nouvelle ligne à chaque seconde d'émission : brut ET converti
                    fw, rw = dbm_vers_watts(fwd), dbm_vers_watts(ref)
                    print(
                        f"{heure}    SWR brut={fmt(swr_raw, '6d')}"
                        f" → {fmt(swr, '5.2f')}:1"
                        f"  FWD={fmt(fwd, '6.1f')} dBm ({fmt(fw, '6.1f')} W)"
                        f"  REF={fmt(ref, '6.1f')} dBm ({fmt(rw, '5.2f')} W)"
                        f"  ALC={fmt(alc, '5.1f')}"
                        f"{'' if age_s is None or age_s < 2 else f'  (SWR figé {age_s:.0f}s)'}"
                    )

            # Au repos : une seule ligne d'état réécrite (pas d'historique utile)
            if not emission:
                print(
                    f"\r{heure}  repos ({t.tx_state})  SWR={fmt(swr, '.2f')}"
                    f"  UDP={t.paquets_udp}  émissions={num_emission}   ",
                    end="",
                    flush=True,
                )
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        print()
        csv_f.close()
        print(f"[CSV] Journal fermé : {os.path.abspath(args.csv)}")
        if t.paquets_udp == 0:
            print(
                "[ATTENTION] Aucun paquet UDP compteurs reçu : vérifier pare-feu "
                "(ufw) et que la radio accepte « client udpport »."
            )
        if t.lignes_m_tcp:
            print(
                f"[INFO] {t.lignes_m_tcp} lignes « M| » texte reçues en TCP (ancien format)."
            )
        if args.dump:
            t.dump(args.dump)
        t.close()


if __name__ == "__main__":
    main()
