"""
spe_expert.py — Interface Python pour l'ampli SPE Expert 1.3K-FA / 2K-FA
Protocole : Application Programmer's Guide Rev. 1.1 (SPE)
ON5AM — hamanalyst.org
"""

import serial
import time
from dataclasses import dataclass
from typing import Optional


# ─── Constantes protocole ────────────────────────────────────────────────────

SYN_HOST = bytes([0x55, 0x55, 0x55])   # Sync host → ampli
SYN_AMP  = bytes([0xAA, 0xAA, 0xAA])   # Sync ampli → host

# Codes de commandes (équivalent touches du panneau avant)
CMD = {
    'INPUT'      : 0x01,
    'BAND_DOWN'  : 0x02,
    'BAND_UP'    : 0x03,
    'ANTENNA'    : 0x04,
    'L_DOWN'     : 0x05,
    'L_UP'       : 0x06,
    'C_DOWN'     : 0x07,
    'C_UP'       : 0x08,
    'TUNE'       : 0x09,
    'OFF'        : 0x0A,
    'POWER'      : 0x0B,
    'DISPLAY'    : 0x0C,
    'OPERATE'    : 0x0D,
    'CAT'        : 0x0E,
    'LEFT'       : 0x0F,
    'RIGHT'      : 0x10,
    'SET'        : 0x11,
    'BACKLIGHT_ON'  : 0x82,
    'BACKLIGHT_OFF' : 0x83,
    'STATUS'     : 0x90,
}

BAND_MAP = {
    '00': '160m', '01': '80m',  '02': '60m',
    '03': '40m',  '04': '30m',  '05': '20m',
    '06': '17m',  '07': '15m',  '08': '12m',
    '09': '10m',  '10': '6m',   '11': '4m',
}

POWER_MAP = {'L': 'LOW', 'M': 'MID', 'H': 'HIGH'}

WARNINGS = {
    'M': 'ALARM AMPLIFIER',      'A': 'NO SELECTED ANTENNA',
    'S': 'SWR ANTENNA',          'B': 'NO VALID BAND',
    'P': 'POWER LIMIT EXCEEDED', 'O': 'OVERHEATING',
    'Y': 'ATU NOT AVAILABLE',    'W': 'TUNING WITH NO POWER',
    'K': 'ATU BYPASSED',         'R': 'POWER HELD BY REMOTE',
    'T': 'COMBINER OVERHEATING', 'C': 'COMBINER FAULT',
    'N': None,
}

ALARMS = {
    'S': 'SWR EXCEEDING LIMITS', 'A': 'AMPLIFIER PROTECTION',
    'D': 'INPUT OVERDRIVING',    'H': 'EXCESS OVERHEATING',
    'C': 'COMBINER FAULT',       'N': None,
}


# ─── Structure de données statut ─────────────────────────────────────────────

@dataclass
class AmpStatus:
    amp_id:      str    # '13K' ou '20K'
    mode:        str    # 'Standby' ou 'Operate'
    rx_tx:       str    # 'RX' ou 'TX'
    bank:        str    # 'A' ou 'B'
    input_port:  int    # 1 ou 2
    band:        str    # '20m', '40m', etc.
    tx_ant:      str    # ex. '1a' (antenne 1, ATU enabled)
    rx_ant:      str    # ex. '0r'
    power_level: str    # 'LOW', 'MID', 'HIGH'
    out_power_w: int    # Watts
    swr_atu:     float  # SWR avant ATU
    swr_ant:     float  # SWR antenne
    vpa:         float  # Tension PA (V)
    ipa:         float  # Courant PA (A)
    temp_c:      int    # Température heatsink (°C)
    warning:     Optional[str]
    alarm:       Optional[str]

    def __str__(self):
        lines = [
            f"╔══ SPE Expert {self.amp_id} ══════════════════════╗",
            f"  Mode      : {self.mode} | {self.rx_tx} | Bank {self.bank} | Input {self.input_port}",
            f"  Bande     : {self.band}   Antenne TX: {self.tx_ant}   RX: {self.rx_ant}",
            f"  Puissance : {self.out_power_w:>4d} W  ({self.power_level})",
            f"  SWR ATU   : {self.swr_atu:.2f}    SWR Ant : {self.swr_ant:.2f}",
            f"  PA        : {self.vpa:.1f} V  /  {self.ipa:.1f} A",
            f"  Temp      : {self.temp_c}°C",
            f"  Warning   : {self.warning or 'aucun'}",
            f"  Alarm     : {self.alarm or 'aucune'}",
            f"╚══════════════════════════════════════════════╝",
        ]
        return "\n".join(lines)


# ─── Classe principale ────────────────────────────────────────────────────────

class SPEExpert:
    """
    Interface série pour SPE Expert 1.3K-FA / 2K-FA.

    Exemple d'utilisation :
        amp = SPEExpert('COM4')          # Windows
        amp = SPEExpert('/dev/ttyUSB0')  # Linux
        with amp:
            status = amp.get_status()
            print(status)
    """

    RESPONSE_LEN = 75  # 3(sync) + 1(cnt) + 67(data) + 2(chk) + 2(CRLF)

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        self.port     = port
        self.baudrate = baudrate
        self.timeout  = timeout
        self._ser: Optional[serial.Serial] = None

    # ── Connexion ────────────────────────────────────────────────────────────

    def connect(self):
        self._ser = serial.Serial(
            port     = self.port,
            baudrate = self.baudrate,
            bytesize = serial.EIGHTBITS,
            parity   = serial.PARITY_NONE,
            stopbits = serial.STOPBITS_ONE,
            timeout  = self.timeout,
        )
        print(f"[SPE] Connecté sur {self.port} @ {self.baudrate} baud")

    def disconnect(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
            print("[SPE] Déconnecté")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    # ── Protocole bas niveau ─────────────────────────────────────────────────

    def _build_packet(self, cmd_byte: int) -> bytes:
        """Construit un paquet : 3×0x55 | CNT=1 | CMD | CHK"""
        return SYN_HOST + bytes([0x01, cmd_byte, cmd_byte])

    def _send(self, cmd_byte: int):
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Port série non ouvert")
        self._ser.flushInput()
        self._ser.write(self._build_packet(cmd_byte))

    def _read_response(self) -> Optional[bytes]:
        """Lit la réponse complète de l'ampli (jusqu'à RESPONSE_LEN bytes)."""
        raw = self._ser.read(self.RESPONSE_LEN)
        if len(raw) < 6:
            print(f"[SPE] Réponse trop courte ({len(raw)} bytes)")
            return None
        return raw

    def _find_sync(self, data: bytes) -> int:
        """Localise les 3 bytes de sync 0xAA dans le buffer."""
        for i in range(len(data) - 2):
            if data[i] == 0xAA and data[i+1] == 0xAA and data[i+2] == 0xAA:
                return i
        return -1

    def _verify_checksum(self, csv_bytes: bytes, chk0: int, chk1: int) -> bool:
        total = sum(csv_bytes)
        return (total % 256 == chk0) and (total // 256 == chk1)

    # ── Commandes publiques ───────────────────────────────────────────────────

    def send_key(self, key: str) -> bool:
        """
        Envoie une commande clavier et attend l'ACK.
        key : 'OPERATE', 'TUNE', 'BAND_UP', etc.
        Retourne True si ACK reçu correctement.
        """
        if key not in CMD:
            raise ValueError(f"Commande inconnue : {key}")
        cmd_byte = CMD[key]
        self._send(cmd_byte)
        raw = self._read_response()
        if raw is None:
            return False
        # ACK attendu : 0xAA 0xAA 0xAA 0x01 <cmd> <cmd>
        idx = self._find_sync(raw)
        if idx < 0:
            return False
        return raw[idx + 4] == cmd_byte

    def get_status(self) -> Optional[AmpStatus]:
        """
        Demande et parse la Status String (commande 0x90).
        Retourne un objet AmpStatus ou None en cas d'erreur.
        """
        self._send(CMD['STATUS'])
        raw = self._read_response()
        if raw is None:
            return None

        idx = self._find_sync(raw)
        if idx < 0:
            print("[SPE] Sync 0xAA introuvable")
            return None

        cnt = raw[idx + 3]
        payload = raw[idx + 4 : idx + 4 + cnt]

        if len(payload) < cnt:
            print(f"[SPE] Données incomplètes ({len(payload)}/{cnt})")
            return None

        chk0 = raw[idx + 4 + cnt]
        chk1 = raw[idx + 4 + cnt + 1]

        if not self._verify_checksum(payload, chk0, chk1):
            print("[SPE] Erreur checksum !")
            return None

        csv = payload.decode('ascii', errors='replace').strip()
        return self._parse_csv(csv)

    # ── Parsing CSV ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_csv(csv: str) -> Optional[AmpStatus]:
        """
        Parse la chaîne CSV 19 champs de la Status String.
        Exemple : '13K,S,R,A,1,00,1a,0r,L,0000, 0.00, 0.00, 0.0, 0.0, 33, 0, 0,N,N'
        """
        fields = [f.strip() for f in csv.split(',')]
        # La chaîne commence parfois par une virgule → champ vide en tête
        if fields and fields[0] == '':
            fields = fields[1:]
        if len(fields) < 19:
            print(f"[SPE] Nombre de champs inattendu : {len(fields)}")
            return None

        try:
            return AmpStatus(
                amp_id      = fields[0],
                mode        = 'Operate' if fields[1] == 'O' else 'Standby',
                rx_tx       = 'TX' if fields[2] == 'T' else 'RX',
                bank        = fields[3],
                input_port  = int(fields[4]),
                band        = BAND_MAP.get(fields[5], fields[5]),
                tx_ant      = fields[6],
                rx_ant      = fields[7],
                power_level = POWER_MAP.get(fields[8], fields[8]),
                out_power_w = int(fields[9]),
                swr_atu     = float(fields[10]),
                swr_ant     = float(fields[11]),
                vpa         = float(fields[12]),
                ipa         = float(fields[13]),
                temp_c      = int(fields[14]),
                warning     = WARNINGS.get(fields[17], fields[17]),
                alarm       = ALARMS.get(fields[18], fields[18]),
            )
        except (ValueError, IndexError) as e:
            print(f"[SPE] Erreur parsing : {e}  (csv={csv!r})")
            return None

    # ── Polling continu ───────────────────────────────────────────────────────

    def monitor(self, interval: float = 1.0, callback=None):
        """
        Polling périodique du statut.
        Si callback est fourni : callback(AmpStatus)
        Sinon : affichage console.
        Stopper avec Ctrl+C.
        """
        print(f"[SPE] Monitoring toutes les {interval}s — Ctrl+C pour arrêter")
        try:
            while True:
                status = self.get_status()
                if status:
                    if callback:
                        callback(status)
                    else:
                        print(status)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[SPE] Monitoring arrêté")


# ─── Test rapide ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    PORT = sys.argv[1] if len(sys.argv) > 1 else 'COM3'

    with SPEExpert(PORT, baudrate=115200) as amp:
        # Lire le statut une fois
        st = amp.get_status()
        if st:
            print(st)
        else:
            print("Pas de réponse — vérifie le port et que KTerm est fermé")