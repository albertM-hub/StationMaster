import os
import sys

# ── Fix matplotlib dans l'environnement PyInstaller (.exe) ──────────────────
# Doit être fait AVANT tout import de matplotlib
os.environ.setdefault('MPLBACKEND', 'TkAgg')
if getattr(sys, 'frozen', False):
    # On tourne dans un .exe PyInstaller
    _FROZEN_DIR = sys._MEIPASS
    os.environ['MATPLOTLIBDATA'] = os.path.join(_FROZEN_DIR, 'matplotlib', 'mpl-data')
    import matplotlib
    matplotlib.use('TkAgg')
# ─────────────────────────────────────────────────────────────────────────────

# Répertoire de l'application — fonctionne depuis n'importe quel dossier de lancement
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
from datetime import datetime, timezone
import socket
import threading
import requests
import xml.etree.ElementTree as ET
import math
import time
import traceback
from tkintermapview import TkinterMapView
import serial
import configparser
import shutil
import re
import struct
import io
import queue
try:
    import winsound
except ImportError:
    winsound = None

def _play_alert_sound(freq_hz=880, duration_ms=200):
    """Bip d'alerte cross-platform (Windows winsound / Linux paplay/aplay)."""
    if winsound:
        try: winsound.Beep(freq_hz, duration_ms); return
        except: pass
    import subprocess, shutil
    # Essai paplay (PulseAudio) avec un son système freedesktop
    for snd in ["/usr/share/sounds/freedesktop/stereo/bell.oga",
                "/usr/share/sounds/freedesktop/stereo/message.oga"]:
        if os.path.exists(snd) and shutil.which("paplay"):
            try: subprocess.Popen(["paplay", snd]); return
            except: pass
    # Fallback : aplay avec un son beep généré en mémoire
    if shutil.which("aplay"):
        try:
            import struct, math
            rate  = 8000
            n     = int(rate * duration_ms / 1000)
            data  = bytes([int(127 + 127 * math.sin(2 * math.pi * freq_hz * i / rate)) for i in range(n)])
            hdr   = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36 + len(data), b'WAVE',
                                b'fmt ', 16, 1, 1, rate, rate, 1, 8, b'data', len(data))
            proc  = subprocess.Popen(["aplay", "-q", "-"], stdin=subprocess.PIPE)
            proc.communicate(hdr + data)
            return
        except: pass

# Tentative import flex_client (Flex-6500)
try:
    from flex_client import FlexClient, RadioState
    _FLEX_OK = True
except ImportError:
    _FLEX_OK = False

# Tentative import win10toast (notifications Windows)
try:
    from win10toast import ToastNotifier
    _TOAST_OK = True
except ImportError:
    _TOAST_OK = False

# Tentative import PIL pour les photos QRZ
try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# ==========================================
# --- CONTINENT MAP ---
# ==========================================
CONTINENT_PREFIXES = {
    "ON":"EU","DL":"EU","F":"EU","G":"EU","I":"EU","PA":"EU","SP":"EU","OK":"EU",
    "HB":"EU","OE":"EU","OH":"EU","SM":"EU","LA":"EU","OZ":"EU","EA":"EU","CT":"EU",
    "YO":"EU","LZ":"EU","SV":"EU","HA":"EU","OM":"EU","9A":"EU","S5":"EU","YU":"EU",
    "UR":"EU","UT":"EU","UA":"EU","ES":"EU","YL":"EU","LY":"EU","TF":"EU","EI":"EU",
    "GI":"EU","GW":"EU","GM":"EU","LX":"EU","EW":"EU","OX":"EU","JW":"EU","OY":"EU",
    "IS":"EU","IT9":"EU","TA":"EU","5B":"EU","4O":"EU","Z3":"EU","ZA":"EU","E7":"EU",
    "GU":"EU","GJ":"EU","GD":"EU","C3":"EU","T7":"EU","3A":"EU","HV":"EU",
    "JA":"AS","HL":"AS","BY":"AS","BV":"AS","VU":"AS","HS":"AS","9V":"AS",
    "DU":"AS","YB":"AS","XV":"AS","XU":"AS","9M":"AS","UN":"AS","A4":"AS",
    "A7":"AS","A9":"AS","HZ":"AS","9K":"AS","4X":"AS","4Z":"AS","OD":"AS",
    "YK":"AS","EP":"AS","JT":"AS","UA9":"AS","EK":"AS","4J":"AS","UK":"AS",
    "EX":"AS","EY":"AS","EZ":"AS","AP":"AS","JY":"AS","YI":"AS","XW":"AS",
    "K":"NA","W":"NA","N":"NA","VE":"NA","XE":"NA","KH6":"NA","KL7":"NA",
    "KP4":"NA","VP9":"NA","TG":"NA","TI":"NA","HP":"NA","HH":"NA","HI":"NA",
    "6Y":"NA","ZF":"NA","V3":"NA","8P":"NA","PJ2":"NA","P4":"NA","CO":"NA",
    "HR":"NA","YS":"NA","KP2":"NA","VP2":"NA","VP5":"NA",
    "PY":"SA","LU":"SA","CE":"SA","YV":"SA","HK":"SA","OA":"SA","CP":"SA",
    "CX":"SA","HC":"SA","FY":"SA","ZP":"SA","9Y":"SA",
    "VK":"OC","ZL":"OC","3D2":"OC","T8":"OC","KH0":"OC","KH2":"OC","A3":"OC",
    "FO":"OC","FK":"OC","VK9":"OC","YJ":"OC","H4":"OC","P2":"OC","V6":"OC",
    "T2":"OC","KH1":"OC","E5":"OC","ZK1":"OC","ZK2":"OC","ZL7":"OC","ZL8":"OC",
    "ZS":"AF","7X":"AF","CN":"AF","SU":"AF","5Z":"AF","5A":"AF","ST":"AF",
    "ET":"AF","5N":"AF","9G":"AF","TU":"AF","6W":"AF","3V":"AF","EA8":"AF",
    "D2":"AF","V5":"AF","A2":"AF","Z2":"AF","9J":"AF","FR":"AF","5R":"AF",
    "TR":"AF","7Q":"AF","3B8":"AF","ZE":"AF","EL":"AF","TJ":"AF","TL":"AF",
    "TT":"AF","D4":"AF","3X":"AF","J5":"AF","S9":"AF","C9":"AF",
}
CONT_LABELS = {"EU":"Europe","AS":"Asie","NA":"N.Amér","SA":"S.Amér",
               "OC":"Océanie","AF":"Afrique","?":"?"}

def get_continent(callsign):
    """Retourne le continent (EU/AS/NA/SA/OC/AF) d'un indicatif."""
    if not callsign: return "?"
    c = callsign.upper().split("/")[0]
    for i in range(4, 0, -1):
        pfx = c[:i]
        if pfx in CONTINENT_PREFIXES:
            return CONTINENT_PREFIXES[pfx]
    return "?"

# --- GLOBALS ---
MY_GRID = "JO20SP"
MY_CALL = "ON5AM"
CAT_PORT = "COM4"
CAT_BAUD = 9600
CONF = None
BACKUP_DIR = "/home/albert/Bureau"  # Dossier de backup choisi par l'utilisateur

# ==========================================
# --- CONFIGURATION ---
# ==========================================
CONFIG_FILE = os.path.join(_APP_DIR, "config.ini")

def load_config_safe():
    global CONF, MY_GRID, MY_CALL, CAT_PORT, CAT_BAUD, BACKUP_DIR
    config = configparser.ConfigParser()
    DEFAULTS = {
        'USER': {'Callsign': 'ON5AM', 'Grid': 'JO20SP'},
        'CAT': {'Port': '/dev/ttyUSB0' if os.name != 'nt' else 'COM4', 'Baud': '9600'},
        'API': {'QRZ_User': 'ON5AM', 'QRZ_Pass': '', 'QRZ_Key': '', 'QRZ_Log_Key': '', 'EQSL_User': 'ON5AM', 'EQSL_Pass': '', 'Club_Email': '', 'Club_Pass': '', 'Club_Call': 'ON5AM', 'Club_Key': ''},
        'CLUSTER': {'Host': 'on0dxk.dyndns.org', 'Port': '8000', 'Call': 'ON5AM'},
        'DXCC': {'Alert_Bands': '20m,15m,10m', 'Alert_Countries': ''},
        'LOTW': {'Callsign': 'ON5AM', 'Tqsl_Path': 'tqsl' if os.name != 'nt' else 'C:\\Program Files (x86)\\TrustedQSL\\tqsl.exe', 'User': 'ON5AM', 'Pass': ''},
        'BACKUP': {'Dir': ''},
        'UDP': {'Source': 'wsjtx', 'WsjtxPort': '2237', 'MulticastIP': '224.0.0.1', 'GridtrackerPort': '2333'},
        'EMAIL': {'smtp_user': 'on5amplus@gmail.com', 'smtp_password': '',
                  'smtp_host': 'smtp.gmail.com', 'smtp_port': '587'},
    }
    try:
        if not os.path.exists(CONFIG_FILE):
            for section, content in DEFAULTS.items(): config[section] = content
            with open(CONFIG_FILE, 'w') as f: config.write(f)
        config.read(CONFIG_FILE)
        # Ajouter les sections manquantes avec leurs valeurs par défaut
        changed = False
        for section, keys in DEFAULTS.items():
            if not config.has_section(section):
                config[section] = keys; changed = True
            else:
                for key, val in keys.items():
                    if not config.has_option(section, key):
                        config.set(section, key, val); changed = True
        if changed:
            with open(CONFIG_FILE, 'w') as f: config.write(f)
        MY_GRID = config.get('USER', 'Grid', fallback='JO20SP')
        MY_CALL = config.get('USER', 'Callsign', fallback='ON5AM')
        CAT_PORT = config.get('CAT', 'Port', fallback='COM4')
        CAT_BAUD = config.getint('CAT', 'Baud', fallback=9600)
        BACKUP_DIR = config.get('BACKUP', 'Dir', fallback='')
        CONF = config
        return True
    except Exception as e:
        print(f"Config Error: {e}")
        return False

# ==========================================
# --- DXCC LOOKUP via CTY.DAT ---
# ==========================================
CTY_FILE = os.path.join(_APP_DIR, 'cty.dat')
CTY_URL  = 'https://www.country-files.com/cty/cty.dat'

_cty_prefixes = {}   # prefix -> country name
_cty_exact    = {}   # exact callsign -> country name
_cty_loaded   = False

def _download_cty():
    """Télécharge cty.dat depuis country-files.com."""
    try:
        r = requests.get(CTY_URL, timeout=20,
                         headers={'User-Agent': 'StationMaster/ON5AM'})
        r.raise_for_status()
        with open(CTY_FILE, 'w', encoding='utf-8') as f:
            f.write(r.text)
        print(f"[cty.dat] Téléchargé : {len(r.text)} octets")
        return True
    except Exception as e:
        print(f"[cty.dat] Téléchargement échoué : {e}")
        return False

def _parse_cty(path):
    """Parse cty.dat et retourne (prefixes_dict, exact_dict)."""
    prefixes = {}
    exact    = {}
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            text = f.read()
    except Exception as e:
        print(f"[cty.dat] Lecture échouée : {e}")
        return prefixes, exact

    # Chaque entrée se termine par ';'
    for record in text.split(';'):
        record = record.strip()
        if not record:
            continue
        lines = record.splitlines()
        # La ligne d'en-tête commence sans espace et contient ':'
        header = None
        alias_lines = []
        for i, line in enumerate(lines):
            if line and not line[0].isspace() and ':' in line:
                header = line
                alias_lines = lines[i + 1:]
                break
        if not header:
            continue
        parts = header.split(':')
        if len(parts) < 8:
            continue
        country = parts[0].strip()
        if not country:
            continue

        # Tous les alias (préfixes) de l'entrée
        alias_text = ' '.join(alias_lines)
        for token in alias_text.split(','):
            token = token.strip()
            if not token:
                continue
            # Supprimer les modificateurs : [15] {23} (EU) <lat/lon> ~
            clean = re.sub(r'[\[{(][^\]})]*[\]})]', '', token)
            clean = clean.replace('~', '').strip()
            if not clean:
                continue
            if clean.startswith('='):
                # Indicatif exact (ex: =W1AW)
                exact[clean[1:].upper()] = country
            else:
                prefixes[clean.upper()] = country

    print(f"[cty.dat] Parsé : {len(prefixes)} préfixes, {len(exact)} indicatifs exacts")
    return prefixes, exact

def _load_cty():
    """Charge cty.dat (télécharge si absent)."""
    global _cty_prefixes, _cty_exact, _cty_loaded
    if _cty_loaded:
        return
    if not os.path.exists(CTY_FILE):
        _download_cty()
    if os.path.exists(CTY_FILE):
        _cty_prefixes, _cty_exact = _parse_cty(CTY_FILE)
    _cty_loaded = True

def _prefix_lookup(call):
    """Recherche par plus long préfixe correspondant (max 6 caractères)."""
    for length in range(min(len(call), 6), 0, -1):
        country = _cty_prefixes.get(call[:length])
        if country:
            return country
    return ""

def get_country_name(callsign):
    """Retourne le nom du pays DXCC pour un indicatif via cty.dat."""
    if not callsign:
        return ""
    if not _cty_loaded:
        _load_cty()
    call = callsign.upper().strip()

    # Correspondance exacte (indicatifs spéciaux)
    if call in _cty_exact:
        return _cty_exact[call]

    # Indicatif portable : W1AW/VE3 ou DL1ABC/P
    parts = call.split('/')
    if len(parts) == 2:
        suffix = parts[1]
        # Si le suffixe ressemble à un préfixe pays (1-4 car), il prime
        if 1 <= len(suffix) <= 4 and not suffix.isdigit():
            res = _prefix_lookup(suffix)
            if res:
                return res

    # Recherche standard sur la partie principale
    return _prefix_lookup(parts[0]) or _prefix_lookup(call) or ""

# ==========================================
# --- FONCTIONS ---
# ==========================================
def grid_to_latlon(grid):
    if not grid or len(grid) < 4: return None
    grid = grid.upper().strip()
    try:
        lon = (ord(grid[0]) - 65) * 20 - 180; lat = (ord(grid[1]) - 65) * 10 - 90
        lon += (int(grid[2]) * 2); lat += (int(grid[3]) * 1)
        return (lat+0.5, lon+1)
    except: return None

def calculate_dist_bearing(grid1, grid2):
    try:
        loc1 = grid_to_latlon(grid1); loc2 = grid_to_latlon(grid2)
        if not loc1 or not loc2: return "", ""
        lat1, lon1 = map(math.radians, loc1); lat2, lon2 = map(math.radians, loc2)
        dlon = lon2 - lon1
        dist = 6371 * math.acos(min(1.0, math.sin(lat1)*math.sin(lat2) + math.cos(lat1)*math.cos(lat2)*math.cos(dlon)))
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
        bear = (math.degrees(math.atan2(y, x)) + 360) % 360
        return int(dist), int(bear)
    except: return "", ""

def freq_to_band(freq_str):
    try:
        f = float(freq_str)
        if f > 100000: f = f / 1000000
        if 1.8  <= f <= 2.0:   return "160m"
        if 3.5  <= f <= 4.0:   return "80m"
        if 5.3  <= f <= 5.41:  return "60m"
        if 7.0  <= f <= 7.3:   return "40m"
        if 10.1 <= f <= 10.15: return "30m"
        if 14.0 <= f <= 14.35: return "20m"
        if 18.068 <= f <= 18.168: return "17m"
        if 21.0 <= f <= 21.45: return "15m"
        if 24.89 <= f <= 24.99: return "12m"
        if 28.0 <= f <= 29.7:  return "10m"
        if 50.0 <= f <= 54.0:  return "6m"
        if 69.9 <= f <= 70.5:  return "4m"
        return "unknown"
    except: return "unknown"

def get_mode_from_freq(freq_str):
    try:
        f = float(freq_str); dec = f - int(f)
        if 0.074 <= dec <= 0.076 or 0.174 <= dec <= 0.176: return "FT8"
        if 0.040 <= dec <= 0.070: return "DIG"
        if dec < 0.040: return "CW"
        return "SSB"
    except: return "SSB"

def get_day_night_status():
    h = datetime.now(timezone.utc).hour
    if 7 <= h < 17: return "JOUR ☀️"
    elif 17 <= h < 19 or 5 <= h < 7: return "GRAYLINE 🌓"
    else: return "NUIT 🌙"

# ==========================================
# --- GREYLINE CALCULATION ---
# ==========================================
def calc_greyline():
    """Calcule la position approximative de la greyline (terminateur solaire)."""
    now = datetime.now(timezone.utc)
    day_of_year = now.timetuple().tm_yday
    # Déclinaison solaire
    decl = math.radians(23.45 * math.sin(math.radians(360/365 * (day_of_year - 81))))
    # Heure solaire
    hour_angle = (now.hour + now.minute/60 - 12) * 15  # degrés
    # Latitude du terminateur
    points = []
    for lon in range(-180, 181, 2):
        ha = math.radians(lon - hour_angle * (-1) + 180) 
        try:
            lat = math.degrees(math.atan(-math.cos(ha) / math.tan(decl)))
            points.append((lat, lon))
        except: pass
    return points

def get_solar_terminator_lats(n_points=180):
    """Retourne la latitude du terminateur solaire pour chaque longitude.
    
    Utilise la formule du terminateur solaire basée sur l'angle horaire.
    Retourne des valeurs clampées à [-85, 85] pour éviter les erreurs de projection.
    """
    now = datetime.now(timezone.utc)
    doy = now.timetuple().tm_yday
    decl = math.radians(-23.45 * math.cos(math.radians(360/365 * (doy + 10))))
    utc_h = now.hour + now.minute/60
    results = []
    for i in range(n_points):
        lon = -180 + i * (360 / n_points)
        ha = math.radians((utc_h * 15) + lon - 180)
        try:
            tan_decl = math.tan(decl)
            if abs(tan_decl) < 1e-9:
                lat = 0.0
            else:
                lat = math.degrees(math.atan2(-math.cos(ha), tan_decl))
            # Clamp entre -85 et 85 pour éviter les erreurs de projection cartographique
            lat = max(-85.0, min(85.0, lat))
            results.append((lat, lon))
        except:
            results.append((0, lon))
    return results


# ==========================================
# --- THREADS ---
# ==========================================
class RadioCAT(threading.Thread):
    def __init__(self, port, baud, callback_func):
        super().__init__(); self.port = port; self.baud = baud; self.callback = callback_func; self.running = True; self.ser = None
    
    def run(self):
        while self.running:
            try:
                if self.ser is None or not self.ser.is_open:
                    try: self.ser = serial.Serial(self.port, self.baud, timeout=0.5)
                    except: time.sleep(2); continue
                
                if self.ser and self.ser.is_open:
                    self.ser.write(b'FA;MD;SM0;IF;') 
                    while self.ser.in_waiting:
                        line = self.ser.read_until(b';').decode('utf-8', errors='ignore')
                        if line.startswith("FA"): self.callback("FREQ", line[2:].replace(';', ''))
                        elif line.startswith("MD"): 
                            modes = {"1":"LSB", "2":"USB", "3":"CW", "4":"FM", "5":"AM", "9":"DIG"}
                            self.callback("MODE", modes.get(line[2:3], "SSB"))
                        elif line.startswith("SM"):
                            try: self.callback("SMETER", int(line[2:].replace(';', '')))
                            except: pass
                        elif line.startswith("IF") and len(line) >= 30:
                            self.callback("TX_STATUS", (line[28] == '1'))
                time.sleep(0.2)
            except: 
                try: self.ser.close(); self.ser = None
                except: pass
                time.sleep(2)

    def set_freq(self, freq_hz):
        if self.ser and self.ser.is_open:
            try: self.ser.write(f"FA{str(int(freq_hz)).zfill(11)};".encode())
            except: pass

class ClusterThread(threading.Thread):
    """Thread connexion DX Cluster telnet — avec login automatique et source nommée."""
    def __init__(self, host, port, callsign, callback_spot, source="Cluster"):
        super().__init__()
        self.host = host; self.port = int(port); self.callsign = callsign
        self.callback = callback_spot; self.source = source
        self.running = True; self.daemon = True; self._sock = None

    def run(self):
        while self.running:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(20)
                self._sock.connect((self.host, self.port))
                self._sock.settimeout(2)
                buf = ""; logged = False
                while self.running:
                    try:
                        data = self._sock.recv(4096).decode("utf-8", errors="ignore")
                        if not data: break
                        buf += data
                        lines = buf.split("\n"); buf = lines[-1]
                        for line in lines[:-1]:
                            ll = line.lower()
                            if not logged and any(k in ll for k in ["login","call:","enter","your call"]):
                                time.sleep(0.5)
                                self._sock.send((self.callsign + "\r\n").encode())
                                time.sleep(1)
                                self._sock.send(b"set/dx\r\nset/noann\r\nset/nowx\r\n")
                                logged = True
                            if "DX de" in line:
                                try:
                                    parts = line.split()
                                    if len(parts) > 4:
                                        spotter = parts[2].replace(":", "")
                                        freq    = parts[3]
                                        dx_call = parts[4]
                                        time_z  = parts[-1]
                                        comment = " ".join(parts[5:-1]) if len(parts) > 5 else ""
                                        self.callback(freq, dx_call, comment, spotter, time_z, self.source)
                                except: pass
                    except socket.timeout: continue
                    except: break
            except Exception as e:
                print(f"[Cluster/{self.source}] {e}")
            finally:
                if self._sock:
                    try: self._sock.close()
                    except: pass
            if self.running: time.sleep(30)

    def stop(self):
        self.running = False
        if self._sock:
            try: self._sock.close()
            except: pass


class DXHeatThread(threading.Thread):
    """Récupère les spots DXHeat.com via leur API JSON."""
    def __init__(self, callback_spot, limit=30, refresh=60):
        super().__init__()
        self.callback = callback_spot; self.limit = limit
        self.refresh  = refresh; self.running = True
        self.daemon   = True; self._seen = set()

    def run(self):
        time.sleep(8)   # laisser le cluster principal se connecter d'abord
        while self.running:
            try:
                resp = requests.get(
                    f"https://dxheat.com/dxc/spots/?limit={self.limit}",
                    timeout=12, headers={"User-Agent": "StationMaster/ON5AM"})
                if resp.status_code == 200:
                    for s in resp.json():
                        freq = str(s.get("frequency", "0"))
                        t    = s.get("time", "")
                        uid  = f"{s.get('dx','')}_{freq}_{t}"
                        if uid in self._seen: continue
                        self._seen.add(uid)
                        comment = str(s.get("comment", ""))[:50]
                        time_z  = t[11:15] if len(t) > 15 else t[:5]
                        self.callback(freq,
                            str(s.get("dx","?")).upper().split("/")[0],
                            comment, str(s.get("spotter","?")).upper(),
                            time_z, "DXHeat")
                    if len(self._seen) > 2000:
                        self._seen = set(list(self._seen)[-500:])
            except Exception as e:
                print(f"[DXHeat] {e}")
            time.sleep(self.refresh)

    def stop(self): self.running = False


class SolarThread(threading.Thread):
    def __init__(self, callback):
        super().__init__(); self.callback = callback; self.running = True
    def run(self):
        while self.running:
            try:
                resp = requests.get("https://www.hamqsl.com/solarxml.php", timeout=10)
                root = ET.fromstring(resp.content); sol = root.find('solardata')
                self.callback(f"SFI: {sol.find('solarflux').text} | K: {sol.find('kindex').text} | A: {sol.find('aindex').text}")
            except: pass
            time.sleep(3600)

class PSKReporterThread(threading.Thread):
    """Récupère les spots PSK Reporter pour une station donnée."""
    def __init__(self, callsign, callback):
        super().__init__()
        self.callsign = callsign
        self.callback = callback
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            try:
                url = f"https://retrieve.pskreporter.info/query?receiverCallsign={self.callsign}&flowStartSeconds=-3600&statistics=0"
                resp = requests.get(url, timeout=15)
                root = ET.fromstring(resp.content)
                spots = []
                for rec in root.findall('.//receptionReport'):
                    sender   = rec.get('senderCallsign','')
                    freq_hz  = rec.get('frequency','0')
                    mode     = rec.get('mode','')
                    snr      = rec.get('sNR','')
                    rcv_call = rec.get('receiverCallsign','')
                    rcv_loc  = rec.get('receiverLocator','')
                    t_str    = rec.get('flowStartSeconds','')
                    try:
                        ts = datetime.fromtimestamp(int(t_str), tz=timezone.utc).strftime('%H:%M')
                    except:
                        ts = '--:--'
                    try:
                        freq_mhz = f"{int(freq_hz)/1e6:.3f}"
                    except:
                        freq_mhz = freq_hz
                    band = freq_to_band(freq_hz)
                    country = get_country_name(rcv_call)
                    spots.append((ts, sender, rcv_call, rcv_loc, freq_mhz, band, mode, snr, country))
                self.callback(spots)
            except Exception as e:
                print(f"PSKReporter error: {e}")
            time.sleep(300)  # Refresh toutes les 5 minutes


def _send_toast(title, msg):
    """Envoie une notification Windows si win10toast est disponible."""
    if _TOAST_OK:
        try:
            t = ToastNotifier()
            t.show_toast(title, msg, duration=6, threaded=True)
        except Exception as e:
            print(f"Toast error: {e}")


class QRZManager:
    """Accès à l'API XML QRZ.com — nécessite un abonnement QRZ."""
    QRZ_URL = "https://xmldata.qrz.com/xml/current/"

    def __init__(self, u, p, k):
        self.u = u; self.p = p; self.k = k
        self.session_key = k if k else None
        self._cache = {}

    def _login(self):
        try:
            r = requests.get(self.QRZ_URL,
                params={"username": self.u, "password": self.p, "agent": "StationMaster1.0"},
                timeout=10)
            root = ET.fromstring(r.content)
            ns = {'q': 'http://xmldata.qrz.com'}
            sess = root.find('q:Session', ns)
            if sess is not None:
                key_el = sess.find('q:Key', ns)
                err_el = sess.find('q:Error', ns)
                if key_el is not None:
                    self.session_key = key_el.text
                    return True
                if err_el is not None:
                    print(f"QRZ login error: {err_el.text}")
        except Exception as e:
            print(f"QRZ login exception: {e}")
        return False

    def get_info(self, callsign):
        if not callsign: return None
        if callsign in self._cache: return self._cache[callsign]
        if not self.session_key:
            if not self._login(): return None
        info = self._fetch(callsign)
        if info is None and self._login():
            info = self._fetch(callsign)
        if info:
            self._cache[callsign] = info
        return info

    def _fetch(self, callsign):
        try:
            r = requests.get(self.QRZ_URL,
                params={"s": self.session_key, "callsign": callsign},
                timeout=10)
            root = ET.fromstring(r.content)
            ns = {'q': 'http://xmldata.qrz.com'}
            cs = root.find('q:Callsign', ns)
            if cs is None: return None

            def t(tag): el = cs.find(f'q:{tag}', ns); return el.text.strip() if el is not None and el.text else ""

            fname = t('fname'); lname = t('lname')
            name  = f"{fname} {lname}".strip() or t('name')

            return {
                'name':     name,
                'fname':    fname,
                'lname':    lname,
                'call':     t('call'),
                'city':     t('addr2'),
                'state':    t('state'),
                'country':  t('country'),
                'grid':     t('grid'),
                'email':    t('email'),
                'born':     t('born'),
                'lic_class':t('class'),
                'efdate':   t('efdate'),
                'expdate':  t('expdate'),
                'addr1':    t('addr1'),
                'zip':      t('zip'),
                'land':     t('land'),
                'image':    t('image'),
                'bio':      t('bio'),
                'qslmgr':   t('qslmgr'),
                'aliases':  t('aliases'),
                'lotw':     t('lotw'),
                'eqsl':     t('eqsl'),
            }
        except Exception as e:
            print(f"QRZ fetch error: {e}")
            return None

    def upload_qso(self, d): return False

class EQSLManager:
    """Upload QSO vers eQSL.cc et vérifie les confirmations reçues."""
    UPLOAD_URL = "https://www.eqsl.cc/qslcard/ImportADIF.cfm"
    INBOX_URL  = "https://www.eqsl.cc/qslcard/DownloadInBox.txt"

    def __init__(self, u, p):
        self.u = u; self.p = p

    def _qso_to_adif(self, d):
        """Construit un enregistrement ADIF minimal depuis le tuple QSO."""
        date, time_, call, band, mode = d[0], d[1], d[2], d[3], d[4]
        rst_s, rst_r = d[5], d[6]
        date_adif = date.replace("-","")
        time_adif = time_.replace(":","")[:4]
        mode_adif = "FT8" if "FT8" in mode.upper() else \
                    "FT4" if "FT4" in mode.upper() else \
                    "MFSK" if "MFSK" in mode.upper() else mode.upper()
        adif = (f"<CALL:{len(call)}>{call}"
                f"<BAND:{len(band)}>{band}"
                f"<MODE:{len(mode_adif)}>{mode_adif}"
                f"<QSO_DATE:{len(date_adif)}>{date_adif}"
                f"<TIME_ON:{len(time_adif)}>{time_adif}"
                f"<RST_SENT:{len(str(rst_s))}>{rst_s}"
                f"<RST_RCVD:{len(str(rst_r))}>{rst_r}"
                f"<EOR>")
        return adif

    def upload_qso(self, d):
        if not self.u or not self.p: return False
        try:
            adif = self._qso_to_adif(d)
            r = requests.get(self.UPLOAD_URL,
                params={"ADIFData": adif, "EQSL_USER": self.u, "EQSL_PSWD": self.p},
                timeout=15)
            ok = "result" in r.text.lower() and "error" not in r.text.lower()
            print(f"[eQSL] upload {d[2]}: {'✅' if ok else '❌'} {r.text[:80]}")
            return ok
        except Exception as e:
            print(f"[eQSL] upload error: {e}"); return False

    def check_incoming(self, since_date=""):
        """Récupère les QSL reçues dans la boîte eQSL."""
        if not self.u or not self.p: return []
        try:
            params = {"U": self.u, "P": self.p, "ConfirmedOnly": "Y",
                      "HamID": self.u}
            if since_date:
                params["RcvdSince"] = since_date
            r = requests.get(self.INBOX_URL, params=params, timeout=20)
            # Parse ADIF response
            confirmed = []
            for m in re.finditer(r'<CALL:(\d+)>([^<]+).*?<BAND:(\d+)>([^<]+).*?<MODE:(\d+)>([^<]+).*?<QSO_DATE:(\d+)>([^<]+)',
                                  r.text, re.DOTALL):
                confirmed.append({
                    'call': m.group(2).strip(),
                    'band': m.group(4).strip(),
                    'mode': m.group(6).strip(),
                    'date': m.group(8).strip(),
                })
            print(f"[eQSL] {len(confirmed)} confirmations reçues")
            return confirmed
        except Exception as e:
            print(f"[eQSL] check error: {e}"); return []


class QRZLogbookManager:
    """Upload QSO vers QRZ.com logbook via API ADIF."""
    API_URL = "https://logbook.qrz.com/api"

    def __init__(self, api_key):
        self.key = api_key

    def upload_qso(self, d):
        if not self.key: return False
        try:
            date, time_, call, band, mode = d[0], d[1], d[2], d[3], d[4]
            rst_s, rst_r = d[5], d[6]
            date_adif = date.replace("-","")
            time_adif = time_.replace(":","")[:4]
            adif = (f"<CALL:{len(call)}>{call}"
                    f"<BAND:{len(band)}>{band}"
                    f"<MODE:{len(mode)}>{mode}"
                    f"<QSO_DATE:{len(date_adif)}>{date_adif}"
                    f"<TIME_ON:{len(time_adif)}>{time_adif}"
                    f"<RST_SENT:{len(str(rst_s))}>{rst_s}"
                    f"<RST_RCVD:{len(str(rst_r))}>{rst_r}"
                    f"<STATION_CALLSIGN:5>ON5AM<EOR>")
            r = requests.post(self.API_URL,
                data={"KEY": self.key, "ACTION": "INSERT", "ADIF": adif},
                timeout=15)
            ok = "STATUS=OK" in r.text or "LOGID" in r.text
            print(f"[QRZ] upload {call}: {'✅' if ok else '❌'} {r.text[:80]}")
            return ok
        except Exception as e:
            print(f"[QRZ] upload error: {e}"); return False

    def check_incoming(self, call="ON5AM"):
        """Vérifie les QSL reçues sur le logbook QRZ."""
        if not self.key: return []
        try:
            r = requests.post(self.API_URL,
                data={"KEY": self.key, "ACTION": "FETCH", "OPTION": "TYPE:RECV"},
                timeout=20)
            confirmed = []
            for m in re.finditer(r'<CALL:(\d+)>([^<]+).*?<BAND:(\d+)>([^<]+).*?<QSO_DATE:(\d+)>([^<]+)',
                                  r.text, re.DOTALL):
                confirmed.append({'call': m.group(2).strip(),
                                   'band': m.group(4).strip(),
                                   'date': m.group(6).strip()})
            print(f"[QRZ] {len(confirmed)} QSL reçues")
            return confirmed
        except Exception as e:
            print(f"[QRZ] check error: {e}"); return []


class ClubLogManager:
    """Upload QSO vers Club Log via API REST."""
    API_URL = "https://clublog.org/realtime.php"

    def __init__(self, e, p, c, k=""):
        self.email = e; self.p = p; self.call = c; self.key = k

    def upload_qso(self, d):
        if not self.email or not self.p: return False
        try:
            date, time_, call, band, mode = d[0], d[1], d[2], d[3], d[4]
            rst_s, rst_r = d[5], d[6]
            date_adif = date.replace("-","")
            time_adif = time_.replace(":","")[:4]
            band_up = band.upper()   # Club Log attend le format ADIF majuscule (ex: 20M)
            adif = (f"<CALL:{len(call)}>{call}"
                    f"<BAND:{len(band_up)}>{band_up}"
                    f"<MODE:{len(mode)}>{mode}"
                    f"<QSO_DATE:{len(date_adif)}>{date_adif}"
                    f"<TIME_ON:{len(time_adif)}>{time_adif}"
                    f"<RST_SENT:{len(str(rst_s))}>{rst_s}"
                    f"<RST_RCVD:{len(str(rst_r))}>{rst_r}"
                    f"<EOR>")
            payload = {"email": self.email, "password": self.p,
                       "callsign": self.call, "adif": adif}
            if self.key:
                payload["api"] = self.key
            headers = {"User-Agent": "StationMaster/1.0 (ON5AM)"}
            print(f"[ClubLog] envoi → callsign={self.call}  email={self.email}  adif={adif}")
            r = requests.post(self.API_URL, data=payload, headers=headers, timeout=15)
            ok = r.status_code == 200 and "error" not in r.text.lower()
            print(f"[ClubLog] HTTP {r.status_code} | réponse complète : {r.text}")
            return ok
        except Exception as e:
            print(f"[ClubLog] upload error: {e}"); return False

class WSJTXPacket:
    """Décodeur de paquets UDP WSJT-X (protocole binaire Qt).
    
    Message type 5 (QSOLogged) :
      Id(str) | DateTimeOff(QDateTime:13B) | DxCall(str) | DxGrid(str)
      | TxFrequency(u64) | Mode(str) | RST_sent(str) | RST_rcvd(str)
      | TxPower(str) | Comments(str) | Name(str) | DateTimeOn(13B)
      | OperatorCall(str) | MyCall(str) | MyGrid(str) | ...
    """
    MAGIC = 0xADBCCBDA

    def __init__(self, d):
        self.d = d; self.cursor = 0
        try:
            self.magic = self.read_u32()
            self.schema = self.read_u32()
            self.msg_type = self.read_u32()
        except: self.msg_type = 0xff

    def read_u8(self):
        v = self.d[self.cursor]; self.cursor += 1; return v

    def read_u32(self):
        v = struct.unpack('>I', self.d[self.cursor:self.cursor+4])[0]; self.cursor += 4; return v

    def read_u64(self):
        v = struct.unpack('>Q', self.d[self.cursor:self.cursor+8])[0]; self.cursor += 8; return v

    def read_str(self):
        """Lit une string Qt (u32 length-prefix). 0xFFFFFFFF = null string."""
        l = self.read_u32()
        if l == 0: return ""
        if l == 0xFFFFFFFF: return ""   # Qt null string
        if l > 500: self.cursor += min(l, len(self.d) - self.cursor); return ""
        s = self.d[self.cursor:self.cursor+l].decode('utf-8', errors='ignore')
        self.cursor += l; return s

    def read_qdatetime(self):
            self.cursor += 8   # julian day ms (u64)
            ts = self.read_u8()
            if ts == 2:
                self.cursor += 4   # offset en secondes
            elif ts == 3:
                # timezone : u32 (IANAId length) + bytes + u8 (nameType) + u32 (offsetSeconds)
                l = struct.unpack('>I', self.d[self.cursor:self.cursor+4])[0]
                self.cursor += 4
                if l < 500:
                    self.cursor += l   # IANA timezone string
                self.cursor += 1   # nameType (u8)
                self.cursor += 4   # offsetFromUtc (i32)
            return 0

    def read_bool(self):
        v = self.d[self.cursor]; self.cursor += 1; return bool(v)

# ==========================================
# --- APP PRINCIPALE ---
# ==========================================
class StationMasterApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{MY_CALL} Station Master V21.0")
        # File thread-safe pour les callbacks tkinter depuis des threads bg (Python 3.14+)
        self._tk_queue = queue.Queue()
        self.root.after(100, self._process_tk_queue)
        # Charger cty.dat en arrière-plan dès le démarrage
        threading.Thread(target=_load_cty, daemon=True).start()
        self.root.geometry("1700x980")

        # ══════════════════════════════════════════════════════════════════════
        # THÈME GLOBAL — Forcer #11273f sur TOUS les widgets
        # Appliqué en deux passes : immédiat + différé (after 1ms)
        # car ttkbootstrap ré-applique son thème après __init__
        # ══════════════════════════════════════════════════════════════════════
        BG  = "#11273f"
        BG2 = "#0a1e35"
        FG  = "white"
        self._BG = BG  # garder pour usage dans les méthodes

        def _apply_theme():
            """Applique #11273f sur tous les widgets ttk et tk."""
            s = ttk.Style()
            # ── Patcher les couleurs du thème ttkbootstrap directement ───────
            try:
                s.theme_use(s.theme_use())  # re-activer le thème courant
                # Patcher via configure sur le style racine "."
                s.configure(".", background=BG, foreground=FG,
                             troughcolor=BG2, fieldbackground=BG,
                             selectbackground="#1a5276", selectforeground=FG,
                             insertcolor=FG)
            except: pass

            # ── Tous les widgets ttk ─────────────────────────────────────────
            for w in ("TFrame", "TLabelframe", "TLabelframe.Label",
                      "TNotebook", "TNotebook.Tab",
                      "TLabel", "TEntry", "TCombobox", "TSpinbox",
                      "TScrollbar", "TPanedwindow", "TMenubutton",
                      "TCheckbutton", "TRadiobutton", "TSeparator",
                      "TButton"):
                try: s.configure(w, background=BG, foreground=FG)
                except: pass

            # ── Treeview ─────────────────────────────────────────────────────
            for tv in ("Treeview", "Custom.Treeview"):
                s.configure(tv, background=BG, fieldbackground=BG,
                            foreground=FG, rowheight=22, borderwidth=0)
                s.map(tv,
                    background=[("selected", "#1a5276")],
                    foreground=[("selected", FG)])
            for tv in ("Treeview.Heading", "Custom.Treeview.Heading",
                       "Cluster.Treeview.Heading"):
                try:
                    s.configure(tv, background="#1a3a5c", foreground="#f39c12",
                                font=("Arial", 9, "bold"), relief="flat")
                except: pass
            s.configure("Cluster.Treeview", background=BG,
                        fieldbackground=BG, foreground=FG,
                        rowheight=25, font=("Arial", 10))

            # ── Variantes bootstyle (info, success, warning…) ────────────────
            for variant in ("info", "success", "warning", "danger",
                            "primary", "secondary", "light", "dark"):
                for suffix in ("Treeview", "Treeview.Heading"):
                    try:
                        s.configure(f"{variant}.{suffix}",
                            background=BG, fieldbackground=BG, foreground=FG)
                    except: pass

            # ── Progressbar ──────────────────────────────────────────────────
            s.configure("TProgressbar", background="#3498db",
                        troughcolor=BG2, borderwidth=0)

            # ── option_add pour les widgets tk classiques ────────────────────
            self.root.option_add("*Background",       BG,  "userDefault")
            self.root.option_add("*background",       BG,  "userDefault")
            self.root.option_add("*Foreground",       FG,  "userDefault")
            self.root.option_add("*foreground",       FG,  "userDefault")
            self.root.option_add("*selectBackground", "#1a5276", "userDefault")
            self.root.option_add("*selectForeground", FG,  "userDefault")
            self.root.option_add("*insertBackground", FG,  "userDefault")

            # ── Forcer bg sur tous les widgets tk déjà créés ────────────────
            def _force_bg(widget):
                try:
                    wclass = widget.winfo_class()
                    if wclass in ("Frame", "Label", "Canvas", "Listbox", "Text"):
                        widget.configure(bg=BG)
                    if wclass in ("Label",):
                        widget.configure(fg=FG)
                except: pass
                for child in widget.winfo_children():
                    _force_bg(child)
            _force_bg(self.root)

        # Appliquer immédiatement ET après 1ms (pour survivre à ttkbootstrap)
        _apply_theme()
        self.root.after(1, _apply_theme)
        self.root.after(500, _apply_theme)  # 2ème passe de sécurité
        # ══════════════════════════════════════════════════════════════════════
        
        self.home_marker = None; self.dx_marker = None; self.path_line = None
        self.current_manual_grid = ""; self.current_freq_hz = "14200000"
        self._all_spots = []  # buffer spots cluster (liste de dicts)
        # Stats session cluster
        self._cluster_session_start     = datetime.now(timezone.utc)
        self._cluster_session_countries = set()
        self._cluster_session_count     = 0
        # Client Flex-6500
        self._flex_client = None

        self.status_var = ttk.StringVar(value=f"Station Prête - {MY_GRID}")
        self.solar_var = ttk.StringVar(value="SFI: --")
        self.utc_time_var = ttk.StringVar(value="00:00:00 UTC")

        # Filtres cluster
        self._cluster_alert_bands     = set()
        self._cluster_alert_countries = set()
        self._cluster_watchlist       = set()
        self._load_cluster_filters()

        self.qrz = QRZManager("","",""); self.eqsl = EQSLManager("","")
        self.qrz_log = QRZLogbookManager(""); self.club = ClubLogManager("","","")
        if CONF:
            self.qrz     = QRZManager(CONF['API']['qrz_user'], CONF['API']['qrz_pass'], CONF['API']['qrz_key'])
            self.eqsl    = EQSLManager(CONF['API']['eqsl_user'], CONF['API']['eqsl_pass'])
            self.qrz_log = QRZLogbookManager(CONF['API'].get('qrz_log_key',''))
            self.club    = ClubLogManager(CONF['API']['club_email'], CONF['API']['club_pass'],
                                          CONF['API']['club_call'], CONF['API']['club_key'])
        
        # Migration automatique : renommer l'ancien fichier si nécessaire
        _db_path = os.path.join(_APP_DIR, 'station_master.db')
        _old_db  = os.path.join(_APP_DIR, 'mon_logbook.db')
        if not os.path.exists(_db_path) and os.path.exists(_old_db):
            os.rename(_old_db, _db_path)
        self.conn = sqlite3.connect(_db_path, check_same_thread=False)
        self.create_table()

        # Charger la config UDP
        self._udp_source      = "wsjtx"       # wsjtx | gridtracker | les_deux
        self._udp_wsjtx_port  = 2237
        self._udp_mcast_ip    = "224.0.0.1"
        self._udp_gt_port     = 2333
        self._load_udp_config()
        self._load_spe_config()

        self.setup_ui()
        try: self.load_data()
        except: pass
        self.update_clock()

        self._start_udp_threads()
        
        self.cat = RadioCAT(CAT_PORT, CAT_BAUD, self.update_radio_info)
        self.cat.daemon = True; self.cat.start()
        
        if CONF:
            self.cluster = ClusterThread(CONF['CLUSTER']['Host'], CONF['CLUSTER']['Port'], CONF['CLUSTER']['Call'], self.on_cluster_spot, source="Cluster")
            self.cluster.daemon = True; self.cluster.start()
            self._dxheat = DXHeatThread(self.on_cluster_spot)
            self._dxheat.start()
        
        sol_t = SolarThread(lambda d: self.solar_var.set(d)); sol_t.daemon = True; sol_t.start()

        # PSK Reporter thread
        self._psk_spots = []
        self._psk_thread = PSKReporterThread(MY_CALL, self._on_psk_spots)
        self._psk_thread.start()

        # Variables dashboard (mise à jour périodique)
        self.root.after(2000, self._refresh_dashboard)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_cluster_filters(self):
        if CONF:
            bands_str = CONF.get('DXCC', 'Alert_Bands', fallback='')
            countries_str = CONF.get('DXCC', 'Alert_Countries', fallback='')
            watchlist_str = CONF.get('DXCC', 'Watchlist', fallback='')
            self._cluster_alert_bands     = set(b.strip().lower() for b in bands_str.split(',') if b.strip())
            self._cluster_alert_countries = set(c.strip().lower() for c in countries_str.split(',') if c.strip())
            self._cluster_watchlist       = set(w.strip().upper() for w in watchlist_str.split(',') if w.strip())

    def _load_udp_config(self):
        """Lit la configuration UDP depuis config.ini."""
        if CONF:
            self._udp_source     = CONF.get('UDP', 'Source',         fallback='wsjtx').strip().lower()
            self._udp_wsjtx_port = int(CONF.get('UDP', 'WsjtxPort',    fallback='2237'))
            self._udp_mcast_ip   = CONF.get('UDP', 'MulticastIP',    fallback='224.0.0.1').strip()
            self._udp_gt_port    = int(CONF.get('UDP', 'GridtrackerPort', fallback='2333'))
        print(f"UDP config: source={self._udp_source}  "
              f"wsjtx_port={self._udp_wsjtx_port}  "
              f"gt_port={self._udp_gt_port}")

    def _on_close(self):
        """Arrête les threads background avant de fermer la fenêtre."""
        try:
            if self._spe_tab is not None:
                self._spe_tab.stop()
        except Exception:
            pass
        self.root.destroy()

    def _load_spe_config(self):
        """Lit le port et baudrate SPE Expert depuis config.ini."""
        self._spe_port = "/dev/ttyUSB1"
        self._spe_baud = 115200
        if CONF and CONF.has_section("SPE"):
            self._spe_port = CONF.get("SPE", "port",     fallback="/dev/ttyUSB1").strip()
            self._spe_baud = int(CONF.get("SPE", "baudrate", fallback="115200"))

    def _start_udp_threads(self):
        """Démarre les threads UDP selon la source configurée."""
        src = self._udp_source
        if src in ("wsjtx", "les_deux"):
            threading.Thread(target=self.udp_listener, daemon=True).start()
        if src in ("gridtracker", "les_deux"):
            threading.Thread(target=self.adif_broadcast_listener, daemon=True).start()
        # Afficher la config dans la barre de statut au démarrage
        labels = {"wsjtx": f"WSJT-X UDP port {self._udp_wsjtx_port}",
                  "gridtracker": f"GridTracker ADIF port {self._udp_gt_port}",
                  "les_deux": f"WSJT-X:{self._udp_wsjtx_port} + GridTracker:{self._udp_gt_port}"}
        self.root.after(2500, lambda: self.lbl_data.config(
            text=f"RX: {labels.get(src, src)}", foreground="#3daee9"))

    def _reload_udp_config(self):
        """Relit la config UDP (après sauvegarde des paramètres).
        Affiche un message — le redémarrage est nécessaire pour changer le port actif."""
        self._load_udp_config()
        src = self._udp_source
        labels = {"wsjtx": f"WSJT-X port {self._udp_wsjtx_port}",
                  "gridtracker": f"GridTracker port {self._udp_gt_port}",
                  "les_deux": f"Les deux (WSJT-X:{self._udp_wsjtx_port} + GT:{self._udp_gt_port})"}
        self.status_var.set(
            f"✅ Config UDP: {labels.get(src, src)} — Redémarrez pour activer le nouveau port.")

    def create_table(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS qsos (id INTEGER PRIMARY KEY AUTOINCREMENT, qso_date TEXT, time_on TEXT, callsign TEXT, band TEXT, mode TEXT, rst_sent TEXT, rst_rcvd TEXT, name TEXT, qth TEXT, qsl_sent TEXT, qsl_rcvd TEXT, distance TEXT, grid TEXT, freq TEXT, qrz_stat TEXT, eqsl_stat TEXT, lotw_stat TEXT, club_stat TEXT, comment TEXT)''')
        for col in ["distance", "grid", "freq", "qrz_stat", "eqsl_stat", "lotw_stat", "club_stat", "comment"]:
            try: c.execute(f"ALTER TABLE qsos ADD COLUMN {col} TEXT"); self.conn.commit()
            except: pass
        # Table DXCC confirmations
        c.execute('''CREATE TABLE IF NOT EXISTS dxcc_confirmed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity TEXT NOT NULL,
            band TEXT DEFAULT '',
            mode TEXT DEFAULT '',
            confirmed INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            UNIQUE(entity, band, mode)
        )''')
        self.conn.commit()

    def _process_tk_queue(self):
        """Exécute les callbacks postés depuis des threads bg — thread-safe Python 3.14."""
        try:
            while True:
                cb = self._tk_queue.get_nowait()
                cb()
        except queue.Empty:
            pass
        self.root.after(50, self._process_tk_queue)

    def update_clock(self):
        self.utc_time_var.set(datetime.now(timezone.utc).strftime('%H:%M:%S UTC'))
        self.root.after(1000, self.update_clock)

    # ==========================================
    # --- SETUP UI ---
    # ==========================================
    def setup_ui(self):
        top = ttk.Frame(self.root, padding=10, bootstyle="dark"); top.pack(fill="x")
        f_left = ttk.Frame(top, bootstyle="dark"); f_left.pack(side="left")
        ttk.Label(f_left, text=f"{MY_CALL} STATION MASTER", font=("Consolas", 22, "bold"), bootstyle="inverse-dark").pack(side="left")
        
        f_radio = ttk.Frame(top, bootstyle="dark", padding=(20,0)); f_radio.pack(side="left", padx=20)
        self.lbl_radio = ttk.Label(f_radio, text="RADIO OFF", font=("Consolas", 16, "bold"), bootstyle="danger-inverse", padding=5)
        self.lbl_radio.pack(side="top", pady=2)
        # pb_smeter : stub caché pour compatibilité update_radio_info
        self.pb_smeter = ttk.Progressbar(f_radio, value=0, maximum=30, length=1)
        
        f_info = ttk.Frame(top, bootstyle="dark", padding=20); f_info.pack(side="left")
        ttk.Label(f_info, textvariable=self.utc_time_var, font=("Consolas", 18, "bold"), foreground="white").pack(side="top")
        dn = get_day_night_status()
        ttk.Label(f_info, text=f"{dn} | ", font=("Arial", 10), foreground="#3daee9").pack(side="left")
        ttk.Label(f_info, textvariable=self.solar_var, font=("Arial", 10), foreground="#f39c12").pack(side="left")
        
        self.lbl_data = ttk.Label(top, text="RX DATA", font=("Consolas", 8), foreground="#3daee9")
        self.lbl_data.pack(side="right", padx=5)

        btn_fr = ttk.Frame(top, bootstyle="dark"); btn_fr.pack(side="right")
        ttk.Button(btn_fr, text="⚙️ Paramètres", command=self.open_settings, bootstyle="secondary").pack(side="right", padx=5)
        ttk.Button(btn_fr, text="❌ Quitter", command=self.confirm_quit, bootstyle="danger").pack(side="right", padx=5)
        ttk.Button(btn_fr, text="💾 Backup", command=self.do_backup, bootstyle="success").pack(side="right", padx=5)
        ttk.Button(btn_fr, text="📂 Import", command=self.import_adif, bootstyle="info-outline").pack(side="right", padx=5)

        mid = ttk.Frame(self.root); mid.pack(fill="x", padx=10, pady=5)
        ins = ttk.Labelframe(mid, text="Nouveau Contact", padding=10, bootstyle="secondary")
        ins.pack(side="left", fill="x", expand=True)
        f1 = ttk.Frame(ins); f1.pack(fill="x")
        self.e_call = ttk.Entry(f1, font=("Consolas", 12, "bold"), width=10); self.e_call.pack(side="left", padx=5)
        self.e_call.bind("<KeyRelease>", self._check_duplicate)
        ttk.Button(f1, text="🔍", command=self.manual_lookup, bootstyle="warning", width=3).pack(side="left")
        self.e_name = ttk.Entry(f1, width=15); self.e_name.pack(side="left", padx=5)
        self.e_mode = ttk.Entry(f1, width=6); self.e_mode.insert(0,"SSB"); self.e_mode.pack(side="left", padx=5)
        self.e_rst_s = ttk.Entry(f1, width=4); self.e_rst_s.insert(0,"59"); self.e_rst_s.pack(side="left", padx=2)
        self.e_rst_r = ttk.Entry(f1, width=4); self.e_rst_r.insert(0,"59"); self.e_rst_r.pack(side="left", padx=2)
        ttk.Label(f1, text="Com:").pack(side="left", padx=2)
        self.e_comment = ttk.Entry(f1, width=15); self.e_comment.pack(side="left", padx=2)
        ttk.Button(f1, text="💾 SAVE", command=self.add_manual_qso, bootstyle="success").pack(side="right", padx=10)
        # Indicateur doublon (ligne 2)
        f2 = ttk.Frame(ins); f2.pack(fill="x", pady=(2,0))
        self.lbl_dup = ttk.Label(f2, text="", font=("Consolas", 9))
        self.lbl_dup.pack(side="left", padx=5)

        sf = ttk.Labelframe(mid, text="Recherche", padding=10, bootstyle="secondary"); sf.pack(side="right", padx=10)
        self.e_s = ttk.Entry(sf, width=12); self.e_s.pack(side="left", padx=5)
        self.e_s.bind("<KeyRelease>", lambda e: self.load_data(self.e_s.get()))
        self.cb_band = ttk.Combobox(sf, values=["All","160m","80m","60m","40m","30m","20m","17m","15m","12m","10m","6m"], width=5)
        self.cb_band.set("All"); self.cb_band.pack(side="left", padx=2)
        self.cb_band.bind("<<ComboboxSelected>>", lambda e: self.load_data())
        self.cb_mode = ttk.Combobox(sf, values=["All","SSB","CW","FT8","FT4","DIG"], width=5)
        self.cb_mode.set("All"); self.cb_mode.pack(side="left", padx=2)
        self.cb_mode.bind("<<ComboboxSelected>>", lambda e: self.load_data())
        ttk.Button(sf, text="X", command=lambda:[self.e_s.delete(0,tk.END), self.cb_band.set("All"), self.cb_mode.set("All"), self.load_data()], width=2).pack(side="left")
        ttk.Button(sf, text="🔎 Avancée", command=self._open_advanced_search,
                   bootstyle="warning-outline", width=10).pack(side="left", padx=5)

        self.nb = ttk.Notebook(self.root); self.nb.pack(fill="both", expand=True, padx=10, pady=5)

        # --- Onglet Dashboard ---
        BG = "#11273f"
        t_dash = tk.Frame(self.nb, bg=BG); self.nb.add(t_dash, text="🏠 Dashboard")
        self._build_dashboard_tab(t_dash)

        # --- Onglet Flex-6500 ---
        t_flex = tk.Frame(self.nb, bg=BG); self.nb.add(t_flex, text="📻 Flex-6500")
        self._build_flex_tab(t_flex)

        # --- Onglet SPE Expert ---
        self._spe_tab = None
        try:
            from tab_spe_expert import SPEExpertTab
            t_spe = tk.Frame(self.nb, bg=BG)
            self.nb.add(t_spe, text="⚡ SPE")
            self._spe_tab = SPEExpertTab(t_spe, app=self,
                                         port=self._spe_port,
                                         baudrate=self._spe_baud)
        except Exception as _e:
            print(f"[SPEExpertTab] Import échoué : {_e}")

        # --- Onglet FT8 Live Monitor ---
        self._ft8_monitor = None
        try:
            from tab_ft8_monitor import FT8MonitorTab
            t_ft8 = tk.Frame(self.nb, bg=BG)
            self.nb.add(t_ft8, text="📡 FT8 Live")
            self._ft8_monitor = FT8MonitorTab(t_ft8, app=self, my_call=MY_CALL,
                                              get_country=get_country_name)
            self.root.after(3000, self._ft8_monitor.load_recent_qsos)
        except Exception as _e:
            print(f"[FT8Monitor] Import échoué: {_e}")

        # --- Onglet Propagation ---
        t_prop = tk.Frame(self.nb, bg=BG); self.nb.add(t_prop, text="🌐 Propagation")
        self._build_propagation_tab(t_prop)

        # --- Initialisation QSLEmailer (utilisé par la barre Journal) ---
        try:
            from tab_qsl import QSLEmailer
            self._qsl_emailer = QSLEmailer(self)
        except Exception as _qe:
            self._qsl_emailer = None
            print(f"[QSLEmailer] Import échoué : {_qe}")

        # --- Onglet Journal ---
        t_log = tk.Frame(self.nb, bg=BG); self.nb.add(t_log, text="🔴 Journal")
        try:
            self.nb.tab(t_log, foreground="red")
        except tk.TclError:
            pass  # ttkbootstrap darkly ne supporte pas foreground par onglet
        # (Placeholder — setup du Journal ci-dessous)

        # ── Barre QSL upload ─────────────────────────────────────────────────
        qsl_bar = tk.Frame(t_log, bg="#0d1e30", pady=5)
        qsl_bar.pack(fill="x", padx=0)
        tk.Label(qsl_bar, text="QSL Auto :", bg="#0d1e30", fg="#8b949e",
                 font=("Consolas", 9)).pack(side="left", padx=(10,4))
        # Indicateurs de statut connexion
        self._qsl_eqsl_lbl = tk.Label(qsl_bar,
            text="● eQSL", bg="#0d1e30",
            fg="#3fb950" if (CONF and CONF['API'].get('EQSL_User')) else "#555",
            font=("Consolas", 9, "bold"))
        self._qsl_eqsl_lbl.pack(side="left", padx=6)
        self._qsl_qrz_lbl = tk.Label(qsl_bar,
            text="● QRZ", bg="#0d1e30",
            fg="#3fb950" if (CONF and CONF['API'].get('QRZ_Log_Key')) else "#555",
            font=("Consolas", 9, "bold"))
        self._qsl_qrz_lbl.pack(side="left", padx=6)
        self._qsl_club_lbl = tk.Label(qsl_bar,
            text="● ClubLog", bg="#0d1e30",
            fg="#3fb950" if (CONF and CONF['API'].get('Club_Email')) else "#555",
            font=("Consolas", 9, "bold"))
        self._qsl_club_lbl.pack(side="left", padx=6)
        import os as _os
        _tqsl_ok = CONF and _os.path.exists(CONF.get('LOTW', 'Tqsl_Path', fallback=''))
        tk.Label(qsl_bar, text="● LoTW/TQSL", bg="#0d1e30",
                 fg="#3fb950" if _tqsl_ok else "#f39c12",
                 font=("Consolas", 9, "bold")).pack(side="left", padx=6)
        # Bouton vérification entrante
        ttk.Button(qsl_bar, text="📥 Vérifier QSL reçues",
                   command=self.check_incoming_qsl,
                   bootstyle="info-outline").pack(side="right", padx=10)
        ttk.Button(qsl_bar, text="📤 Renvoyer QSO sélectionné",
                   command=self._resend_selected_qso,
                   bootstyle="success-outline").pack(side="right", padx=4)
        ttk.Button(qsl_bar, text="📧 Envoyer QSL par email",
                   command=lambda: self._qsl_emailer.send_dialog() if self._qsl_emailer
                           else messagebox.showerror("Erreur", "tab_qsl.py introuvable"),
                   bootstyle="warning-outline").pack(side="right", padx=4)

        cols = ("ID","Pays","Date","Heure","Callsign","Nom","QTH","Bande","Mode","RS","RR","Km","Ant°","QRZ","eQSL","LoTW","Club","Comment","Grid")
        self.tree = ttk.Treeview(t_log, columns=cols, show='headings', style="Custom.Treeview")
        for c in cols: self.tree.heading(c, text=c); self.tree.column(c, width=50, anchor="center")
        self.tree.column("ID", width=0, stretch=tk.NO); self.tree.column("Grid", width=0, stretch=tk.NO)
        self.tree.column("Pays", width=80); self.tree.column("Nom", width=120); self.tree.column("QTH", width=120); self.tree.column("Comment", width=150)
        sb = ttk.Scrollbar(t_log, orient="vertical", command=self.tree.yview); self.tree.configure(yscroll=sb.set); sb.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.edit_qso)
        self.tree.bind("<Control-a>", lambda e: self.select_all())
        self.tree.bind("<Control-A>", lambda e: self.select_all())

        self.menu = tk.Menu(self.root, tearoff=0, bg="#1a3a5c", fg="white",
                            activebackground="#1a5276", activeforeground="white")
        self.menu.add_command(label="☑️ Tout sélectionner  (Ctrl+A)", command=self.select_all)
        self.menu.add_separator()
        self.menu.add_command(label="✅ LoTW OK", command=lambda: self.manual_mark("lotw_stat"))
        self.menu.add_command(label="✅ ClubLog OK", command=lambda: self.manual_mark("club_stat"))
        self.menu.add_separator()
        self.menu.add_command(label="📤 Exporter Sélection (ADIF)", command=self.export_selection)
        self.menu.add_command(label="📤 Exporter LoTW (ADIF)", command=self.export_lotw_adif)
        self.menu.add_separator()
        self.menu.add_command(label="📧 Envoyer QSL par email",
                              command=lambda: self._qsl_emailer.send_dialog() if self._qsl_emailer
                                      else messagebox.showerror("Erreur", "tab_qsl.py introuvable"))
        self.menu.add_separator()
        self.menu.add_command(label="❌ Supprimer la sélection", command=self.del_qso)
        self.menu.add_separator()
        self.menu.add_command(label="🗑️ Vider tout le logbook…", command=self.clear_logbook)
        self.tree.bind("<Button-3>", lambda e: self.menu.post(e.x_root, e.y_root))

        # --- Onglet Carte Live ---
        t_map = tk.Frame(self.nb, bg=BG); self.nb.add(t_map, text="🌍 Carte Live")
        map_ctrl = tk.Frame(t_map, bg=BG); map_ctrl.pack(fill="x", padx=5, pady=3)
        self.greyline_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(map_ctrl, text="🌓 Greyline animée", variable=self.greyline_var,
                        command=self._toggle_greyline, bootstyle="info-round-toggle").pack(side="left", padx=5)
        self.greyline_info_var = tk.StringVar(value="")
        ttk.Label(map_ctrl, textvariable=self.greyline_info_var, foreground="#3daee9", font=("Consolas",9)).pack(side="left", padx=10)
        self.map_widget = TkinterMapView(t_map, corner_radius=10); self.map_widget.pack(fill="both", expand=True, padx=5, pady=5)
        self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        home_pos = grid_to_latlon(MY_GRID)
        if home_pos:
            self.map_widget.set_position(home_pos[0], home_pos[1])
            self.map_widget.set_zoom(5)
            self.home_marker = self.map_widget.set_marker(home_pos[0], home_pos[1], text=f"🏠 {MY_CALL}")
        self._greyline_markers = []
        self._update_greyline_map()  # Premier tracé immédiat

        # --- Onglet QSL Email ---
        self._qsl_email_tab = None
        try:
            from tab_qsl_email import QSLEmailTab
            t_qslemail = tk.Frame(self.nb, bg=BG)
            self.nb.add(t_qslemail, text="📧 QSL Email")
            self._qsl_email_tab = QSLEmailTab(t_qslemail, app=self,
                                              get_country=get_country_name)
        except Exception as _e:
            print(f"[QSLEmailTab] Import échoué : {_e}")

        # --- Onglet QSL Card ---
        t_qslcard = tk.Frame(self.nb, bg=BG); self.nb.add(t_qslcard, text="🖨️ QSL Card")
        self._build_qslcard_tab(t_qslcard)

        # --- Onglet Grayline ---
        t_gray = tk.Frame(self.nb, bg=BG); self.nb.add(t_gray, text="🌙 Grayline")
        from tab_grayline import TabGrayline
        TabGrayline(t_gray, app=self)

        # --- Onglet DX Live ---
        from tab_dx_unified import TabDXUnified
        t_dx = tk.Frame(self.nb, bg=BG)
        self.nb.add(t_dx, text="📡 DX Live")
        TabDXUnified(t_dx, app=self)

        # --- Onglet PSK Reporter ---
        t_psk = tk.Frame(self.nb, bg=BG); self.nb.add(t_psk, text="📻 PSK Reporter")
        self._build_psk_tab(t_psk)

        # --- Onglet Mémoires fréquences ---
        t_mem = tk.Frame(self.nb, bg=BG); self.nb.add(t_mem, text="📻 Mémoires")
        self._build_memories_tab(t_mem)

        # --- Onglet DX World + DXCC (unifié) ---
        t_dxcc = tk.Frame(self.nb, bg=BG); self.nb.add(t_dxcc, text="🌍 DX World / DXCC")
        try:
            from tab_dxcc import DXCCTab, DXCC_DATA as _dxcc_data
            self.DXCC_DATA = _dxcc_data
            self._dxcc_tab = DXCCTab(t_dxcc, app=self,
                                     get_country=get_country_name,
                                     grid_to_latlon=grid_to_latlon)
        except Exception as _e:
            import traceback; traceback.print_exc()
            tk.Label(t_dxcc, text=f"⚠️ tab_dxcc.py introuvable : {_e}",
                     fg="red", bg=BG).pack(expand=True)

        # --- Onglet Spot History ---
        t_spot_hist = tk.Frame(self.nb, bg=BG); self.nb.add(t_spot_hist, text="📜 Spot History")
        self._build_spot_history_tab(t_spot_hist)

        # --- Onglet Statistiques avancées ---
        t_stat = tk.Frame(self.nb, bg=BG); self.nb.add(t_stat, text="📈 Statistiques")
        self._build_stats_tab(t_stat)

        # --- Onglet Graphiques ---
        t_graphs = tk.Frame(self.nb, bg=BG); self.nb.add(t_graphs, text="📊 Graphiques")
        self._build_graphs_tab(t_graphs)

        # --- Onglet Heatmap ---
        t_heat = tk.Frame(self.nb, bg=BG); self.nb.add(t_heat, text="🗺️ Heatmap")
        self._build_heatmap_tab(t_heat)

        # --- Onglet Contests ---
        from contest_tab import ContestTab
        t_contests = tk.Frame(self.nb, bg="#11273f")
        self.nb.add(t_contests, text="🏆 Contests")
        self._contest_tab = ContestTab(t_contests)

        # --- Onglet Wiki ---
        t_wiki = tk.Frame(self.nb, bg=BG); self.nb.add(t_wiki, text="📖 Wiki")
        self._build_wiki_tab(t_wiki)

        # Barre de statut (TOUJOURS en dernier pour être en bas)
        self.lbl_count = ttk.Label(self.root, text="QSO: 0", font=("Consolas", 10, "bold"), foreground="#f39c12")
        self.lbl_count.pack(side="bottom", anchor="e", padx=10)
        self.lbl_status = ttk.Label(self.root, textvariable=self.status_var, font=("Consolas", 11, "bold"), foreground="#3daee9", padding=5)
        self.lbl_status.pack(side="bottom", fill="x")

        # ── Raccourcis clavier F1-F7 : sélection rapide de bande ──────────────
        _BAND_FREQS = {
            "<F1>": ("1825000",  "160m", "SSB"),
            "<F2>": ("3730000",  "80m",  "SSB"),
            "<F3>": ("7100000",  "40m",  "SSB"),
            "<F4>": ("14200000", "20m",  "SSB"),
            "<F5>": ("21200000", "15m",  "SSB"),
            "<F6>": ("28500000", "10m",  "SSB"),
            "<F7>": ("50150000", "6m",   "SSB"),
        }
        for key, (freq, band, mode) in _BAND_FREQS.items():
            self.root.bind(key, lambda e, f=freq, b=band, m=mode: self._select_band(f, b, m))

    def _select_band(self, freq_hz, band, mode):
        """Bascule sur une bande via raccourci clavier (F1-F7)."""
        self.current_freq_hz = freq_hz
        self.e_mode.delete(0, tk.END); self.e_mode.insert(0, mode)
        try: self.cat.set_freq(float(freq_hz))
        except: pass
        self.status_var.set(f"🎹 {band}  —  {float(freq_hz)/1e6:.3f} MHz  (F1-F7 pour changer)")

    # ==========================================
    # --- ONGLET DASHBOARD ---
    # ==========================================
    def _build_dashboard_tab(self, parent):
        """Tableau de bord principal avec widgets live."""
        BG = "#11273f"
        BG2 = "#0d1e30"   # légèrement plus sombre pour les LabelFrame intérieurs

        # Frame principale scrollable
        canvas_outer = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas_outer.yview)
        canvas_outer.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas_outer.pack(fill="both", expand=True)
        dash_frame = tk.Frame(canvas_outer, bg=BG, padx=10, pady=10)
        canvas_outer.create_window((0,0), window=dash_frame, anchor="nw")
        dash_frame.bind("<Configure>", lambda e: canvas_outer.configure(scrollregion=canvas_outer.bbox("all")))

        def lf(parent, title, fg_title="#f39c12"):
            """LabelFrame stylisé avec fond #11273f."""
            f = tk.LabelFrame(parent, text=title, bg=BG, fg=fg_title,
                              font=("Arial", 9, "bold"),
                              bd=1, relief="groove",
                              padx=10, pady=8)
            return f

        # --- Ligne 1 : Grands chiffres ---
        row1 = tk.Frame(dash_frame, bg=BG); row1.pack(fill="x", pady=8)

        frm_total = lf(row1, "📊 QSOs Total", "#3498db")
        frm_total.pack(side="left", expand=True, fill="both", padx=6)
        self.dash_total_var = tk.StringVar(value="---")
        tk.Label(frm_total, textvariable=self.dash_total_var, font=("Impact",40),
                 fg="#3498db", bg=BG).pack()
        self.dash_today_var = tk.StringVar(value="-- aujourd'hui")
        tk.Label(frm_total, textvariable=self.dash_today_var, font=("Arial",10),
                 fg="#aaa", bg=BG).pack()

        frm_dxcc = lf(row1, "🌍 DXCC Travaillés", "#2ecc71")
        frm_dxcc.pack(side="left", expand=True, fill="both", padx=6)
        self.dash_dxcc_var = tk.StringVar(value="---")
        tk.Label(frm_dxcc, textvariable=self.dash_dxcc_var, font=("Impact",40),
                 fg="#2ecc71", bg=BG).pack()
        self.dash_dxcc_conf_var = tk.StringVar(value="-- confirmés")
        tk.Label(frm_dxcc, textvariable=self.dash_dxcc_conf_var, font=("Arial",10),
                 fg="#aaa", bg=BG).pack()

        frm_band = lf(row1, "📻 Bande active", "#f39c12")
        frm_band.pack(side="left", expand=True, fill="both", padx=6)
        self.dash_band_var = tk.StringVar(value="---")
        tk.Label(frm_band, textvariable=self.dash_band_var, font=("Impact",40),
                 fg="#f39c12", bg=BG).pack()
        self.dash_freq_var = tk.StringVar(value="--- MHz")
        tk.Label(frm_band, textvariable=self.dash_freq_var, font=("Consolas",11),
                 fg="#aaa", bg=BG).pack()

        frm_prop = lf(row1, "🌞 Propagation", "#e74c3c")
        frm_prop.pack(side="left", expand=True, fill="both", padx=6)
        self.dash_prop_var = tk.StringVar(value="Chargement...")
        tk.Label(frm_prop, textvariable=self.dash_prop_var, font=("Consolas",10),
                 fg="#f39c12", bg=BG, justify="center").pack()

        # --- Ligne 2 : Greyline + Dernier QSO ---
        row2 = tk.Frame(dash_frame, bg=BG); row2.pack(fill="x", pady=8)

        frm_gl = lf(row2, "🌓 Greyline & Soleil", "#3498db")
        frm_gl.pack(side="left", expand=True, fill="both", padx=6)
        self.dash_gl_var = tk.StringVar(value="Calcul...")
        tk.Label(frm_gl, textvariable=self.dash_gl_var, font=("Consolas",11),
                 fg="#3498db", bg=BG, justify="left").pack(anchor="w")

        frm_last = lf(row2, "📡 Dernier QSO", "#95a5a6")
        frm_last.pack(side="left", expand=True, fill="both", padx=6)
        self.dash_last_var = tk.StringVar(value="Aucun QSO")
        tk.Label(frm_last, textvariable=self.dash_last_var, font=("Consolas",11),
                 fg="white", bg=BG, justify="left").pack(anchor="w")

        frm_rate = lf(row2, "⚡ Cadence QSOs", "#2ecc71")
        frm_rate.pack(side="left", expand=True, fill="both", padx=6)
        self.dash_rate_var   = tk.StringVar(value="-- QSO/h")
        self.dash_rate24_var = tk.StringVar(value="-- aujourd'hui")
        tk.Label(frm_rate, textvariable=self.dash_rate_var, font=("Impact",26),
                 fg="#2ecc71", bg=BG).pack()
        tk.Label(frm_rate, textvariable=self.dash_rate24_var, font=("Consolas",9),
                 fg="#aaa", bg=BG).pack()

        # --- Météo (4e colonne de row2) ---
        try:
            from tab_weather import WeatherWidget
            frm_meteo = lf(row2, "🌤️ Météo locale", "#3daee9")
            frm_meteo.pack(side="left", expand=True, fill="both", padx=6)
            WeatherWidget(frm_meteo, bg=BG, compact=True)
        except Exception as _we:
            print(f"[WeatherWidget] {_we}")

        # --- Ligne 3 : Progression Awards ---
        row3 = tk.Frame(dash_frame, bg=BG); row3.pack(fill="x", pady=8)

        frm_awards = lf(row3, "🏆 Progression Awards", "#f39c12")
        frm_awards.pack(fill="x", padx=6)
        self._dash_award_bars = {}
        awards_cfg = [
            ("DXCC 100", 100, "success"),
            ("DXCC 200", 200, "info"),
            ("DXCC 300", 300, "warning"),
            ("WAZ 40",   40,  "danger"),
            ("WAS 50",   50,  "primary"),
        ]
        for label, maxval, bstyle in awards_cfg:
            f = tk.Frame(frm_awards, bg=BG); f.pack(fill="x", pady=3)
            tk.Label(f, text=f"{label}:", width=12, anchor="e",
                     font=("Arial",9), bg=BG, fg="white").pack(side="left")
            pb = ttk.Progressbar(f, maximum=maxval, bootstyle=f"{bstyle}-striped", length=350)
            pb.pack(side="left", padx=8)
            lbl = tk.Label(f, text=f"0/{maxval}", fg="white", bg=BG, width=12)
            lbl.pack(side="left")
            self._dash_award_bars[label] = (pb, lbl, maxval)

        # --- Ligne 4 : Activité récente + Top 5 pays ---
        row4 = tk.Frame(dash_frame, bg=BG); row4.pack(fill="x", pady=8)

        frm_recent = lf(row4, "🕐 Activité récente (7 derniers jours)", "#3498db")
        frm_recent.pack(side="left", expand=True, fill="both", padx=6)
        cols_r = ("Date","Heure","Callsign","Pays","Bande","Mode")
        self.dash_tree_recent = ttk.Treeview(frm_recent, columns=cols_r, show='headings',
                                              bootstyle="info", height=6)
        for col in cols_r:
            self.dash_tree_recent.heading(col, text=col)
            self.dash_tree_recent.column(col, width=90, anchor="center")
        self.dash_tree_recent.column("Pays", width=130, anchor="w")
        self.dash_tree_recent.pack(fill="both", expand=True)
        self.dash_tree_recent.configure(style="Custom.Treeview")

        frm_top = lf(row4, "🏅 Top 5 pays (tous QSOs)", "#2ecc71")
        frm_top.pack(side="left", expand=True, fill="both", padx=6)
        cols_t = ("Pays","QSOs")
        self.dash_tree_top = ttk.Treeview(frm_top, columns=cols_t, show='headings',
                                           bootstyle="success", height=6)
        for col in cols_t:
            self.dash_tree_top.heading(col, text=col)
            self.dash_tree_top.column(col, width=140, anchor="center")
        self.dash_tree_top.column("Pays", anchor="w")
        self.dash_tree_top.pack(fill="both", expand=True)
        self.dash_tree_top.configure(style="Custom.Treeview")

        # --- Boutons ---
        row5 = tk.Frame(dash_frame, bg=BG); row5.pack(fill="x", pady=12)
        ttk.Button(row5, text="📄 Générer Rapport PDF", command=self._export_pdf_report,
                   bootstyle="danger", width=26).pack(side="left", padx=8)
        ttk.Button(row5, text="🔄 Actualiser Dashboard", command=self._refresh_dashboard,
                   bootstyle="primary-outline", width=24).pack(side="left", padx=5)


    def _on_psk_spots(self, spots):
        """Callback appelé par PSKReporterThread avec les spots reçus."""
        self._psk_spots = spots
        self.root.after(0, self._refresh_psk_tab)

    def _refresh_dashboard(self):
        """Met à jour tous les widgets du dashboard."""
        try:
            c = self.conn.cursor()
            # Total QSOs
            total = c.execute("SELECT COUNT(*) FROM qsos").fetchone()[0]
            self.dash_total_var.set(str(total))
            today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            today_n = c.execute("SELECT COUNT(*) FROM qsos WHERE qso_date=?", (today_str,)).fetchone()[0]
            self.dash_today_var.set(f"{today_n} aujourd'hui")

            # DXCC
            countries = set()
            conf_entities = set()
            for call, lotw, eqsl, qslr in c.execute(
                    "SELECT callsign, lotw_stat, eqsl_stat, qsl_rcvd FROM qsos"):
                cn = get_country_name(call)
                if not cn: continue
                countries.add(cn)
                if ((lotw and lotw.upper() in ('OK','YES','Y','LOTW')) or
                    (eqsl and eqsl.upper() in ('OK','YES','Y','EQSL')) or
                    (qslr and qslr.upper() in ('Y','YES','R'))):
                    conf_entities.add(cn)
            # Ajouter les confirmations manuelles (table dxcc_confirmed)
            for (entity,) in c.execute("SELECT entity FROM dxcc_confirmed WHERE confirmed=1"):
                conf_entities.add(entity)
            self.dash_dxcc_var.set(str(len(countries)))
            self.dash_dxcc_conf_var.set(f"{len(conf_entities)} confirmés")

            # Bande active (depuis CAT)
            try:
                freq_hz = float(self.current_freq_hz)
                band = freq_to_band(str(freq_hz))
                freq_mhz = f"{freq_hz/1e6:.3f} MHz"
            except:
                band = "---"; freq_mhz = "--- MHz"
            self.dash_band_var.set(band)
            self.dash_freq_var.set(freq_mhz)

            # Propagation résumé
            solar_txt = self.solar_var.get()
            gl_status = get_day_night_status()
            self.dash_prop_var.set(f"{solar_txt}\n{gl_status}")

            # Greyline
            sr, ss = self._calc_greyline_times()
            now_utc = datetime.now(timezone.utc)
            self.dash_gl_var.set(
                f"📍 {MY_CALL}  ({MY_GRID})\n"
                f"🌅 Lever  : {sr} UTC\n"
                f"🌇 Coucher: {ss} UTC\n"
                f"⏰ Maintenant: {now_utc.strftime('%H:%M')} UTC  {gl_status}"
            )

            # Dernier QSO
            last = c.execute(
                "SELECT qso_date, time_on, callsign, band, mode, rst_sent, rst_rcvd "
                "FROM qsos ORDER BY qso_date DESC, time_on DESC LIMIT 1").fetchone()
            if last:
                country_l = get_country_name(last[2])
                self.dash_last_var.set(
                    f"📡 {last[2]}  ({country_l})\n"
                    f"📅 {last[0]}  ⏰ {last[1]} UTC\n"
                    f"📻 {last[3]}  {last[4]}  RST: {last[5]}/{last[6]}"
                )

            # Awards bars
            dxcc_n = len(countries)
            calls = c.execute("SELECT callsign FROM qsos").fetchall()
            # WAZ estimation
            waz_set = set()
            for (call,) in calls:
                entity = get_country_name(call)
                zone = self.WAZ_ZONES.get(entity)
                if zone: waz_set.add(zone)
            waz_n = len(waz_set)
            # WAS estimation
            rows_was = c.execute("SELECT callsign, qth FROM qsos").fetchall()
            was_set = set()
            for call, qth in rows_was:
                if call and call[0].upper() in ('K','W','N') and qth:
                    for state in self.USA_STATES:
                        if state.upper() in qth.upper():
                            was_set.add(state)
            was_n = len(was_set)

            award_vals = {"DXCC 100": dxcc_n, "DXCC 200": dxcc_n, "DXCC 300": dxcc_n,
                          "WAZ 40": waz_n, "WAS 50": was_n}
            for label, (pb, lbl, maxval) in self._dash_award_bars.items():
                val = award_vals.get(label, 0)
                pb['value'] = min(val, maxval)
                done = "✅" if val >= maxval else ""
                lbl.config(text=f"{min(val, maxval)}/{maxval} {done}")

            # Cadence QSOs/heure
            if hasattr(self, 'dash_rate_var'):
                now_utc = datetime.now(timezone.utc)
                one_hour_ago = (now_utc - __import__('datetime').timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')
                today_str    = now_utc.strftime('%Y-%m-%d')
                n_hour = c.execute(
                    "SELECT COUNT(*) FROM qsos WHERE qso_date || ' ' || time_on >= ?",
                    (one_hour_ago,)).fetchone()[0]
                n_today = c.execute(
                    "SELECT COUNT(*) FROM qsos WHERE qso_date = ?",
                    (today_str,)).fetchone()[0]
                self.dash_rate_var.set(f"{n_hour} QSO/h")
                self.dash_rate24_var.set(f"{n_today} aujourd'hui ({today_str})")

            # Activité récente (7 jours)
            for item in self.dash_tree_recent.get_children():
                self.dash_tree_recent.delete(item)
            week_ago = (datetime.now(timezone.utc).date() - __import__('datetime').timedelta(days=7)).strftime('%Y-%m-%d')
            recent = c.execute(
                "SELECT qso_date, time_on, callsign, band, mode FROM qsos "
                "WHERE qso_date >= ? ORDER BY qso_date DESC, time_on DESC LIMIT 20",
                (week_ago,)).fetchall()
            for r in recent:
                country_r = get_country_name(r[2])
                self.dash_tree_recent.insert("", "end", values=(r[0], r[1], r[2], country_r, r[3], r[4]))

            # Top 5 pays
            for item in self.dash_tree_top.get_children():
                self.dash_tree_top.delete(item)
            country_counts = {}
            for (call,) in calls:
                cn = get_country_name(call)
                if cn: country_counts[cn] = country_counts.get(cn, 0) + 1
            medals = ["🥇","🥈","🥉","4.","5."]
            for i, (cn, cnt) in enumerate(sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:5]):
                self.dash_tree_top.insert("", "end", values=(f"{medals[i]} {cn}", cnt))

        except Exception as e:
            print(f"Dashboard refresh error: {e}")

        # Re-schedule toutes les 30 secondes
        self.root.after(30000, self._refresh_dashboard)

    # ==========================================
    # --- GREYLINE ANIMÉE SUR CARTE ---
    # ==========================================
    def _update_greyline_map(self):
        """Trace le terminateur solaire sur la carte TkinterMapView."""
        if not self.greyline_var.get():
            self.root.after(60000, self._update_greyline_map)
            return
        try:
            # Supprimer les anciens marqueurs greyline
            for m in self._greyline_markers:
                try: m.delete()
                except: pass
            self._greyline_markers.clear()

            pts = get_solar_terminator_lats(90)
            # Placer des marqueurs légers tous les 4 degrés de longitude
            for lat, lon in pts[::2]:
                m = self.map_widget.set_marker(lat, lon, text="", marker_color_circle="#f39c12",
                                               marker_color_outside="orange")
                self._greyline_markers.append(m)

            now_utc = datetime.now(timezone.utc)
            sr, ss = self._calc_greyline_times()
            self.greyline_info_var.set(f"Terminateur solaire  |  Lever: {sr} UTC  Coucher: {ss} UTC  |  {now_utc.strftime('%H:%M')} UTC")
        except Exception as e:
            print(f"Greyline map error: {e}")

        # Rafraîchir toutes les 60 secondes
        self.root.after(60000, self._update_greyline_map)

    def _toggle_greyline(self):
        """Active/désactive la greyline sur la carte."""
        if not self.greyline_var.get():
            for m in self._greyline_markers:
                try: m.delete()
                except: pass
            self._greyline_markers.clear()
            self.greyline_info_var.set("Greyline désactivée")
        else:
            self._update_greyline_map()

    # ==========================================
    # --- PSK REPORTER TAB ---
    # ==========================================
    def _build_psk_tab(self, parent):
        ctrl = tk.Frame(parent, bg="#11273f"); ctrl.pack(fill="x")
        ttk.Label(ctrl, text=f"Stations qui ont entendu {MY_CALL} (PSK Reporter — dernière heure) :",
                  font=("Arial",10,"bold"), foreground="#f39c12").pack(side="left", padx=5)
        ttk.Button(ctrl, text="🔄 Actualiser", command=lambda: threading.Thread(
            target=self._psk_thread.run, daemon=True).start(),
            bootstyle="primary-outline").pack(side="right", padx=5)
        self.psk_count_var = tk.StringVar(value="Chargement...")
        ttk.Label(ctrl, textvariable=self.psk_count_var, foreground="#aaa").pack(side="right", padx=10)

        cols = ("UTC","Callsign TX","Entendu par","Locator RX","Freq MHz","Bande","Mode","SNR","Pays RX")
        self.tree_psk = ttk.Treeview(parent, columns=cols, show='headings', style="Custom.Treeview")
        widths = [55, 100, 110, 80, 80, 60, 60, 60, 140]
        for col, w in zip(cols, widths):
            self.tree_psk.heading(col, text=col)
            self.tree_psk.column(col, width=w, anchor="center")
        self.tree_psk.column("Entendu par", anchor="w")
        self.tree_psk.column("Pays RX", anchor="w")
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_psk.yview)
        self.tree_psk.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree_psk.pack(fill="both", expand=True)
        self.tree_psk.tag_configure('row0', background='#11273f')
        self.tree_psk.tag_configure('row1', background='#34495e')
        self.tree_psk.bind("<Double-1>", self._psk_show_on_map)

        # Note
        ttk.Label(parent,
                  text="ℹ️  Les spots PSK Reporter montrent où votre signal a été entendu dans le monde. Double-clic = voir sur la carte.",
                  foreground="#888", font=("Arial",9)).pack(anchor="w", padx=8, pady=3)

    def _refresh_psk_tab(self):
        """Rafraîchit le tableau PSK Reporter avec les derniers spots."""
        if not hasattr(self, 'tree_psk'): return
        for item in self.tree_psk.get_children():
            self.tree_psk.delete(item)
        for i, spot in enumerate(self._psk_spots):
            tag = 'row0' if i % 2 == 0 else 'row1'
            self.tree_psk.insert("", "end", values=spot, tags=(tag,))
        n = len(self._psk_spots)
        self.psk_count_var.set(f"{n} réception(s) trouvée(s)")

    def _psk_show_on_map(self, event=None):
        """Double-clic sur un spot PSK → affiche le locator sur la carte."""
        sel = self.tree_psk.selection()
        if not sel: return
        v = self.tree_psk.item(sel[0])['values']
        locator = str(v[3]) if len(v) > 3 else ""
        if len(locator) >= 4:
            pos = grid_to_latlon(locator)
            if pos:
                self.nb.select(1)  # Aller sur l'onglet Carte
                self.map_widget.set_position(pos[0], pos[1])
                self.map_widget.set_zoom(6)
                m = self.map_widget.set_marker(pos[0], pos[1], text=f"📻 {v[1]} via {v[2]}")
                self.status_var.set(f"PSK Reporter: {v[2]} ({locator}) a entendu {v[1]} sur {v[4]} MHz {v[6]}")

    # ==========================================
    # --- EXPORT RAPPORT PDF ---
    # ==========================================
    def _export_pdf_report(self):
        """Génère un rapport de station complet en PDF."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
        except ImportError:
            messagebox.showerror("PDF",
                "reportlab n'est pas installé.\n\nInstallez-le avec :\n    pip install reportlab\n\n"
                "Puis relancez Station Master.")
            return

        fn = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            title="Enregistrer le rapport PDF",
            initialfile=f"Rapport_{MY_CALL}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        )
        if not fn: return

        try:
            c = self.conn.cursor()
            doc = SimpleDocTemplate(fn, pagesize=A4,
                                    rightMargin=2*cm, leftMargin=2*cm,
                                    topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet()
            story = []

            # --- En-tête ---
            title_style = ParagraphStyle('Title', fontSize=28, textColor=colors.HexColor('#f39c12'),
                                         fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=6)
            sub_style   = ParagraphStyle('Sub', fontSize=13, textColor=colors.HexColor('#3498db'),
                                         fontName='Helvetica', alignment=TA_CENTER, spaceAfter=4)
            h2_style    = ParagraphStyle('H2', fontSize=13, textColor=colors.HexColor('#2ecc71'),
                                         fontName='Helvetica-Bold', spaceBefore=14, spaceAfter=4)
            body_style  = ParagraphStyle('Body', fontSize=9, textColor=colors.black,
                                         fontName='Helvetica', spaceAfter=3)

            story.append(Paragraph(f"STATION MASTER — {MY_CALL}", title_style))
            story.append(Paragraph(f"Rapport de station  •  Locator : {MY_GRID}", sub_style))
            story.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} UTC", body_style))
            story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#f39c12'), spaceAfter=12))

            # --- Statistiques générales ---
            total = c.execute("SELECT COUNT(*) FROM qsos").fetchone()[0]
            today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            today_n = c.execute("SELECT COUNT(*) FROM qsos WHERE qso_date=?", (today_str,)).fetchone()[0]
            first_qso = c.execute("SELECT MIN(qso_date) FROM qsos").fetchone()[0] or "---"

            calls = c.execute("SELECT callsign FROM qsos").fetchall()
            countries = set()
            for (call,) in calls:
                cn = get_country_name(call)
                if cn: countries.add(cn)
            confirmed = c.execute("SELECT COUNT(*) FROM dxcc_confirmed WHERE confirmed=1").fetchone()[0]

            story.append(Paragraph("📊 Statistiques générales", h2_style))
            gen_data = [
                ["Indicatif", MY_CALL, "Locator", MY_GRID],
                ["QSOs total", str(total), "Aujourd'hui", str(today_n)],
                ["Premier QSO", first_qso, "DXCC travaillés", str(len(countries))],
                ["DXCC confirmés", str(confirmed), "", ""],
            ]
            gen_tbl = Table(gen_data, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
            gen_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a3a5c')),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f0f4f8')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#e8f0fe')]),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(gen_tbl)

            # --- QSOs par bande ---
            story.append(Paragraph("🎚️ QSOs par bande", h2_style))
            band_rows = c.execute(
                "SELECT band, COUNT(*) as n FROM qsos GROUP BY band ORDER BY n DESC").fetchall()
            if band_rows:
                tbl_data = [["Bande", "QSOs", "% du total"]]
                for band, n in band_rows:
                    pct = f"{n/total*100:.1f}%" if total else "0%"
                    tbl_data.append([band or "?", str(n), pct])
                tbl = Table(tbl_data, colWidths=[4*cm, 4*cm, 4*cm])
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a5c1a')),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#e8ffe8')]),
                    ('PADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(tbl)

            # --- QSOs par mode ---
            story.append(Paragraph("📻 QSOs par mode", h2_style))
            mode_rows = c.execute(
                "SELECT mode, COUNT(*) as n FROM qsos GROUP BY mode ORDER BY n DESC").fetchall()
            if mode_rows:
                tbl_data = [["Mode", "QSOs", "% du total"]]
                for mode, n in mode_rows:
                    pct = f"{n/total*100:.1f}%" if total else "0%"
                    tbl_data.append([mode or "?", str(n), pct])
                tbl = Table(tbl_data, colWidths=[4*cm, 4*cm, 4*cm])
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#5c1a1a')),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#ffe8e8')]),
                    ('PADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(tbl)

            # --- Top 20 pays ---
            story.append(Paragraph("🏆 Top 20 pays (DXCC estimé)", h2_style))
            country_counts = {}
            for (call,) in calls:
                cn = get_country_name(call)
                if cn: country_counts[cn] = country_counts.get(cn, 0) + 1
            top20 = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            if top20:
                medals = ["🥇","🥈","🥉"] + [f"#{i+1}" for i in range(3,20)]
                tbl_data = [["#","Pays","QSOs"]]
                for i, (cn, cnt) in enumerate(top20):
                    tbl_data.append([medals[i], cn, str(cnt)])
                tbl = Table(tbl_data, colWidths=[2*cm, 10*cm, 4*cm])
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#5c3a1a')),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fff5e8')]),
                    ('PADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(tbl)

            # --- QSOs par mois (12 derniers) ---
            story.append(Paragraph("📅 QSOs par mois (12 derniers)", h2_style))
            month_rows = c.execute("""
                SELECT substr(qso_date,1,7) as ym, COUNT(*) as n
                FROM qsos WHERE qso_date != ''
                GROUP BY ym ORDER BY ym DESC LIMIT 12""").fetchall()
            if month_rows:
                tbl_data = [["Mois","QSOs"]]
                for ym, n in reversed(month_rows):
                    tbl_data.append([ym, str(n)])
                tbl = Table(tbl_data, colWidths=[6*cm, 4*cm])
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a3a5c')),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#e8f0fe')]),
                    ('PADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(tbl)

            # --- Pied de page ---
            story.append(Spacer(1, 20))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#aaaaaa')))
            story.append(Paragraph(
                f"Station Master V21.0  •  {MY_CALL}  •  {MY_GRID}  •  Rapport généré le {datetime.now().strftime('%d/%m/%Y')}",
                ParagraphStyle('Footer', fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
            ))

            doc.build(story)
            messagebox.showinfo("PDF", f"✅ Rapport PDF généré avec succès !\n\n{fn}")
            self.status_var.set(f"📄 Rapport PDF : {os.path.basename(fn)}")

            # Ouvrir le PDF automatiquement
            try:
                if os.name == 'nt':
                    os.startfile(fn)
            except: pass

        except Exception as e:
            messagebox.showerror("Erreur PDF", f"Impossible de générer le PDF :\n{e}\n\n"
                                               "Installez reportlab : pip install reportlab")

    # ==========================================
    # --- ONGLET CLUSTER ENRICHI ---
    # ==========================================
    def _build_cluster_tab(self, parent):
        """DX Cluster complet — multi-source, propagation, activité bandes, tooltip, âge."""
        BG  = "#11273f"
        BG2 = "#0d1e30"
        BG3 = "#162035"

        # ── Barre propagation ────────────────────────────────────────────────
        prop_fr = tk.Frame(parent, bg=BG2, pady=4); prop_fr.pack(fill="x")
        tk.Label(prop_fr, text="☀ PROPAGATION", bg=BG2, fg="#3fb950",
                 font=("Consolas", 11, "bold")).pack(side="left", padx=(10, 6))
        self._cluster_prop_lbls = {}
        for key, label in [("sfi","SFI"),("ssn","SSN"),("k","K-idx"),("a","A-idx"),("aurora","Aurora")]:
            frm = tk.Frame(prop_fr, bg=BG2); frm.pack(side="left", padx=8)
            tk.Label(frm, text=label, bg=BG2, fg="#8b949e", font=("Consolas", 9)).pack()
            lbl = tk.Label(frm, text="—", bg=BG2, fg="#e6edf3",
                           font=("Consolas", 12, "bold"), width=6)
            lbl.pack(); self._cluster_prop_lbls[key] = lbl
        self._cluster_prop_upd = tk.Label(prop_fr, text="", bg=BG2, fg="#8b949e", font=("Consolas", 9))
        self._cluster_prop_upd.pack(side="right", padx=10)
        if not hasattr(self, '_cluster_solar_running'):
            self._cluster_solar_running = True
            threading.Thread(target=self._cluster_solar_loop, daemon=True).start()

        # ── Barres activité bandes ────────────────────────────────────────────
        act_fr = tk.Frame(parent, bg=BG3, pady=3); act_fr.pack(fill="x")
        tk.Label(act_fr, text="Activité :", bg=BG3, fg="#8b949e",
                 font=("Consolas", 9)).pack(side="left", padx=(8, 4))
        BAND_COL = {"160m":"#ff6b6b","80m":"#ff9f43","40m":"#ffd93d","30m":"#6bcb77",
                    "20m":"#4d96ff","17m":"#c77dff","15m":"#ff6bff","12m":"#ff9fff",
                    "10m":"#ff4757","6m":"#eccc68"}
        self._cluster_band_bars   = {}
        self._cluster_band_counts = {}
        for b in ["160m","80m","40m","30m","20m","17m","15m","12m","10m","6m"]:
            col = BAND_COL.get(b, "#888")
            frm = tk.Frame(act_fr, bg=BG3); frm.pack(side="left", padx=3)
            tk.Label(frm, text=b, bg=BG3, fg=col, font=("Consolas", 8)).pack()
            bar = tk.Canvas(frm, width=28, height=32, bg="#0d1117", highlightthickness=0, bd=0)
            bar.pack()
            self._cluster_band_bars[b]   = (bar, col)
            self._cluster_band_counts[b] = 0
        self._cluster_stats_lbl = tk.Label(act_fr, text="Session: 0 spots | 0 pays | 0h00",
                                           bg=BG3, fg="#c9d1d9", font=("Consolas", 10))
        self._cluster_stats_lbl.pack(side="right", padx=10)
        leg = tk.Frame(act_fr, bg=BG3); leg.pack(side="right", padx=14)
        for col, lbl in [("#3fb950","<5m"),("#d29922","5-15m"),("#4a5568",">15m")]:
            tk.Label(leg, text="●", bg=BG3, fg=col, font=("Consolas", 12)).pack(side="left")
            tk.Label(leg, text=lbl+" ", bg=BG3, fg="#c9d1d9", font=("Consolas", 9)).pack(side="left")

        # ── Filtres enrichis ──────────────────────────────────────────────────
        flt_fr = tk.Frame(parent, bg=BG, pady=4); flt_fr.pack(fill="x", padx=4)

        def lbl(text): tk.Label(flt_fr, text=text, bg=BG, fg="#c9d1d9",
                                font=("Consolas", 10)).pack(side="left", padx=(6, 2))

        lbl("Bande:")
        self.cluster_band_var = tk.StringVar(value="ALL")
        cb_band = ttk.Combobox(flt_fr, textvariable=self.cluster_band_var,
                                values=["ALL","160m","80m","40m","30m","20m","17m","15m","12m","10m","6m"],
                                width=6, state="readonly", font=("Consolas", 10))
        cb_band.pack(side="left", padx=2)
        cb_band.bind("<<ComboboxSelected>>", lambda e: self._apply_cluster_filter())

        lbl("Source:")
        self.cluster_src_var = tk.StringVar(value="ALL")
        cb_src = ttk.Combobox(flt_fr, textvariable=self.cluster_src_var,
                               values=["ALL","Cluster","DXHeat"], width=8, state="readonly",
                               font=("Consolas", 10))
        cb_src.pack(side="left", padx=2)
        cb_src.bind("<<ComboboxSelected>>", lambda e: self._apply_cluster_filter())

        lbl("Cont:")
        self.cluster_cont_var = tk.StringVar(value="ALL")
        cb_cont = ttk.Combobox(flt_fr, textvariable=self.cluster_cont_var,
                                values=["ALL","EU","AS","NA","SA","OC","AF"],
                                width=5, state="readonly", font=("Consolas", 10))
        cb_cont.pack(side="left", padx=2)
        cb_cont.bind("<<ComboboxSelected>>", lambda e: self._apply_cluster_filter())

        lbl("Mode:")
        self.cluster_mode_var = tk.StringVar(value="ALL")
        cb_mode = ttk.Combobox(flt_fr, textvariable=self.cluster_mode_var,
                                values=["ALL","CW","SSB","FT8","FT4","RTTY","JS8","PSK","DIGI"],
                                width=6, state="readonly", font=("Consolas", 10))
        cb_mode.pack(side="left", padx=2)
        cb_mode.bind("<<ComboboxSelected>>", lambda e: self._apply_cluster_filter())

        lbl("🔍")
        self.cluster_search_var = tk.StringVar()
        tk.Entry(flt_fr, textvariable=self.cluster_search_var, bg="#21262d", fg="#c9d1d9",
                 insertbackground="white", relief="flat", font=("Consolas", 10),
                 width=12).pack(side="left", padx=2)
        self.cluster_search_var.trace_add("write", lambda *a: self._apply_cluster_filter())

        self.cluster_alert_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(flt_fr, text="🔔 Alerte", variable=self.cluster_alert_var).pack(side="left", padx=8)
        ttk.Button(flt_fr, text="✕ Effacer", command=self._clear_cluster_filters,
                   bootstyle="secondary-outline", width=10).pack(side="left", padx=3)
        ttk.Button(flt_fr, text="⚙️ Config", command=self.open_cluster_alert_config,
                   bootstyle="warning-outline", width=10).pack(side="left", padx=3)
        ttk.Button(flt_fr, text="💾 CSV", command=self._export_cluster_csv,
                   bootstyle="info-outline", width=8).pack(side="left", padx=3)
        self.cluster_count_var = tk.StringVar(value="0 spots")
        tk.Label(flt_fr, textvariable=self.cluster_count_var, bg=BG,
                 fg="#f39c12", font=("Consolas", 11, "bold")).pack(side="right", padx=10)

        # ── Treeview ──────────────────────────────────────────────────────────
        style = ttk.Style()
        style.configure("Cluster.Treeview",
            rowheight=28, font=("Consolas", 11),
            background=BG, fieldbackground=BG, foreground="#c9d1d9")
        style.configure("Cluster.Treeview.Heading",
            background="#161b22", foreground="#f39c12",
            font=("Arial", 11, "bold"), relief="flat")
        style.map("Cluster.Treeview",
            background=[("selected", "#1a5276")], foreground=[("selected", "white")])

        cols = ("UTC","Âge","Freq","Band","Mode","Cont","Pays","DX Call","Az°","km","Spotter","Source","Info")
        self.tree_cl = ttk.Treeview(parent, columns=cols, show="headings", style="Cluster.Treeview")
        for cid, heading, width, anchor in [
            ("UTC",     "UTC",     65,  "center"),("Âge",     "Âge",     50,  "center"),
            ("Freq",    "Freq",    95,  "center"),("Band",    "Bande",   65,  "center"),
            ("Mode",    "Mode",    65,  "center"),("Cont",    "Cont",    45,  "center"),
            ("Pays",    "Pays",    150, "w"),     ("DX Call", "DX Call", 100, "w"),
            ("Az°",     "Az SP°",  55,  "center"),("km",      "km",      65,  "center"),
            ("Spotter", "Spotter", 110, "w"),     ("Source",  "Source",  70,  "center"),
            ("Info",    "Info",    260, "w"),
        ]:
            self.tree_cl.heading(cid, text=heading)
            self.tree_cl.column(cid, width=width, anchor=anchor)

        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_cl.yview)
        self.tree_cl.configure(yscroll=sb.set)
        sb.pack(side="right", fill="y")
        self.tree_cl.pack(fill="both", expand=True)

        self.tree_cl.tag_configure("age_new",   foreground="#3fb950")
        self.tree_cl.tag_configure("age_mid",   foreground="#d29922")
        self.tree_cl.tag_configure("age_old",   foreground="#4a5568")
        self.tree_cl.tag_configure("new_dxcc",  background="#1a2a4a", foreground="#bc8cff")
        self.tree_cl.tag_configure("alert",     background="#3a1a1a", foreground="#ff6b35")
        self.tree_cl.tag_configure("watchlist", background="#2a1a3a", foreground="#ffdd57")
        self.tree_cl.tag_configure("row_alt",   background="#161b22")

        self.tree_cl.bind("<Double-1>", self.on_cluster_click)
        self.tree_cl.bind("<Button-3>", self._cluster_right_click)
        self._cl_tooltip_win  = None
        self._cl_tooltip_item = None
        self.tree_cl.bind("<Motion>", self._cluster_tooltip_show)
        self.tree_cl.bind("<Leave>",  self._cluster_tooltip_hide)

        self.root.after(15000, self._cluster_refresh_ages)

    # ── Méthodes cluster ──────────────────────────────────────────────────────

    def _cluster_solar_loop(self):
        time.sleep(2)  # laisser mainloop() démarrer avant le premier fetch
        while True:
            try:
                resp = requests.get("https://www.hamqsl.com/solarxml.php", timeout=10)
                root = ET.fromstring(resp.content)
                sol  = root.find("solardata")
                def g(t): el = sol.find(t); return el.text.strip() if el is not None and el.text else "?"
                data = {"sfi":g("solarflux"),"ssn":g("sunspots"),
                        "k":g("kindex"),"a":g("aindex"),"aurora":g("aurora")}
                def _upd(d=data):
                    if not hasattr(self, "_cluster_prop_lbls"): return
                    for key, lbl in self._cluster_prop_lbls.items():
                        val = d.get(key, "?")
                        color = "#e6edf3"
                        if key == "k":
                            try:
                                ki = float(val)
                                color = "#3fb950" if ki <= 2 else "#d29922" if ki <= 4 else "#f85149"
                            except: pass
                        lbl.config(text=val, fg=color)
                    self._cluster_prop_upd.config(
                        text=f"Mis à jour {datetime.now().strftime('%H:%M')}")
                self._tk_queue.put(_upd)
            except Exception as e:
                print(f"[ClusterSolar] {e}")
            time.sleep(1800)

    @staticmethod
    def _age_str(seconds):
        if seconds < 60:   return f"{int(seconds)}s"
        if seconds < 3600: return f"{int(seconds//60)}m"
        return f"{int(seconds//3600)}h{int((seconds%3600)//60):02d}"

    def _cluster_refresh_ages(self):
        if not hasattr(self, "tree_cl"): return
        try:
            now = datetime.now(timezone.utc)
            for item in self.tree_cl.get_children():
                vals = list(self.tree_cl.item(item, "values"))
                call = vals[7] if len(vals) > 7 else ""
                spot = next((s for s in self._all_spots
                             if isinstance(s, dict) and s.get("call") == call), None)
                if not spot: continue
                age_sec = (now - spot["ts"]).total_seconds()
                age_tag = "age_new" if age_sec < 300 else "age_mid" if age_sec < 900 else "age_old"
                tags = self.tree_cl.item(item, "tags")
                special = next((t for t in tags if t in ("new_dxcc","alert","watchlist")), None)
                vals[1] = self._age_str(age_sec)
                self.tree_cl.item(item, values=tuple(vals), tags=(special or age_tag,))
            self._update_cluster_stats()
            self._update_cluster_band_bars()
        except Exception as e:
            print(f"[ClusterAge] {e}")
        self.root.after(15000, self._cluster_refresh_ages)

    def _update_cluster_stats(self):
        if not hasattr(self, "_cluster_stats_lbl"): return
        try:
            n  = getattr(self, "_cluster_session_count", 0)
            nc = len(getattr(self, "_cluster_session_countries", set()))
            t0 = getattr(self, "_cluster_session_start", datetime.now(timezone.utc))
            el = (datetime.now(timezone.utc) - t0).total_seconds()
            h, m = int(el // 3600), int((el % 3600) // 60)
            self._cluster_stats_lbl.config(
                text=f"Session: {n} spots | {nc} pays | {h}h{m:02d}")
        except: pass

    def _update_cluster_band_bars(self):
        if not hasattr(self, "_cluster_band_bars"): return
        counts = self._cluster_band_counts
        maxv = max(1, max(counts.values()))
        for b, (bar, col) in self._cluster_band_bars.items():
            bar.delete("all")
            h = int(32 * counts.get(b, 0) / maxv)
            if h > 0:
                bar.create_rectangle(2, 32 - h, 26, 32, fill=col, outline="")
            bar.create_text(14, 16, text=str(counts.get(b, 0)),
                            fill="#c9d1d9", font=("Consolas", 8))

    @staticmethod
    def _latlon_to_grid(lat, lon):
        """Conversion simple lat/lon → Maidenhead 4 chars."""
        try:
            lon2 = lon + 180; lat2 = lat + 90
            g  = chr(int(lon2 / 20) + 65)
            g += chr(int(lat2 / 10) + 65)
            g += str(int((lon2 % 20) / 2))
            g += str(int(lat2 % 10))
            return g
        except: return ""

    def _cluster_get_latlon(self, callsign):
        """Retourne (lat, lon) approximatif d'un indicatif depuis DXCC_DATA."""
        call = callsign.upper().split("/")[0]
        for ln in range(4, 0, -1):
            pfx = call[:ln]
            for row in self.DXCC_DATA:
                if row[0] == pfx:
                    return row[3], row[4]
        return None, None

    def _cluster_tooltip_show(self, event):
        item = self.tree_cl.identify_row(event.y)
        if not item: self._cluster_tooltip_hide(); return
        if item == self._cl_tooltip_item: return
        self._cl_tooltip_item = item
        vals = self.tree_cl.item(item, "values")
        if not vals or len(vals) < 13: self._cluster_tooltip_hide(); return
        utc, age, freq, band, mode, cont, pays, dx_call, az_col, km_col, spotter, source, info = vals[:13]

        # Az LP = opposé de Az SP
        try:
            lp_str = f"{(int(az_col.replace('°','')) + 180) % 360}°" if az_col else "—"
            bear_str = az_col if az_col else "—"
            dist_str = f"{km_col} km" if km_col else "—"
        except:
            lp_str = "—"; bear_str = "—"; dist_str = "—"

        txt = (f"  DX Call  : {dx_call}\n"
               f"  Pays     : {pays}\n"
               f"  Continent: {cont} — {CONT_LABELS.get(cont, cont)}\n"
               f"  Fréquence: {freq} kHz  [{band}]\n"
               f"  Mode     : {mode or '?'}\n"
               f"  Az SP    : {bear_str}   Az LP : {lp_str}\n"
               f"  Distance : {dist_str}\n"
               f"  Spotter  : {spotter}\n"
               f"  Source   : {source}\n"
               f"  Âge      : {age}\n"
               f"  Info     : {info}\n"
               f"  ────────────────────────\n"
               f"  Double-clic → Syntoniser")
        self._cluster_tooltip_hide()
        win = tk.Toplevel(self.tree_cl)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"+{event.x_root + 16}+{event.y_root + 12}")
        win.configure(bg="#21262d")
        tk.Label(win, text=txt, bg="#21262d", fg="#e6edf3",
                 font=("Consolas", 10), justify="left", padx=10, pady=8).pack()
        self._cl_tooltip_win = win

    def _cluster_tooltip_hide(self, event=None):
        self._cl_tooltip_item = None
        if self._cl_tooltip_win:
            try: self._cl_tooltip_win.destroy()
            except: pass
            self._cl_tooltip_win = None

    def _apply_cluster_filter(self):
        band_f   = self.cluster_band_var.get()
        src_f    = self.cluster_src_var.get()
        cont_f   = self.cluster_cont_var.get()
        mode_f   = self.cluster_mode_var.get()
        search_f = self.cluster_search_var.get().strip().upper()

        for item in self.tree_cl.get_children():
            self.tree_cl.delete(item)

        now = datetime.now(timezone.utc); count = 0
        for spot in self._all_spots:
            if not isinstance(spot, dict): continue
            freq    = spot.get("freq","");    call    = spot.get("call","")
            comment = spot.get("comment",""); spotter = spot.get("spotter","")
            time_z  = spot.get("time_z","");  band    = spot.get("band","")
            mode    = spot.get("mode","");    country = spot.get("country","")
            cont    = spot.get("continent","?"); source = spot.get("source","Cluster")
            ts      = spot.get("ts", now)

            if band_f  != "ALL" and band.lower() != band_f.lower(): continue
            if src_f   != "ALL" and source != src_f:                continue
            if cont_f  != "ALL" and cont   != cont_f:               continue
            if mode_f  != "ALL" and mode   != mode_f:               continue
            if search_f and not any(search_f in x.upper()
                                    for x in [call, country, spotter, comment]): continue

            # Calcul Az SP et distance depuis MY_GRID
            az_str = ""; km_str = ""
            try:
                dx_lat, dx_lon = self._cluster_get_latlon(call)
                if dx_lat is not None:
                    dx_grid = self._latlon_to_grid(dx_lat, dx_lon)
                    dist_km, bearing = calculate_dist_bearing(MY_GRID, dx_grid)
                    if dist_km:
                        az_str = f"{int(bearing)}°"
                        km_str = f"{dist_km}"
            except: pass

            age_sec = (now - ts).total_seconds()
            age_str = self._age_str(age_sec)
            age_tag = "age_new" if age_sec < 300 else "age_mid" if age_sec < 900 else "age_old"
            tag = self._get_spot_tag(band, country, call) or age_tag
            if count % 2 == 1 and tag == age_tag: tag = "row_alt"

            self.tree_cl.insert("", "end",
                values=(time_z, age_str, freq, band, mode, cont,
                        country, call, az_str, km_str, spotter, source, comment),
                tags=(tag,))
            count += 1

        self.cluster_count_var.set(f"{count} spot{'s' if count != 1 else ''}")

    def _get_spot_tag(self, band, country, call):
        """Retourne le tag visuel prioritaire : watchlist > new_dxcc > alert."""
        # Watchlist — préfixes rares configurés (ex: 3B9, FT5, VK9X...)
        wl = getattr(self, "_cluster_watchlist", set())
        if wl:
            call_up = call.upper()
            for pfx in sorted(wl, key=len, reverse=True):   # plus long d'abord
                if call_up.startswith(pfx):
                    return "watchlist"
        # Nouveau DXCC (jamais travaillé)
        try:
            c = self.conn.cursor()
            worked = c.execute("SELECT COUNT(*) FROM qsos WHERE callsign LIKE ?",
                               (call[:4]+"%",)).fetchone()[0]
            if country and country != "Unknown" and worked == 0:
                return "new_dxcc"
        except: pass
        # Alerte bandes/pays configurées
        if (self._cluster_alert_bands and band.lower() in self._cluster_alert_bands) or \
           (self._cluster_alert_countries and country.lower() in self._cluster_alert_countries):
            return "alert"
        return None

    def _clear_cluster_filters(self):
        self.cluster_band_var.set("ALL")
        self.cluster_src_var.set("ALL")
        self.cluster_cont_var.set("ALL")
        self.cluster_mode_var.set("ALL")
        self.cluster_search_var.set("")
        self._apply_cluster_filter()

    def _export_cluster_csv(self):
        import csv as _csv
        fn = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile=f"spots_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not fn: return
        try:
            with open(fn, "w", newline="", encoding="utf-8") as f:
                w = _csv.writer(f)
                w.writerow(["UTC","Freq","Band","Mode","Cont","Pays","DX Call","Spotter","Source","Info"])
                for s in self._all_spots:
                    if not isinstance(s, dict): continue
                    w.writerow([s.get(k,"") for k in
                                ["time_z","freq","band","mode","continent","country","call","spotter","source","comment"]])
            messagebox.showinfo("CSV", f"✅ {len(self._all_spots)} spots exportés :\n{fn}")
        except Exception as e:
            messagebox.showerror("CSV", f"Erreur : {e}")

    def open_cluster_alert_config(self):
        """Fenêtre de configuration des alertes cluster."""
        win = tk.Toplevel(self.root)
        win.title("🔔 Configuration des alertes DX Cluster")
        win.geometry("480x420"); win.grab_set()
        frm = ttk.Frame(win, padding=20); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Bandes à surveiller (séparées par virgules) :", font=("Arial",10)).pack(anchor="w", pady=(0,3))
        ttk.Label(frm, text="Ex: 20m,15m,10m", foreground="gray", font=("Arial",9)).pack(anchor="w")
        e_bands = ttk.Entry(frm, width=40); e_bands.pack(fill="x", pady=(0,12))
        if CONF: e_bands.insert(0, CONF.get("DXCC","Alert_Bands",""))
        ttk.Label(frm, text="Pays à surveiller (séparés par virgules) :", font=("Arial",10)).pack(anchor="w", pady=(0,3))
        ttk.Label(frm, text="Ex: Japan,USA,Australia", foreground="gray", font=("Arial",9)).pack(anchor="w")
        e_countries = ttk.Entry(frm, width=40); e_countries.pack(fill="x", pady=(0,12))
        if CONF: e_countries.insert(0, CONF.get("DXCC","Alert_Countries",""))

        ttk.Label(frm, text="⭐ Watchlist — préfixes rares (séparés par virgules) :", font=("Arial",10)).pack(anchor="w", pady=(0,3))
        ttk.Label(frm, text="Ex: 3B9,FT5,VK9X,ZL9,VP6,KH1,E5,BS7,3Y",
                  foreground="gray", font=("Arial",9)).pack(anchor="w")
        e_watch = ttk.Entry(frm, width=40); e_watch.pack(fill="x", pady=(0,12))
        if CONF: e_watch.insert(0, CONF.get("DXCC","Watchlist",""))

        ttk.Label(frm, text="🟦 Nouveau DXCC  |  🟥 Alerte bande/pays  |  ⭐ Watchlist",
                  foreground="#aaa", font=("Arial",9)).pack(anchor="w", pady=5)
        def save():
            global CONF
            cfg = configparser.ConfigParser(); cfg.read(CONFIG_FILE)
            if not cfg.has_section("DXCC"): cfg.add_section("DXCC")
            cfg.set("DXCC","Alert_Bands",     e_bands.get().strip())
            cfg.set("DXCC","Alert_Countries", e_countries.get().strip())
            cfg.set("DXCC","Watchlist",       e_watch.get().strip())
            with open(CONFIG_FILE,"w") as f: cfg.write(f)
            load_config_safe(); self._load_cluster_filters()
            self.status_var.set("✅ Alertes cluster sauvegardées"); win.destroy()
        bf = ttk.Frame(win); bf.pack(fill="x", padx=20, pady=10)
        ttk.Button(bf, text="💾 Enregistrer", command=save, bootstyle="success", width=16).pack(side="left")
        ttk.Button(bf, text="✖ Annuler", command=win.destroy, bootstyle="secondary", width=12).pack(side="right")

    # ==========================================
    # --- ONGLET SPOT HISTORY ---
    # ==========================================
    def _build_spot_history_tab(self, parent):
        """Historique des spots DX cluster par entité DXCC — session courante."""
        BG = "#11273f"

        # ── Barre de contrôle ─────────────────────────────────────────────────
        ctrl = tk.Frame(parent, bg=BG); ctrl.pack(fill="x", padx=6, pady=4)

        tk.Label(ctrl, text="🔍 Entité / Callsign :", bg=BG, fg="white",
                 font=("Arial",10)).pack(side="left")
        self._sh_search_var = tk.StringVar()
        sh_entry = ttk.Entry(ctrl, textvariable=self._sh_search_var, width=20)
        sh_entry.pack(side="left", padx=6)
        sh_entry.bind("<KeyRelease>", lambda e: self._sh_filter())

        tk.Label(ctrl, text="Bande:", bg=BG, fg="white").pack(side="left", padx=(10,3))
        self._sh_band_var = tk.StringVar(value="ALL")
        ttk.Combobox(ctrl, textvariable=self._sh_band_var, width=7,
                     values=["ALL","160m","80m","60m","40m","30m","20m","17m","15m","12m","10m","6m","2m"]
                     ).pack(side="left")
        self._sh_band_var.trace_add("write", lambda *_: self._sh_filter())

        ttk.Button(ctrl, text="🔄 Rafraîchir", command=self._sh_filter,
                   bootstyle="primary").pack(side="left", padx=10)

        self._sh_count_var = tk.StringVar(value="0 spots")
        tk.Label(ctrl, textvariable=self._sh_count_var, bg=BG, fg="#f39c12",
                 font=("Consolas",10,"bold")).pack(side="right", padx=10)

        # ── Treeview ──────────────────────────────────────────────────────────
        cols = ("Heure UTC","Age","Freq kHz","Bande","Mode","Pays","Callsign","Spotter","Source","Commentaire")
        self._sh_tree = ttk.Treeview(parent, columns=cols, show="headings",
                                     style="Cluster.Treeview", selectmode="browse")
        widths = [65,55,80,55,55,140,100,100,75,200]
        for col, w in zip(cols, widths):
            self._sh_tree.heading(col, text=col)
            self._sh_tree.column(col, width=w, minwidth=40)

        vsb = ttk.Scrollbar(parent, orient="vertical",   command=self._sh_tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self._sh_tree.xview)
        self._sh_tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self._sh_tree.pack(side="left", fill="both", expand=True, padx=(6,0), pady=4)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")

        # Tags couleur identiques au cluster
        for band, color in {"160m":"#ff4444","80m":"#ff8800","40m":"#88ff00",
                             "20m":"#00ccff","15m":"#aa44ff","10m":"#ff0066",
                             "6m":"#ffffff","2m":"#aaaaaa"}.items():
            self._sh_tree.tag_configure(band, foreground=color)

        # Clic droit identique au cluster
        self._sh_tree.bind("<Button-3>", self._sh_right_click)
        self._sh_tree.bind("<Double-1>", self._sh_double_click)

        # Bouton Logger en bas
        bot = tk.Frame(parent, bg=BG); bot.pack(fill="x", padx=6, pady=2)
        tk.Label(bot, text="Double-clic = syntoniser  |  Clic droit = Logger / QRZ",
                 bg=BG, fg="#555", font=("Arial",8)).pack(side="left")
        ttk.Button(bot, text="🗑️ Vider session", bootstyle="danger-outline",
                   command=self._sh_clear).pack(side="right", padx=4)

        self._sh_filter()

    def _sh_filter(self):
        """Rafraîchit le Spot History selon les filtres."""
        if not hasattr(self, '_sh_tree'):
            return
        search = self._sh_search_var.get().strip().upper()
        band_f = self._sh_band_var.get()
        for item in self._sh_tree.get_children():
            self._sh_tree.delete(item)

        now = datetime.now(timezone.utc)
        count = 0
        for spot in self._all_spots:
            if not isinstance(spot, dict): continue
            call    = spot.get("call", "")
            country = spot.get("country", "")
            band    = spot.get("band", "")
            mode    = spot.get("mode", "")
            freq    = spot.get("freq", "")
            spotter = spot.get("spotter", "")
            source  = spot.get("source", "")
            comment = spot.get("comment", "")
            time_z  = spot.get("time_z", "")
            ts      = spot.get("ts", now)

            if band_f != "ALL" and band.lower() != band_f.lower(): continue
            if search and not any(search in x.upper() for x in [call, country, spotter, comment]): continue

            age_sec = (now - ts).total_seconds()
            age_str = f"{int(age_sec//60)}m" if age_sec < 3600 else f"{int(age_sec//3600)}h{int((age_sec%3600)//60)}m"

            tag = band if band in ("160m","80m","40m","20m","15m","10m","6m","2m") else ""
            self._sh_tree.insert("", "end",
                values=(time_z, age_str, freq, band, mode, country, call, spotter, source, comment),
                tags=(tag,))
            count += 1

        self._sh_count_var.set(f"{count} spot{'s' if count != 1 else ''}")

    def _sh_right_click(self, event):
        row = self._sh_tree.identify_row(event.y)
        if not row: return
        self._sh_tree.selection_set(row)
        vals = self._sh_tree.item(row)["values"]
        if not vals or len(vals) < 7: return
        freq, band, mode, country, call = vals[2], vals[3], vals[4], vals[5], vals[6]
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"📋 Logger {call}  [{band} {mode}]",
                         command=lambda: self._prefill_from_spot(call, freq, mode, country))
        menu.add_command(label=f"📻 Syntoniser → {freq} kHz",
                         command=lambda: self._tune_spot_freq(freq, mode))
        menu.add_command(label=f"🔍 QRZ.com : {call}",
                         command=lambda: __import__('webbrowser').open(f"https://www.qrz.com/db/{call}"))
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    def _sh_double_click(self, event):
        sel = self._sh_tree.selection()
        if sel:
            freq = self._sh_tree.item(sel[0])["values"][2]
            mode = self._sh_tree.item(sel[0])["values"][4]
            self._tune_spot_freq(str(freq), str(mode))

    def _sh_clear(self):
        self._all_spots.clear()
        self._sh_filter()
        if hasattr(self, '_apply_cluster_filter'):
            self._apply_cluster_filter()

    # ==========================================
    # --- ONGLET STATISTIQUES ---
    # ==========================================
    def _build_stats_tab(self, parent):
        BG = "#11273f"
        btn_fr = tk.Frame(parent, bg=BG); btn_fr.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_fr, text="🔄 Actualiser", command=self.update_stats_view, bootstyle="primary").pack(side="left", padx=5)
        ttk.Button(btn_fr, text="📋 Copier rapport", command=self._copy_stats, bootstyle="secondary-outline").pack(side="left", padx=5)
        self.txt_stats = tk.Text(parent, font=("Consolas", 11), bg=BG, fg="white",
                                 insertbackground="white", selectbackground="#1a5276",
                                 padx=20, pady=20, relief="flat", borderwidth=0)
        self.txt_stats.pack(fill="both", expand=True)

    def update_stats_view(self):
        self.txt_stats.delete("1.0", tk.END); c = self.conn.cursor()
        lines = [f"=== RAPPORT DE STATION {MY_CALL} ===",
                 f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

        # Total
        total = c.execute("SELECT COUNT(*) FROM qsos").fetchone()[0]
        lines.append(f"📊 TOTAL QSOs : {total}")
        lines.append("")

        # Par bande
        lines.append("🎚️ CONTACTS PAR BANDE :")
        lines.append("=" * 30)
        bands = ["160M","80M","60M","40M","30M","20M","17M","15M","12M","10M","6M"]
        for b in bands:
            count = c.execute("SELECT COUNT(*) FROM qsos WHERE UPPER(band)=?", (b,)).fetchone()[0]
            if count > 0:
                bar = "█" * min(count // max(1, total // 30), 30)
                lines.append(f"{b:<5} : {count:<5} {bar}")

        # Par mode
        lines.append("")
        lines.append("📻 CONTACTS PAR MODE :")
        lines.append("=" * 30)
        for row in c.execute("SELECT mode, COUNT(*) as n FROM qsos GROUP BY mode ORDER BY n DESC"):
            lines.append(f"{row[0]:<8}: {row[1]}")

        # Par mois (12 derniers)
        lines.append("")
        lines.append("📅 QSOs PAR MOIS (12 derniers) :")
        lines.append("=" * 30)
        for row in c.execute("""
            SELECT substr(qso_date,1,7) as ym, COUNT(*) as n 
            FROM qsos GROUP BY ym ORDER BY ym DESC LIMIT 12"""):
            bar = "█" * min(row[1] // max(1, total // 50), 20)
            lines.append(f"{row[0]} : {row[1]:<5} {bar}")

        # Top 15 pays
        lines.append("")
        lines.append("🏆 TOP 15 PAYS (DXCC Estimé) :")
        lines.append("-" * 30)
        calls = c.execute("SELECT callsign FROM qsos").fetchall()
        countries = {}
        for row in calls:
            cn = get_country_name(row[0])
            if cn: countries[cn] = countries.get(cn, 0) + 1
        medals = ["🥇","🥈","🥉"]
        for idx, (name, cnt) in enumerate(sorted(countries.items(), key=lambda x: x[1], reverse=True)[:15]):
            prefix = medals[idx] if idx < 3 else f"#{idx+1} "
            lines.append(f"{prefix:<4} {name:<22}: {cnt}")

        # Top distances
        lines.append("")
        lines.append("📡 TOP 5 DISTANCES :")
        lines.append("-" * 30)
        for row in c.execute("SELECT callsign, qso_date, grid FROM qsos WHERE grid != '' ORDER BY CAST(distance AS INTEGER) DESC LIMIT 5"):
            d, _ = calculate_dist_bearing(MY_GRID, row[2])
            if d: lines.append(f"  {row[0]:<12} {row[1]}  {d} km")

        self.txt_stats.insert(tk.END, "\n".join(lines))

    def _copy_stats(self):
        content = self.txt_stats.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_var.set("📋 Rapport copié dans le presse-papier")

    def _check_duplicate(self, event=None):
        """Vérifie en temps réel si le callsign a déjà été travaillé."""
        call = self.e_call.get().strip().upper()
        if not call or len(call) < 3:
            self.lbl_dup.config(text="", foreground="#3fb950")
            return
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT band, mode, qso_date FROM qsos WHERE callsign=? ORDER BY qso_date DESC",
            (call,)).fetchall()
        if not rows:
            self.lbl_dup.config(text=f"✅ {call} — Premier QSO !", foreground="#3fb950")
            return
        band_modes = {}
        for band, mode, date in rows:
            key = band or "?"
            if key not in band_modes: band_modes[key] = []
            if (mode or "?") not in band_modes[key]: band_modes[key].append(mode or "?")
        summary = "  |  ".join(f"{b}: {', '.join(m)}" for b, m in sorted(band_modes.items()))
        last_date = rows[0][2] if rows else ""
        n = len(rows)
        current_band = freq_to_band(self.current_freq_hz)
        same_band = [r for r in rows if r[0] == current_band]
        if same_band:
            self.lbl_dup.config(
                text=f"⚠️ DOUBLON  {call} — {n} QSO(s) dont {len(same_band)} sur {current_band}  [{summary}]  Dernier: {last_date}",
                foreground="#f85149")
        else:
            self.lbl_dup.config(
                text=f"🔄 Déjà travaillé  {call} — {n} QSO(s) — Bandes: {summary}  Dernier: {last_date}  ➜ Nouvelle bande possible sur {current_band}",
                foreground="#f39c12")

    # ==========================================
    # --- ONGLET GRAPHIQUES ---
    # ==========================================
    def _build_graphs_tab(self, parent):
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            self._matplotlib_ok = True
        except ImportError:
            self._matplotlib_ok = False
            ttk.Label(parent, text="⚠️ matplotlib non installé.\nInstallez-le avec : pip install matplotlib",
                      font=("Arial",14), justify="center").pack(expand=True)
            return

        ctrl = tk.Frame(parent, bg="#11273f"); ctrl.pack(fill="x")
        ttk.Label(ctrl, text="Type de graphique:").pack(side="left", padx=5)
        self.graph_type_var = tk.StringVar(value="QSOs par mois")
        types = ["QSOs par mois","QSOs par bande","QSOs par mode","Activité par heure","Progression DXCC"]
        cb = ttk.Combobox(ctrl, textvariable=self.graph_type_var, values=types, width=22)
        cb.pack(side="left", padx=5)
        ttk.Button(ctrl, text="📊 Générer", command=self._draw_graph, bootstyle="primary").pack(side="left", padx=5)

        self._graph_frame = tk.Frame(parent, bg="#11273f"); self._graph_frame.pack(fill="both", expand=True)

    def _draw_graph(self):
        if not getattr(self, '_matplotlib_ok', False): return
        import matplotlib
        matplotlib.use("TkAgg")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        # Nettoyer le frame
        for w in self._graph_frame.winfo_children(): w.destroy()

        c = self.conn.cursor()
        graph_type = self.graph_type_var.get()

        fig = Figure(figsize=(10, 5), dpi=100, facecolor='#11273f')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#11273f')
        ax.tick_params(colors='white'); ax.xaxis.label.set_color('white'); ax.yaxis.label.set_color('white')
        ax.title.set_color('#f39c12')
        for spine in ax.spines.values(): spine.set_edgecolor('#445566')

        if graph_type == "QSOs par mois":
            rows = c.execute("""
                SELECT substr(qso_date,1,7) as ym, COUNT(*) as n
                FROM qsos WHERE qso_date != ''
                GROUP BY ym ORDER BY ym DESC LIMIT 24""").fetchall()
            if rows:
                rows = list(reversed(rows))
                labels = [r[0] for r in rows]; values = [r[1] for r in rows]
                bars = ax.bar(range(len(labels)), values, color='#3498db', edgecolor='#2980b9')
                ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8, color='white')
                for bar, val in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, str(val), ha='center', va='bottom', fontsize=7, color='white')
                ax.set_title("QSOs par mois (24 derniers)", color='#f39c12', fontsize=13)
                ax.set_ylabel("Nombre de QSOs", color='white')

        elif graph_type == "QSOs par bande":
            rows = c.execute("SELECT band, COUNT(*) as n FROM qsos GROUP BY band ORDER BY n DESC").fetchall()
            if rows:
                labels = [r[0] or "?" for r in rows]; values = [r[1] for r in rows]
                colors = ['#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6','#1abc9c','#e67e22','#34495e','#e91e63','#00bcd4','#8bc34a']
                wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                                    colors=colors[:len(values)], startangle=90,
                                                    textprops={'color':'white'})
                for at in autotexts: at.set_fontsize(8)
                ax.set_title("Répartition par bande", color='#f39c12', fontsize=13)

        elif graph_type == "QSOs par mode":
            rows = c.execute("SELECT mode, COUNT(*) as n FROM qsos GROUP BY mode ORDER BY n DESC").fetchall()
            if rows:
                labels = [r[0] or "?" for r in rows]; values = [r[1] for r in rows]
                colors = ['#2ecc71','#3498db','#e74c3c','#f39c12','#9b59b6','#1abc9c']
                bars = ax.barh(range(len(labels)), values, color=colors[:len(values)])
                ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, color='white')
                for bar, val in zip(bars, values):
                    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2, str(val), va='center', color='white', fontsize=9)
                ax.set_title("QSOs par mode", color='#f39c12', fontsize=13)
                ax.set_xlabel("Nombre de QSOs", color='white')

        elif graph_type == "Activité par heure":
            rows = c.execute("SELECT substr(time_on,1,2) as h, COUNT(*) as n FROM qsos WHERE time_on != '' GROUP BY h ORDER BY h").fetchall()
            if rows:
                hours = [int(r[0]) for r in rows if r[0].isdigit()]; counts = [r[1] for r in rows if r[0].isdigit()]
                ax.bar(hours, counts, color='#f39c12', edgecolor='#e67e22', width=0.8)
                ax.set_xticks(range(0, 24)); ax.set_xticklabels([f"{h:02d}h" for h in range(24)], rotation=45, color='white', fontsize=8)
                ax.set_title("Activité UTC par heure", color='#f39c12', fontsize=13)
                ax.set_ylabel("Nombre de QSOs", color='white')
                ax.set_xlabel("Heure UTC", color='white')

        elif graph_type == "Progression DXCC":
            rows = c.execute("SELECT qso_date, callsign FROM qsos WHERE qso_date != '' ORDER BY qso_date").fetchall()
            if rows:
                seen = set(); dates_new = []; cumul = []
                cnt = 0
                for date, call in rows:
                    entity = get_country_name(call)
                    if entity and entity not in seen:
                        seen.add(entity); cnt += 1
                        dates_new.append(date); cumul.append(cnt)
                if dates_new:
                    step = max(1, len(dates_new) // 50)
                    xs = list(range(len(dates_new)))
                    ax.plot(xs, cumul, color='#2ecc71', linewidth=2)
                    ax.fill_between(xs, cumul, alpha=0.3, color='#2ecc71')
                    tick_positions = range(0, len(dates_new), max(1, len(dates_new)//10))
                    ax.set_xticks(list(tick_positions))
                    ax.set_xticklabels([dates_new[i][:7] for i in tick_positions], rotation=45, ha='right', color='white', fontsize=8)
                    ax.set_title(f"Progression DXCC — {cnt} entités", color='#f39c12', fontsize=13)
                    ax.set_ylabel("Entités DXCC cumulées", color='white')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self._graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ==========================================
    # --- ONGLET PROPAGATION ---
    # ==========================================
    def _build_propagation_tab(self, parent):
        # Panneau gauche : données solaires et conditions de propagation
        paned = tk.PanedWindow(parent, orient="horizontal", sashrelief="raised", sashwidth=6, bg="#11273f")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, padding=10); paned.add(left, minsize=320)
        right = ttk.Frame(paned, padding=10); paned.add(right, minsize=400)

        # --- Gauche : données + greyline info ---
        ttk.Label(left, text="🌞 DONNÉES SOLAIRES", font=("Consolas",13,"bold"), foreground="#f39c12").pack(anchor="w", pady=(0,8))

        btn_fr = tk.Frame(left, bg="#11273f"); btn_fr.pack(fill="x", pady=5)
        ttk.Button(btn_fr, text="🔄 Actualiser", command=self._refresh_propagation, bootstyle="primary").pack(side="left")
        ttk.Button(btn_fr, text="🌐 DX Maps", command=lambda: __import__('webbrowser').open("https://www.dxmaps.com/spots/mapg.php?Lan=E&Frec=28.0&ML=M&Map=EU&HF=1"), bootstyle="info-outline").pack(side="left", padx=5)
        ttk.Button(btn_fr, text="📡 VOACAP", command=lambda: __import__('webbrowser').open("https://www.voacap.com/hf/"), bootstyle="secondary-outline").pack(side="left", padx=5)
        ttk.Button(btn_fr, text="🎯 VOACAP P2P", command=self._open_voacap_p2p, bootstyle="warning-outline").pack(side="left", padx=5)

        self.prop_data_frame = tk.Frame(left, bg="#11273f"); self.prop_data_frame.pack(fill="x", pady=10)
        self.prop_labels = {}
        for key in ["SFI","SN","K-index","A-index","Conditions","Hémisphère N","Hémisphère S"]:
            f = ttk.Frame(self.prop_data_frame); f.pack(fill="x", pady=2)
            ttk.Label(f, text=f"{key}:", width=16, anchor="e", foreground="#888").pack(side="left")
            lbl = ttk.Label(f, text="--", font=("Consolas",11,"bold"), foreground="white")
            lbl.pack(side="left", padx=8)
            self.prop_labels[key] = lbl

        ttk.Separator(left).pack(fill="x", pady=10)

        # Greyline
        ttk.Label(left, text="🌓 GREYLINE", font=("Consolas",12,"bold"), foreground="#3daee9").pack(anchor="w")
        self.prop_greyline_var = tk.StringVar(value="Calcul en cours...")
        ttk.Label(left, textvariable=self.prop_greyline_var, font=("Consolas",10), foreground="#3daee9", wraplength=300, justify="left").pack(anchor="w", pady=5)

        ttk.Separator(left).pack(fill="x", pady=10)

        # Tableau des bandes (conditions)
        ttk.Label(left, text="📻 CONDITIONS PAR BANDE", font=("Consolas",12,"bold"), foreground="#3fb950").pack(anchor="w", pady=(5,3))
        self.band_cond_frame = tk.Frame(left, bg="#11273f"); self.band_cond_frame.pack(fill="x")

        ttk.Separator(left).pack(fill="x", pady=8)

        # --- VOACAP P2P intégré ---
        ttk.Label(left, text="🎯 VOACAP POINT À POINT", font=("Consolas",11,"bold"), foreground="#f39c12").pack(anchor="w")
        voa_fr = tk.Frame(left, bg="#11273f"); voa_fr.pack(fill="x", pady=4)
        ttk.Label(voa_fr, text="Dest (call/pays):").pack(side="left")
        self._voacap_dest_var = tk.StringVar(value="JA1AAA")
        ttk.Entry(voa_fr, textvariable=self._voacap_dest_var, width=12).pack(side="left", padx=4)
        ttk.Button(voa_fr, text="🌐 Ouvrir VOACAP", command=self._open_voacap_p2p,
                   bootstyle="warning").pack(side="left", padx=4)
        voa_tip = tk.Frame(left, bg="#11273f"); voa_tip.pack(fill="x")
        ttk.Label(voa_tip, text="Entrez l'indicatif de destination → lookup coords → VOACAP dans le navigateur",
                  font=("Arial",8), foreground="#888", wraplength=290, justify="left").pack(anchor="w")

        # --- Droite : graphique MUF / ionosphère ---
        ttk.Label(right, text="🔭 IONOSPHÈRE / MUF", font=("Consolas",13,"bold"), foreground="#3fb950").pack(anchor="w", pady=(0,5))

        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            self._prop_fig = Figure(figsize=(7, 5), dpi=90, facecolor='#11273f')
            self._prop_canvas = FigureCanvasTkAgg(self._prop_fig, master=right)
            self._prop_canvas.get_tk_widget().pack(fill="both", expand=True)
            self._prop_matplotlib_ok = True
        except ImportError:
            self._prop_matplotlib_ok = False
            ttk.Label(right, text="⚠️ matplotlib requis pour les graphiques", foreground="gray").pack(expand=True)

        # Démarrer la mise à jour automatique après 1s (widgets déjà créés)
        self.root.after(1000, self._refresh_propagation)

    def _refresh_propagation(self):
        threading.Thread(target=self._fetch_propagation_data, daemon=True).start()

    def _fetch_propagation_data(self):
        try:
            resp = requests.get("https://www.hamqsl.com/solarxml.php", timeout=10)
            root = ET.fromstring(resp.content)
            sol = root.find('solardata')
            if sol is None: return

            def txt(tag):
                el = sol.find(tag); return el.text.strip() if el is not None and el.text else "--"

            sfi = txt('solarflux'); sn = txt('sunspots')
            k = txt('kindex'); a = txt('aindex')
            nh = txt('calculatedconditions/band[@name="80m-40m"]') if sol.find('calculatedconditions') is not None else "--"

            data = {
                'SFI': sfi, 'SN': sn, 'K-index': k, 'A-index': a,
                'Conditions': self._k_to_condition(k),
            }

            # Conditions par bande depuis le XML
            cond_node = sol.find('calculatedconditions')
            band_data = {}
            if cond_node is not None:
                for band in cond_node.findall('band'):
                    name = band.get('name',''); time_v = band.get('time','')
                    val = band.text.strip() if band.text else "?"
                    key = f"{name} ({time_v})"
                    band_data[key] = val

            cond_vhf = sol.find('calculatedvhfconditions')
            vhf_data = {}
            if cond_vhf is not None:
                for ph in cond_vhf.findall('phenomenon'):
                    name = ph.get('name',''); location = ph.get('location','')
                    val = ph.text.strip() if ph.text else "?"
                    vhf_data[f"{name} ({location})"] = val

            # Données hémisphères
            data['Hémisphère N'] = ""
            data['Hémisphère S'] = ""
            for k_bd, v_bd in band_data.items():
                if 'day' in k_bd.lower() and '20m' in k_bd.lower():
                    data['Hémisphère N'] = v_bd; break

            try:
                self.root.after(0, lambda: self._update_prop_ui(data, band_data, vhf_data))
            except RuntimeError: pass
        except Exception as e:
            print(f"Propagation fetch error: {e}")
            try:
                self.root.after(0, lambda: self.status_var.set("⚠️ Erreur lecture données propagation"))
            except RuntimeError: pass

    def _k_to_condition(self, k_str):
        try:
            k = float(k_str)
            if k <= 1: return "🟢 Excellent"
            elif k <= 2: return "🟢 Bon"
            elif k <= 3: return "🟡 Normal"
            elif k <= 4: return "🟡 Dégradé"
            elif k <= 5: return "🔴 Mauvais"
            else: return "🔴 Tempête géomagnétique"
        except: return "--"

    def _update_prop_ui(self, data, band_data, vhf_data):
        """Met à jour tous les labels de propagation."""
        color_map = {
            'Excellent': '#2ecc71', 'Good': '#2ecc71', 'Bon': '#2ecc71',
            'Fair': '#f39c12', 'Normal': '#f39c12',
            'Poor': '#e74c3c', 'Mauvais': '#e74c3c', 'Dégradé': '#e67e22'
        }

        for key, lbl in self.prop_labels.items():
            val = data.get(key, "--")
            color = "white"
            for cw, cv in color_map.items():
                if cw.lower() in val.lower(): color = cv; break
            lbl.config(text=val, foreground=color)

        # Greyline
        now = datetime.now(timezone.utc)
        sunrise_utc, sunset_utc = self._calc_greyline_times()
        gl_text = (f"📍 Station: {MY_CALL} ({MY_GRID})\n"
                   f"🌅 Lever local: {sunrise_utc} UTC\n"
                   f"🌇 Coucher local: {sunset_utc} UTC\n"
                   f"⏰ Maintenant: {now.strftime('%H:%M')} UTC  {get_day_night_status()}\n\n"
                   f"💡 Greyline = ±30 min lever/coucher\n"
                   f"    Bandes favorables: 160m, 80m, 40m")
        self.prop_greyline_var.set(gl_text)

        # Conditions par bande
        for w in self.band_cond_frame.winfo_children(): w.destroy()
        for key, val in list(band_data.items())[:16]:
            f = ttk.Frame(self.band_cond_frame); f.pack(fill="x", pady=1)
            color = color_map.get(val, "white")
            ttk.Label(f, text=key, width=22, anchor="e", foreground="#888", font=("Arial",9)).pack(side="left")
            ttk.Label(f, text=val, foreground=color, font=("Arial",9,"bold")).pack(side="left", padx=5)

        # Graphique MUF si matplotlib dispo
        if getattr(self, '_prop_matplotlib_ok', False):
            self._draw_muf_chart(data)

    def _open_voacap_p2p(self):
        """Ouvre VOACAP Point-à-Point dans le navigateur avec les coordonnées ON5AM → destination."""
        import webbrowser
        dest_call = getattr(self, '_voacap_dest_var', None)
        dest_call = dest_call.get().strip().upper() if dest_call else ""

        # Coords ON5AM (émetteur)
        home = grid_to_latlon(MY_GRID) or (50.655, 5.548)
        tx_lat, tx_lon = home

        # Coords destination : chercher dans cty.dat
        rx_lat, rx_lon = None, None
        if dest_call:
            country = get_country_name(dest_call)
            cty_path = CTY_FILE
            try:
                with open(cty_path, encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                for record in text.split(";"):
                    for line in record.strip().splitlines():
                        if line and not line[0].isspace() and ":" in line:
                            parts = line.split(":")
                            if len(parts) >= 6 and parts[0].strip() == country:
                                rx_lat =  float(parts[4].strip())
                                rx_lon = -float(parts[5].strip())
                            break
                    if rx_lat is not None:
                        break
            except Exception:
                pass

        if rx_lat is None:
            # Fallback : Japon si aucune correspondance
            rx_lat, rx_lon = 35.68, 139.69
            messagebox.showinfo("VOACAP",
                f"Pays de {dest_call} non trouvé dans cty.dat.\nUtilisation du Japon par défaut.")

        now = datetime.now(timezone.utc)
        ssn = 120  # valeur par défaut; sera affinée si SFI disponible
        try:
            sfi_txt = self.prop_labels.get("SFI", None)
            if sfi_txt:
                sfi_val = float(sfi_txt.cget("text"))
                ssn = max(0, int((sfi_val - 65) / 0.7))
        except Exception:
            pass

        url = (f"https://www.voacap.com/p2p/"
               f"?txlat={tx_lat:.3f}&txlng={tx_lon:.3f}"
               f"&rxlat={rx_lat:.3f}&rxlng={rx_lon:.3f}"
               f"&month={now.month}&ssn={ssn}&mode=17&power=100&freq=0")
        webbrowser.open(url)
        self.status_var.set(f"🌐 VOACAP ouvert : {MY_CALL} → {dest_call or 'JA'}  SSN={ssn}")

    def _calc_greyline_times(self):
        """Calcul approximatif lever/coucher solaire pour MY_GRID."""
        pos = grid_to_latlon(MY_GRID)
        if not pos: return "--:--", "--:--"
        lat, lon = pos
        now = datetime.now(timezone.utc)
        doy = now.timetuple().tm_yday
        # Déclinaison solaire
        decl = math.radians(23.45 * math.sin(math.radians(360/365 * (doy - 81))))
        try:
            cos_ha = -math.tan(math.radians(lat)) * math.tan(decl)
            if cos_ha < -1: return "00:00","23:59"  # soleil permanent
            if cos_ha > 1: return "--:--","--:--"   # nuit permanente
            ha = math.degrees(math.acos(cos_ha))
            lon_offset = lon / 15.0
            sunrise = (12 - ha/15 - lon_offset) % 24
            sunset  = (12 + ha/15 - lon_offset) % 24
            return f"{int(sunrise):02d}:{int((sunrise%1)*60):02d}", f"{int(sunset):02d}:{int((sunset%1)*60):02d}"
        except: return "--:--", "--:--"

    def _draw_muf_chart(self, data):
        """Dessine un graphique de prévision MUF/bandes selon SFI."""
        from matplotlib.figure import Figure
        self._prop_fig.clear()
        ax = self._prop_fig.add_subplot(111)
        ax.set_facecolor('#11273f')
        self._prop_fig.set_facecolor('#11273f')
        ax.tick_params(colors='white'); ax.xaxis.label.set_color('white'); ax.yaxis.label.set_color('white')
        for spine in ax.spines.values(): spine.set_edgecolor('#445566')

        try:
            sfi = float(data.get('SFI', 70))
            k = float(data.get('K-index', 2))
        except: sfi = 70; k = 2

        # Estimation MUF approximative selon l'heure UTC
        hours = list(range(0, 25))
        # Modèle simplifié : MUF varie avec SFI et l'heure
        muf_day = []
        for h in hours:
            base = 8 + (sfi - 60) * 0.15
            # Pic au midi solaire
            factor = 1.0 + 0.7 * math.sin(math.pi * (h - 6) / 12) if 6 <= h <= 18 else 0.5
            k_penalty = max(0, (k - 2) * 1.5)
            muf = max(3, base * factor - k_penalty)
            muf_day.append(muf)

        ax.plot(hours, muf_day, color='#f39c12', linewidth=2, label='MUF estimée (MHz)')
        ax.fill_between(hours, muf_day, alpha=0.2, color='#f39c12')

        # Lignes de référence des bandes
        band_freqs = [(3.7, "80m", "#e74c3c"), (7.1, "40m", "#e67e22"),
                      (14.2, "20m", "#2ecc71"), (21.2, "15m", "#3498db"),
                      (28.4, "10m", "#9b59b6")]
        for freq, name, color in band_freqs:
            ax.axhline(y=freq, color=color, linestyle='--', linewidth=1, alpha=0.7)
            ax.text(23.5, freq+0.3, name, color=color, fontsize=8, ha='right')

        ax.set_xticks(range(0, 25, 2))
        ax.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 2)], color='white', fontsize=8)
        ax.tick_params(axis='y', colors='white')   # couleur des yticks sans UserWarning
        ax.set_xlabel("Heure UTC", color='white')
        ax.set_ylabel("Fréquence (MHz)", color='white')
        now_h = datetime.now(timezone.utc).hour + datetime.now(timezone.utc).minute/60
        ax.axvline(x=now_h, color='white', linestyle=':', linewidth=1.5, label='Maintenant')
        ax.set_title(f"MUF estimée — SFI={data.get('SFI','?')} K={data.get('K-index','?')}", color='#f39c12', fontsize=11)
        ax.legend(loc='upper left', facecolor='#11273f', labelcolor='white', fontsize=8)
        self._prop_fig.tight_layout()
        self._prop_canvas.draw()

    # ==========================================
    # --- AWARDS / MÉMOIRES — données de classe ---
    # ==========================================

    # Zones WAZ (CQ zones) par entité DXCC (simplifié)
    WAZ_ZONES = {
        "Belgium":14,"France":14,"Germany":14,"England":14,"Italy":15,"Spain":14,
        "Portugal":14,"Netherlands":14,"Switzerland":14,"Austria":15,"Denmark":14,
        "Norway":14,"Sweden":18,"Finland":18,"Iceland":40,"Ireland":14,
        "Poland":15,"Czech Rep.":15,"Slovakia":15,"Hungary":15,"Romania":20,
        "Bulgaria":20,"Greece":20,"Croatia":15,"Slovenia":15,"Turkey":20,
        "Russia (EU)":16,"Russia (AS)":17,"Ukraine":16,"Belarus":16,
        "Japan":25,"China":24,"South Korea":25,"Taiwan":24,"India":26,
        "Australia":29,"New Zealand":32,"USA":3,"Canada":4,"Mexico":6,
        "Brazil":11,"Argentina":13,"Chile":12,"Colombia":9,"Venezuela":9,
        "South Africa":38,"Kenya":34,"Nigeria":35,"Egypt":33,"Morocco":33,
        "Saudi Arabia":21,"Israel":20,"Iran":21,"Pakistan":21,
    }

    # États USA pour WAS
    USA_STATES = [
        "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
        "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa",
        "Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan",
        "Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada",
        "New Hampshire","New Jersey","New Mexico","New York","North Carolina",
        "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island",
        "South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
        "Virginia","Washington","West Virginia","Wisconsin","Wyoming"
    ]

    # Mémoires fréquences par défaut
    DEFAULT_MEMORIES = [
        ("14.074", "FT8 20m", "20m", "FT8"),
        ("14.225", "SSB 20m", "20m", "SSB"),
        ("14.195", "DX SSB 20m", "20m", "SSB"),
        ("7.074",  "FT8 40m", "40m", "FT8"),
        ("7.150",  "SSB 40m", "40m", "SSB"),
        ("3.573",  "FT8 80m", "80m", "FT8"),
        ("3.750",  "SSB 80m", "80m", "SSB"),
        ("21.074", "FT8 15m", "15m", "FT8"),
        ("21.300", "SSB 15m", "15m", "SSB"),
        ("28.074", "FT8 10m", "10m", "FT8"),
        ("28.400", "SSB 10m", "10m", "SSB"),
        ("10.136", "FT8 30m", "30m", "FT8"),
        ("18.100", "FT8 17m", "17m", "FT8"),
        ("24.915", "FT8 12m", "12m", "FT8"),
        ("50.313", "FT8 6m",  "6m",  "FT8"),
        ("50.150", "SSB 6m",  "6m",  "SSB"),
        ("1.840",  "FT8 160m","160m","FT8"),
        ("7.040",  "CW 40m",  "40m", "CW"),
        ("14.040", "CW 20m",  "20m", "CW"),
        ("21.040", "CW 15m",  "15m", "CW"),
        ("7.043",  "FT4 40m", "40m", "FT4"),
        ("14.080", "PSK31 20m","20m","DIG"),
        ("14.230", "SSTV 20m","20m", "DIG"),
        ("145.500","FM 2m",   "2m",  "FM"),
    ]

    # ==========================================
    # --- MÉMOIRES FRÉQUENCES ---
    # ==========================================

    def _build_memories_tab(self, parent):
        self.conn.cursor().execute("""
            CREATE TABLE IF NOT EXISTS freq_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                freq TEXT NOT NULL,
                label TEXT NOT NULL,
                band TEXT DEFAULT '',
                mode TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0
            )""")
        self.conn.commit()
        self._ensure_default_memories()

        ctrl = tk.Frame(parent, bg="#11273f"); ctrl.pack(fill="x")
        ttk.Label(ctrl, text="Ajouter mémoire :").pack(side="left", padx=5)
        self.mem_freq_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self.mem_freq_var, width=10,
                  font=("Consolas",11)).pack(side="left", padx=3)
        ttk.Label(ctrl, text="MHz  Libellé:").pack(side="left", padx=2)
        self.mem_label_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self.mem_label_var, width=16).pack(side="left", padx=3)
        ttk.Label(ctrl, text="Mode:").pack(side="left", padx=2)
        self.mem_mode_var = tk.StringVar(value="SSB")
        ttk.Combobox(ctrl, textvariable=self.mem_mode_var,
                     values=["SSB","CW","FT8","FT4","DIG","FM","AM"], width=6).pack(side="left", padx=3)
        ttk.Button(ctrl, text="➕ Ajouter", command=self._add_memory,
                   bootstyle="success").pack(side="left", padx=5)
        ttk.Button(ctrl, text="❌ Supprimer sélection", command=self._del_memory,
                   bootstyle="danger-outline").pack(side="left", padx=5)
        ttk.Button(ctrl, text="🔄 Restaurer défauts", command=self._restore_default_memories,
                   bootstyle="secondary-outline").pack(side="left", padx=5)

        self.mem_btn_frame = tk.Frame(parent, bg="#11273f"); self.mem_btn_frame.pack(fill="x")
        ttk.Label(self.mem_btn_frame, text="⚡ Clic = accord le transceiver via CAT :",
                  font=("Arial",9), foreground="#aaa").pack(anchor="w", pady=(0,5))
        self.mem_buttons_grid = ttk.Frame(self.mem_btn_frame)
        self.mem_buttons_grid.pack(fill="x")

        cols = ("ID","Fréquence (MHz)","Libellé","Bande","Mode")
        self.tree_mem = ttk.Treeview(parent, columns=cols, show='headings', height=8, style="Custom.Treeview")
        self.tree_mem.column("ID", width=0, stretch=tk.NO)
        self.tree_mem.heading("Fréquence (MHz)", text="Fréquence (MHz)"); self.tree_mem.column("Fréquence (MHz)", width=130, anchor="center")
        self.tree_mem.heading("Libellé", text="Libellé"); self.tree_mem.column("Libellé", width=200, anchor="w")
        self.tree_mem.heading("Bande", text="Bande"); self.tree_mem.column("Bande", width=70, anchor="center")
        self.tree_mem.heading("Mode", text="Mode"); self.tree_mem.column("Mode", width=70, anchor="center")
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_mem.yview)
        self.tree_mem.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree_mem.pack(fill="both", expand=True)
        self.tree_mem.bind("<Double-1>", self._tune_memory)

        self._refresh_memories()

    def _ensure_default_memories(self):
        c = self.conn.cursor()
        count = c.execute("SELECT COUNT(*) FROM freq_memories").fetchone()[0]
        if count == 0:
            for i, (freq, label, band, mode) in enumerate(self.DEFAULT_MEMORIES):
                c.execute("INSERT INTO freq_memories (freq, label, band, mode, sort_order) VALUES (?,?,?,?,?)",
                          (freq, label, band, mode, i))
            self.conn.commit()

    def _restore_default_memories(self):
        if messagebox.askyesno("Restaurer", "Effacer les mémoires actuelles et restaurer les défauts ?"):
            self.conn.cursor().execute("DELETE FROM freq_memories")
            self.conn.commit()
            self._ensure_default_memories()
            self._refresh_memories()

    def _refresh_memories(self):
        for w in self.mem_buttons_grid.winfo_children(): w.destroy()
        for item in self.tree_mem.get_children(): self.tree_mem.delete(item)

        rows = self.conn.cursor().execute(
            "SELECT id, freq, label, band, mode FROM freq_memories ORDER BY sort_order, id").fetchall()

        mode_colors = {
            "FT8":"#2ecc71","FT4":"#27ae60","SSB":"#3498db","CW":"#f39c12",
            "DIG":"#9b59b6","FM":"#1abc9c","AM":"#e67e22"
        }
        band_groups = {}
        for mem_id, freq, label, band, mode in rows:
            if band not in band_groups: band_groups[band] = []
            band_groups[band].append((mem_id, freq, label, band, mode))

        col = 0; row_idx = 0
        for band in ["160m","80m","40m","30m","20m","17m","15m","12m","10m","6m","2m",""]:
            if band not in band_groups: continue
            if col > 0 and col % 8 == 0:
                row_idx += 2; col = 0
            ttk.Label(self.mem_buttons_grid, text=band or "?", font=("Arial",8,"bold"),
                      foreground="#f39c12").grid(row=row_idx, column=col, padx=2, pady=(4,1))
            for mem_id, freq, label, band2, mode in band_groups[band]:
                color = mode_colors.get(mode, "#555")
                btn = tk.Button(
                    self.mem_buttons_grid,
                    text=f"{freq}\n{label}",
                    width=10, height=2,
                    font=("Consolas", 8),
                    bg=color, fg="white",
                    relief="raised", cursor="hand2",
                    command=lambda f=freq, m=mode: self._tune_to(f, m)
                )
                btn.grid(row=row_idx+1, column=col, padx=2, pady=2, sticky="ew")
                col += 1
                if col >= 12: col = 0; row_idx += 2

        for mem_id, freq, label, band, mode in rows:
            self.tree_mem.insert("", "end", values=(mem_id, freq, label, band, mode))

    def _tune_to(self, freq_mhz, mode):
        try:
            freq_hz = float(freq_mhz) * 1e6
            self.cat.set_freq(freq_hz)
            self.e_mode.delete(0, tk.END); self.e_mode.insert(0, mode)
            self.status_var.set(f"📻 Accordé sur {freq_mhz} MHz — {mode}")
        except Exception as e:
            self.status_var.set(f"⚠️ Erreur CAT : {e}")

    def _tune_memory(self, event=None):
        sel = self.tree_mem.selection()
        if not sel: return
        v = self.tree_mem.item(sel[0])['values']
        self._tune_to(str(v[1]), str(v[4]))

    def _add_memory(self):
        freq = self.mem_freq_var.get().strip()
        label = self.mem_label_var.get().strip()
        mode = self.mem_mode_var.get()
        if not freq or not label:
            messagebox.showwarning("Mémoire","Fréquence et libellé requis."); return
        try: float(freq)
        except: messagebox.showwarning("Mémoire","Fréquence invalide."); return
        band = freq_to_band(freq)
        c = self.conn.cursor()
        c.execute("INSERT INTO freq_memories (freq, label, band, mode, sort_order) VALUES (?,?,?,?,?)",
                  (freq, label, band, mode, 999))
        self.conn.commit()
        self.mem_freq_var.set(""); self.mem_label_var.set("")
        self._refresh_memories()
        self.status_var.set(f"✅ Mémoire ajoutée : {label} — {freq} MHz")

    def _del_memory(self):
        sel = self.tree_mem.selection()
        if not sel: return
        if messagebox.askyesno("Supprimer", f"Supprimer {len(sel)} mémoire(s) ?"):
            c = self.conn.cursor()
            for item in sel:
                mem_id = self.tree_mem.item(item)['values'][0]
                c.execute("DELETE FROM freq_memories WHERE id=?", (mem_id,))
            self.conn.commit()
            self._refresh_memories()

    # ==========================================
    # --- EXPORT LoTW (ADIF format TQSL) ---
    # ==========================================

    def export_lotw_adif(self):
        """Export ADIF compatible LoTW pour soumission via TQSL."""
        fn = filedialog.asksaveasfilename(
            defaultextension=".adi",
            filetypes=[("ADIF for LoTW", "*.adi"), ("All", "*.*")],
            title="Export ADIF pour LoTW/TQSL"
        )
        if not fn: return

        sel = self.tree.selection()
        use_selection = len(sel) > 0

        if use_selection:
            if not messagebox.askyesno("Export LoTW", f"Exporter les {len(sel)} QSO(s) sélectionnés ?\n(Non = exporter tout le logbook)"):
                use_selection = False

        try:
            c = self.conn.cursor()
            if use_selection:
                ids = [self.tree.item(item)['values'][0] for item in sel]
                placeholders = ",".join("?" * len(ids))
                rows = c.execute(f"SELECT * FROM qsos WHERE id IN ({placeholders})", ids).fetchall()
            else:
                rows = c.execute("SELECT * FROM qsos").fetchall()

            col_names = [d[0] for d in c.description]
            ci = {name: i for i, name in enumerate(col_names)}

            with open(fn, "w", encoding="utf-8") as f:
                f.write(f"LoTW ADIF Export by {MY_CALL} Station Master\n")
                f.write(f"<ADIF_VER:5>2.2.7 ")
                f.write(f"<CREATED_TIMESTAMP:{len(datetime.now().strftime('%Y%m%d %H%M%S'))}>{datetime.now().strftime('%Y%m%d %H%M%S')} ")
                f.write(f"<PROGRAMID:13>StationMaster ")
                f.write(f"<EOH>\n\n")

                def adif(tag, val):
                    val = str(val).strip() if val else ""
                    return f"<{tag}:{len(val)}>{val} " if val else ""

                exported = 0
                for row in rows:
                    date_raw = row[ci.get('qso_date', 1)] or ""
                    time_raw = row[ci.get('time_on', 2)] or ""
                    call     = row[ci.get('callsign', 3)] or ""
                    band     = row[ci.get('band', 4)] or ""
                    mode     = row[ci.get('mode', 5)] or ""
                    rst_s    = row[ci.get('rst_sent', 6)] or "59"
                    rst_r    = row[ci.get('rst_rcvd', 7)] or "59"
                    name     = row[ci.get('name', 8)] or ""
                    qth      = row[ci.get('qth', 9)] or ""
                    grid     = row[ci.get('grid', 13)] or ""
                    freq_raw = row[ci.get('freq', 14)] or ""
                    comment  = row[ci.get('comment', 19)] or ""

                    if not call or not date_raw: continue

                    # Normaliser date YYYYMMDD
                    date_adif = date_raw.replace('-', '') if '-' in date_raw else date_raw
                    # Normaliser heure HHMM
                    time_adif = time_raw.replace(':', '') if ':' in time_raw else time_raw
                    if len(time_adif) > 4: time_adif = time_adif[:4]

                    # Fréquence en MHz
                    freq_mhz = ""
                    try:
                        fv = float(freq_raw)
                        freq_mhz = f"{fv/1e6:.6f}" if fv > 1e4 else f"{fv:.6f}"
                    except: pass

                    # Mode ADIF normalisé
                    mode_adif = mode.upper()
                    submodes = {"FT8": ("MFSK", "FT8"), "FT4": ("MFSK", "FT4"),
                                "JS8": ("MFSK", "JS8CALL"), "WSPR": ("WSPR", ""),
                                "JT65": ("JT65", ""), "JT9": ("JT9", "")}
                    submode_val = ""
                    if mode_adif in submodes:
                        mode_adif, submode_val = submodes[mode_adif]

                    rec  = adif("CALL", call)
                    rec += adif("QSO_DATE", date_adif)
                    rec += adif("TIME_ON", time_adif)
                    rec += adif("BAND", band)
                    rec += adif("MODE", mode_adif)
                    if submode_val: rec += adif("SUBMODE", submode_val)
                    if freq_mhz: rec += adif("FREQ", freq_mhz)
                    rec += adif("RST_SENT", rst_s)
                    rec += adif("RST_RCVD", rst_r)
                    if name: rec += adif("NAME", name)
                    if qth: rec += adif("QTH", qth)
                    if grid: rec += adif("GRIDSQUARE", grid)
                    if comment: rec += adif("COMMENT", comment)
                    rec += adif("STATION_CALLSIGN", MY_CALL)
                    rec += adif("MY_GRIDSQUARE", MY_GRID)
                    rec += "<EOR>\n"
                    f.write(rec)
                    exported += 1

            msg = f"✅ {exported} QSO(s) exportés vers :\n{fn}\n\n"
            msg += "Pour soumettre à LoTW :\n"
            msg += "1. Ouvrez TQSL\n"
            msg += "2. Signez le fichier .adi avec votre certificat\n"
            msg += "3. Uploadez le fichier .tq8 résultant sur lotw.arrl.org\n\n"
            tqsl_path = CONF.get('LOTW', 'Tqsl_Path', fallback='') if CONF else ''
            if tqsl_path and os.path.exists(tqsl_path):
                if messagebox.askyesno("LoTW Export", msg + f"Ouvrir TQSL maintenant ?\n({tqsl_path})"):
                    import subprocess
                    subprocess.Popen([tqsl_path, fn])
            else:
                messagebox.showinfo("LoTW Export", msg)

            self.status_var.set(f"📤 LoTW ADIF : {exported} QSOs exportés → {os.path.basename(fn)}")
        except Exception as e:
            messagebox.showerror("Erreur export LoTW", str(e))

    def _submit_lotw_direct(self):
        """Exporte automatiquement les QSOs non encore soumis à LoTW et lance TQSL."""
        import subprocess, tempfile
        tqsl_path = CONF.get('LOTW', 'Tqsl_Path', fallback='') if CONF else ''
        if not tqsl_path:
            messagebox.showwarning("TQSL", "Chemin TQSL non configuré.\nAllez dans ⚙️ Paramètres → LoTW / TQSL.")
            return

        # Sur Linux, TQSL peut être dans le PATH même sans chemin absolu
        tqsl_ok = os.path.exists(tqsl_path) or (os.name != 'nt' and tqsl_path == 'tqsl')
        if not tqsl_ok:
            messagebox.showwarning("TQSL", f"TQSL introuvable :\n{tqsl_path}\nVérifiez ⚙️ Paramètres → LoTW / TQSL.")
            return

        try:
            c = self.conn.cursor()
            rows = c.execute(
                "SELECT * FROM qsos WHERE (lotw_stat IS NULL OR lotw_stat NOT IN ('OK','YES','Y','LOTW','Submitted'))"
            ).fetchall()
            if not rows:
                messagebox.showinfo("LoTW", "✅ Tous les QSOs sont déjà soumis à LoTW !")
                return

            col_names = [d[0] for d in c.description]
            ci = {name: i for i, name in enumerate(col_names)}

            if not messagebox.askyesno("Soumettre LoTW",
                    f"Exporter et soumettre {len(rows)} QSO(s) non encore envoyés à LoTW ?\n\n"
                    "TQSL s'ouvrira pour signer le fichier."):
                return

            def adif(tag, val):
                val = str(val).strip() if val else ""
                return f"<{tag}:{len(val)}>{val} " if val else ""

            tmp = tempfile.NamedTemporaryFile(suffix=".adi", delete=False,
                                             dir=_APP_DIR, prefix="lotw_submit_")
            tmp_path = tmp.name
            with tmp as f_out:
                f_out.write(f"LoTW Submit — {MY_CALL} — {datetime.now().strftime('%Y%m%d %H%M%S')}\n".encode())
                f_out.write(b"<ADIF_VER:5>2.2.7 <EOH>\n\n")
                for row in rows:
                    date_raw = row[ci.get('qso_date', 1)] or ""
                    time_raw = row[ci.get('time_on',   2)] or ""
                    call     = row[ci.get('callsign',  3)] or ""
                    band     = row[ci.get('band',      4)] or ""
                    mode     = row[ci.get('mode',      5)] or ""
                    rst_s    = row[ci.get('rst_sent',  6)] or "59"
                    rst_r    = row[ci.get('rst_rcvd',  7)] or "59"
                    grid     = row[ci.get('grid',     13)] or ""
                    freq_raw = row[ci.get('freq',     14)] or ""
                    if not call or not date_raw: continue
                    date_adif = date_raw.replace('-', '')
                    time_adif = time_raw.replace(':', '')[:4]
                    freq_mhz  = ""
                    try:
                        fv = float(freq_raw)
                        freq_mhz = f"{fv/1e6:.6f}" if fv > 1e4 else f"{fv:.6f}"
                    except: pass
                    mode_adif = mode.upper()
                    submodes  = {"FT8":("MFSK","FT8"),"FT4":("MFSK","FT4"),"JS8":("MFSK","JS8CALL"),
                                 "WSPR":("WSPR",""),"JT65":("JT65",""),"JT9":("JT9","")}
                    submode_v = ""
                    if mode_adif in submodes:
                        mode_adif, submode_v = submodes[mode_adif]
                    rec  = adif("CALL", call) + adif("QSO_DATE", date_adif)
                    rec += adif("TIME_ON", time_adif) + adif("BAND", band)
                    rec += adif("MODE", mode_adif)
                    if submode_v:  rec += adif("SUBMODE", submode_v)
                    if freq_mhz:   rec += adif("FREQ", freq_mhz)
                    rec += adif("RST_SENT", rst_s) + adif("RST_RCVD", rst_r)
                    if grid: rec += adif("GRIDSQUARE", grid)
                    rec += adif("STATION_CALLSIGN", MY_CALL) + adif("MY_GRIDSQUARE", MY_GRID)
                    rec += "<EOR>\n"
                    f_out.write(rec.encode())

            # Marquer comme "Submitted"
            ids = [row[ci.get('id', 0)] for row in rows]
            c.executemany("UPDATE qsos SET lotw_stat='Submitted' WHERE id=?",
                         [(i,) for i in ids])
            self.conn.commit()

            subprocess.Popen([tqsl_path, tmp_path])
            self.status_var.set(f"📡 LoTW : {len(rows)} QSOs envoyés à TQSL → {os.path.basename(tmp_path)}")
            messagebox.showinfo("LoTW", f"✅ {len(rows)} QSOs exportés et TQSL lancé.\n\nFichier : {tmp_path}\nSignez avec votre certificat LoTW dans TQSL.")
        except Exception as e:
            messagebox.showerror("Erreur LoTW", str(e))


    # ==========================================
    # --- HEATMAP MONDIALE ---
    # ==========================================
    def _build_heatmap_tab(self, parent):
        ctrl = tk.Frame(parent, bg="#11273f"); ctrl.pack(fill="x")
        ttk.Button(ctrl, text="🔄 Générer la heatmap", command=self._draw_heatmap,
                   bootstyle="primary").pack(side="left", padx=5)
        ttk.Label(ctrl, text="Afficher par:").pack(side="left", padx=(15,3))
        self.heatmap_mode_var = tk.StringVar(value="Entités DXCC")
        ttk.Combobox(ctrl, textvariable=self.heatmap_mode_var,
                     values=["Entités DXCC","Densité QSOs","Continents"], width=16).pack(side="left", padx=3)
        ttk.Label(ctrl, text="Année:").pack(side="left", padx=(12,3))
        self.heatmap_year_var = tk.StringVar(value="Tout")
        try:
            years = ["Tout"] + sorted(
                {r[0][:4] for r in self.conn.cursor().execute(
                    "SELECT qso_date FROM qsos WHERE qso_date IS NOT NULL AND qso_date != ''").fetchall()
                 if r[0] and len(r[0]) >= 4}, reverse=True)
        except Exception:
            years = ["Tout"]
        ttk.Combobox(ctrl, textvariable=self.heatmap_year_var,
                     values=years, width=8).pack(side="left", padx=3)
        self.heatmap_info_var = tk.StringVar(value="Chargement de la carte…")
        ttk.Label(ctrl, textvariable=self.heatmap_info_var, foreground="#f39c12").pack(side="right", padx=10)

        self._heatmap_map_base  = None
        self._heatmap_photo     = None
        self._heatmap_redraw_id = None

        self._heatmap_canvas = tk.Canvas(parent, bg="#050a14", highlightthickness=0)
        self._heatmap_canvas.pack(fill="both", expand=True)
        self._heatmap_canvas.bind("<Configure>", lambda e: self._heatmap_schedule_redraw())
        threading.Thread(target=self._heatmap_load_map, daemon=True).start()

    def _heatmap_load_map(self):
        import urllib.request
        _MAP_URL  = "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57752/land_shallow_topo_2048.jpg"
        map_file  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "world_map_grayline.jpg")
        if not os.path.exists(map_file):
            try:
                req = urllib.request.Request(
                    _MAP_URL, headers={"User-Agent": "StationMaster/21 ON5AM"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                with open(map_file, "wb") as f:
                    f.write(data)
            except Exception as e:
                print(f"[Heatmap] téléchargement carte : {e}")
                self._tk_queue.put(self._draw_heatmap)
                return
        try:
            from PIL import Image
            self._heatmap_map_base = Image.open(map_file).convert("RGB")
        except Exception as e:
            print(f"[Heatmap] lecture carte : {e}")
        self._tk_queue.put(self._draw_heatmap)

    def _heatmap_schedule_redraw(self):
        if self._heatmap_redraw_id:
            self.root.after_cancel(self._heatmap_redraw_id)
        self._heatmap_redraw_id = self.root.after(120, self._draw_heatmap)

    @staticmethod
    def _heatmap_ll2xy(lat, lon, w, h):
        return int((lon + 180) / 360 * w), int((90 - lat) / 180 * h)

    def _draw_heatmap(self):
        try:
            from PIL import Image, ImageDraw, ImageTk
        except ImportError:
            self.heatmap_info_var.set("⚠️ Pillow requis : pip install Pillow")
            return

        canvas = self._heatmap_canvas
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 20 or h < 20:
            return

        # ── Fond carte ────────────────────────────────────────────────────────
        if self._heatmap_map_base:
            img = self._heatmap_map_base.copy().resize((w, h), Image.LANCZOS)
        else:
            img = Image.new("RGB", (w, h), (10, 20, 50))
            d0  = ImageDraw.Draw(img)
            for lat in range(-60, 91, 30):
                y0 = self._heatmap_ll2xy(lat, 0, w, h)[1]
                d0.line([(0, y0), (w, y0)], fill=(30, 40, 70))
            for lon in range(-180, 181, 30):
                x0 = self._heatmap_ll2xy(0, lon, w, h)[0]
                d0.line([(x0, 0), (x0, h)], fill=(30, 40, 70))

        draw = ImageDraw.Draw(img, "RGBA")

        # ── Données QSOs ──────────────────────────────────────────────────────
        c    = self.conn.cursor()
        year = getattr(self, 'heatmap_year_var', None)
        year = year.get() if year else "Tout"
        if year and year != "Tout":
            rows = c.execute(
                "SELECT callsign, grid FROM qsos WHERE grid != '' AND qso_date LIKE ?",
                (f"{year}%",)).fetchall()
        else:
            rows = c.execute("SELECT callsign, grid FROM qsos WHERE grid != ''").fetchall()
        mode = self.heatmap_mode_var.get()

        points = {}
        for call, grid in rows:
            pos = grid_to_latlon(grid)
            if not pos:
                continue
            lat, lon = pos
            entity = get_country_name(call) or "?"
            key = (round(lat), round(lon))
            if key not in points:
                points[key] = {'count': 0, 'entity': entity}
            points[key]['count'] += 1

        # ── Palettes ──────────────────────────────────────────────────────────
        _PAL = [
            (52,152,219),(231,76,60),(46,204,113),(243,156,18),(155,89,182),
            (26,188,156),(230,126,34),(233,30,99),(0,188,212),(139,195,74),
            (255,87,34),(96,125,139),(255,152,0),(3,169,244),(121,85,72),
            (105,240,174),(234,128,252),(255,235,59),
        ]
        _CONT_RGB = {
            "EU":(52,152,219),"AS":(231,76,60),"NA":(46,204,113),
            "SA":(243,156,18),"AF":(155,89,182),"OC":(26,188,156),"AN":(170,170,170),
        }
        _CONT_NAMES = {
            "EU":"Europe","AS":"Asie","NA":"Am. Nord","SA":"Am. Sud",
            "AF":"Afrique","OC":"Océanie","AN":"Antarctique",
        }

        if mode == "Densité QSOs":
            max_c = max((v['count'] for v in points.values()), default=1)
            for (lat, lon), data in points.items():
                t    = data['count'] / max_c
                r    = int(80 + 175 * t)
                g    = int(200 * (1 - t * 0.8))
                size = max(2, int(2 + 6 * t))
                x, y = self._heatmap_ll2xy(lat, lon, w, h)
                draw.ellipse([x-size, y-size, x+size, y+size],
                             fill=(r, g, 0, 210), outline=(255, 255, 255, 40))

        elif mode == "Continents":
            for (lat, lon), data in points.items():
                entity = data['entity']
                cont   = "EU"
                for row in self.DXCC_DATA:
                    if row[1] == entity:
                        cont = row[2]; break
                color = _CONT_RGB.get(cont, (150, 150, 150))
                x, y  = self._heatmap_ll2xy(lat, lon, w, h)
                draw.ellipse([x-4, y-4, x+4, y+4],
                             fill=(*color, 210), outline=(255, 255, 255, 40))
            # Légende
            lx = 10
            ly = h - len(_CONT_RGB) * 16 - 12
            draw.rectangle([lx-3, ly-3, lx+118, ly + len(_CONT_RGB)*16 + 3],
                           fill=(0, 0, 0, 160))
            for i, (cont, color) in enumerate(_CONT_RGB.items()):
                y0 = ly + i * 16
                draw.ellipse([lx, y0+2, lx+10, y0+12], fill=(*color, 255))
                draw.text((lx+14, y0), _CONT_NAMES.get(cont, cont),
                          fill=(200, 200, 200, 230))

        else:  # Entités DXCC
            entities  = list({d['entity'] for d in points.values()})
            ent_color = {e: _PAL[i % len(_PAL)] for i, e in enumerate(entities)}
            for (lat, lon), data in points.items():
                color = ent_color.get(data['entity'], (170, 170, 170))
                x, y  = self._heatmap_ll2xy(lat, lon, w, h)
                draw.ellipse([x-4, y-4, x+4, y+4],
                             fill=(*color, 210), outline=(255, 255, 255, 30))

        # ── Marqueur station ──────────────────────────────────────────────────
        home = grid_to_latlon(MY_GRID)
        if home:
            hx, hy = self._heatmap_ll2xy(home[0], home[1], w, h)
            draw.ellipse([hx-7,  hy-7,  hx+7,  hy+7],  fill=(255, 165, 0, 255))
            draw.ellipse([hx-11, hy-11, hx+11, hy+11],
                         outline=(255, 165, 0, 180), width=2)
            draw.text((hx+13, hy-7), MY_CALL, fill=(255, 255, 255, 230))

        # ── Bandeau stats ─────────────────────────────────────────────────────
        total_qsos = sum(v['count'] for v in points.values())
        total_pts  = len(points)
        n_ent      = len({d['entity'] for d in points.values()})
        info = f"  {total_qsos} QSOs  •  {total_pts} locators  •  {n_ent} entités  •  {mode}  "
        draw.rectangle([0, 0, w, 18], fill=(0, 0, 0, 160))
        draw.text((6, 2), info, fill=(243, 156, 18, 230))

        self._heatmap_photo = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=self._heatmap_photo)
        self.heatmap_info_var.set(
            f"{total_qsos} QSOs • {total_pts} locators uniques • {n_ent} entités")

    # ==========================================
    # --- CONTEST TIMER ---
    # ==========================================
    def _build_contest_tab(self, parent):
        self._contest_running = False
        self._contest_start = None
        self._contest_qso_start = 0
        self._contest_end_time = None

        top = tk.Frame(parent, bg="#11273f"); top.pack(fill="x")
        # Config contest
        cfg = ttk.Labelframe(top, text="Configuration", bootstyle="warning", padding=10)
        cfg.pack(side="left", fill="x", expand=True)
        fields = tk.Frame(cfg, bg="#11273f"); fields.pack(fill="x")
        ttk.Label(fields, text="Nom du contest:").grid(row=0,column=0,sticky="e",padx=5,pady=3)
        self.contest_name_var = tk.StringVar(value="CQ WW SSB")
        ttk.Combobox(fields, textvariable=self.contest_name_var,
            values=["CQ WW SSB","CQ WW CW","CQ WW FT8","WAE SSB","WAE CW",
                    "IARU HF","King of Spain","UBA Contest","Autres"],
            width=18).grid(row=0,column=1,padx=5,pady=3)
        ttk.Label(fields, text="Durée (heures):").grid(row=0,column=2,sticky="e",padx=5)
        self.contest_dur_var = tk.StringVar(value="48")
        ttk.Combobox(fields, textvariable=self.contest_dur_var,
            values=["6","8","12","24","48"], width=5).grid(row=0,column=3,padx=5)
        ttk.Label(fields, text="Objectif QSOs:").grid(row=0,column=4,sticky="e",padx=5)
        self.contest_goal_var = tk.StringVar(value="500")
        ttk.Entry(fields, textvariable=self.contest_goal_var, width=7).grid(row=0,column=5,padx=5)

        # Panneau central - grands chiffres
        center = tk.Frame(parent, bg="#11273f"); center.pack(fill="x")
        self.contest_timer_var = tk.StringVar(value="00:00:00")
        self.contest_remain_var = tk.StringVar(value="--:--:--")
        ttk.Label(center, textvariable=self.contest_timer_var,
                  font=("Impact",52), foreground="#f39c12").pack(side="left", padx=20)
        mid_f = tk.Frame(center, bg="#11273f"); mid_f.pack(side="left", padx=20)
        ttk.Label(mid_f, text="TEMPS ÉCOULÉ", font=("Arial",9), foreground="#888").pack()
        ttk.Label(mid_f, text="TEMPS RESTANT", font=("Arial",9), foreground="#888").pack(pady=(15,0))
        ttk.Label(mid_f, textvariable=self.contest_remain_var,
                  font=("Impact",24), foreground="#3daee9").pack()
        # Stats QSOs
        stats_f = tk.Frame(center, bg="#11273f"); stats_f.pack(side="left", padx=20)
        self.contest_qsos_var = tk.StringVar(value="0")
        self.contest_rate_var = tk.StringVar(value="0")
        self.contest_rate1h_var = tk.StringVar(value="0")
        ttk.Label(stats_f, text="QSOs CONTEST", font=("Arial",9), foreground="#888").pack()
        ttk.Label(stats_f, textvariable=self.contest_qsos_var,
                  font=("Impact",42), foreground="#3fb950").pack()
        rate_f = tk.Frame(stats_f, bg="#11273f"); rate_f.pack()
        ttk.Label(rate_f, text="Rate /h:", foreground="#aaa", font=("Consolas",10)).pack(side="left")
        ttk.Label(rate_f, textvariable=self.contest_rate_var,
                  font=("Consolas",10,"bold"), foreground="#3fb950").pack(side="left", padx=5)
        ttk.Label(rate_f, text="  Dernière heure:", foreground="#aaa", font=("Consolas",10)).pack(side="left")
        ttk.Label(rate_f, textvariable=self.contest_rate1h_var,
                  font=("Consolas",10,"bold"), foreground="#3daee9").pack(side="left", padx=5)
        # Barre progression objectif
        goal_f = tk.Frame(parent, bg="#11273f"); goal_f.pack(fill="x")
        ttk.Label(goal_f, text="Progression vers objectif:", font=("Arial",9), foreground="#aaa").pack(anchor="w")
        self.contest_pb = ttk.Progressbar(goal_f, maximum=100, bootstyle="success-striped", length=600)
        self.contest_pb.pack(fill="x", pady=3)
        self.contest_pb_lbl = ttk.Label(goal_f, text="0 / 500", foreground="white"); self.contest_pb_lbl.pack(anchor="w")

        # Boutons
        btn_f = tk.Frame(parent, bg="#11273f"); btn_f.pack(fill="x")
        self.btn_contest_start = ttk.Button(btn_f, text="▶ DÉMARRER", command=self._contest_start,
                                             bootstyle="success", width=16)
        self.btn_contest_start.pack(side="left", padx=5)
        ttk.Button(btn_f, text="⏸ PAUSE / REPRENDRE", command=self._contest_pause,
                   bootstyle="warning", width=20).pack(side="left", padx=5)
        ttk.Button(btn_f, text="⏹ ARRÊTER", command=self._contest_stop,
                   bootstyle="danger", width=14).pack(side="left", padx=5)
        ttk.Button(btn_f, text="📊 Rapport final", command=self._contest_report,
                   bootstyle="info-outline", width=16).pack(side="left", padx=5)

        # Log contest
        ttk.Label(parent, text="Activité contest (QSOs depuis le démarrage) :", foreground="#aaa",
                  font=("Arial",9)).pack(anchor="w", padx=10)
        cols = ("Heure","Callsign","Bande","Mode","RS Envoyé","RS Reçu")
        self.tree_contest = ttk.Treeview(parent, columns=cols, show='headings',
                                          style="Custom.Treeview", height=8)
        for col in cols:
            self.tree_contest.heading(col, text=col); self.tree_contest.column(col, width=110, anchor="center")
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_contest.yview)
        self.tree_contest.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree_contest.pack(fill="both", expand=True, padx=5, pady=5)

    def _contest_start(self):
        if self._contest_running: return
        self._contest_running = True
        self._contest_paused = False
        self._contest_start = datetime.now(timezone.utc)
        self._contest_end_time = None
        try:
            dur_h = float(self.contest_dur_var.get())
            from datetime import timedelta
            self._contest_deadline = self._contest_start + timedelta(hours=dur_h)
        except: self._contest_deadline = None
        self._contest_qso_start = self.conn.cursor().execute("SELECT COUNT(*) FROM qsos").fetchone()[0]
        self.status_var.set(f"⏱️ Contest démarré : {self.contest_name_var.get()}")
        self.btn_contest_start.config(bootstyle="secondary")
        self._contest_tick()
        # Observer: charger les QSOs récents dans le tableau
        self._contest_refresh_log()

    def _contest_pause(self):
        self._contest_paused = not getattr(self, '_contest_paused', False)
        if self._contest_paused:
            self._pause_time = datetime.now(timezone.utc)
            self.status_var.set("⏸ Contest en pause")
        else:
            if hasattr(self,'_pause_time') and self._contest_start:
                from datetime import timedelta
                pause_dur = datetime.now(timezone.utc) - self._pause_time
                self._contest_start += pause_dur
                if self._contest_deadline: self._contest_deadline += pause_dur
            self.status_var.set(f"▶ Contest repris : {self.contest_name_var.get()}")
            self._contest_tick()

    def _contest_stop(self):
        self._contest_running = False
        self._contest_end_time = datetime.now(timezone.utc)
        self.status_var.set(f"⏹ Contest arrêté — {self.contest_name_var.get()}")
        self.btn_contest_start.config(bootstyle="success")

    def _contest_tick(self):
        if not self._contest_running or getattr(self,'_contest_paused',False): return
        now = datetime.now(timezone.utc)
        if self._contest_start:
            elapsed = now - self._contest_start
            h,rem = divmod(int(elapsed.total_seconds()), 3600)
            m,s = divmod(rem, 60)
            self.contest_timer_var.set(f"{h:02d}:{m:02d}:{s:02d}")
            if self._contest_deadline:
                remain = self._contest_deadline - now
                if remain.total_seconds() > 0:
                    rh,rrem = divmod(int(remain.total_seconds()),3600)
                    rm,rs = divmod(rrem,60)
                    self.contest_remain_var.set(f"{rh:02d}:{rm:02d}:{rs:02d}")
                else:
                    self.contest_remain_var.set("TERMINÉ")
                    self._contest_stop()
                    messagebox.showinfo("Contest","⏱️ Temps écoulé ! Contest terminé.")
                    return
        # Stats QSOs
        total_now = self.conn.cursor().execute("SELECT COUNT(*) FROM qsos").fetchone()[0]
        contest_qsos = max(0, total_now - self._contest_qso_start)
        self.contest_qsos_var.set(str(contest_qsos))
        # Rate global
        elapsed_h = elapsed.total_seconds()/3600 if self._contest_start else 1
        rate = int(contest_qsos / max(elapsed_h, 0.017))
        self.contest_rate_var.set(str(rate))
        # Rate dernière heure
        one_h_ago = (now - __import__('datetime').timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')
        rate1h = self.conn.cursor().execute(
            "SELECT COUNT(*) FROM qsos WHERE qso_date||' '||time_on >= ?", (one_h_ago,)).fetchone()[0]
        self.contest_rate1h_var.set(str(rate1h))
        # Progression
        try:
            goal = int(self.contest_goal_var.get())
            pct = min(100, int(contest_qsos/goal*100))
            self.contest_pb['value'] = pct
            self.contest_pb_lbl.config(text=f"{contest_qsos} / {goal}  ({pct}%)")
        except: pass
        # Rafraîchir log toutes les 30 ticks
        if int(elapsed.total_seconds()) % 30 == 0:
            self._contest_refresh_log()
        self.root.after(1000, self._contest_tick)

    def _contest_refresh_log(self):
        if not self._contest_start: return
        for item in self.tree_contest.get_children(): self.tree_contest.delete(item)
        start_str = self._contest_start.strftime('%Y-%m-%d %H:%M')
        rows = self.conn.cursor().execute(
            "SELECT time_on, callsign, band, mode, rst_sent, rst_rcvd FROM qsos "
            "WHERE qso_date||' '||time_on >= ? ORDER BY qso_date DESC, time_on DESC LIMIT 50",
            (start_str,)).fetchall()
        for row in rows:
            self.tree_contest.insert("","end", values=row)

    def _contest_report(self):
        if not self._contest_start:
            messagebox.showinfo("Contest","Démarrez d'abord un contest."); return
        now = self._contest_end_time or datetime.now(timezone.utc)
        elapsed = now - self._contest_start
        h,rem = divmod(int(elapsed.total_seconds()),3600); m,s = divmod(rem,60)
        total_now = self.conn.cursor().execute("SELECT COUNT(*) FROM qsos").fetchone()[0]
        contest_qsos = max(0, total_now - self._contest_qso_start)
        elapsed_h = elapsed.total_seconds()/3600
        rate = int(contest_qsos/max(elapsed_h,0.017))
        c = self.conn.cursor()
        start_str = self._contest_start.strftime('%Y-%m-%d %H:%M')
        bands = c.execute("SELECT band, COUNT(*) FROM qsos WHERE qso_date||' '||time_on >= ? GROUP BY band ORDER BY COUNT(*) DESC", (start_str,)).fetchall()
        modes = c.execute("SELECT mode, COUNT(*) FROM qsos WHERE qso_date||' '||time_on >= ? GROUP BY mode ORDER BY COUNT(*) DESC", (start_str,)).fetchall()
        msg = (f"=== RAPPORT CONTEST : {self.contest_name_var.get()} ===\n\n"
               f"Début : {self._contest_start.strftime('%Y-%m-%d %H:%M UTC')}\n"
               f"Fin   : {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
               f"Durée : {h:02d}h{m:02d}\n\n"
               f"QSOs totaux  : {contest_qsos}\n"
               f"Rate moyen   : {rate} QSO/h\n\n"
               f"Par bande:\n" + "\n".join(f"  {b[0]}: {b[1]}" for b in bands) +
               f"\n\nPar mode:\n" + "\n".join(f"  {m2[0]}: {m2[1]}" for m2 in modes))
        win = tk.Toplevel(self.root); win.title("Rapport Contest"); win.geometry("420x400")
        txt = tk.Text(win, font=("Consolas",10), bg="#11273f", fg="white", padx=15, pady=10)
        txt.pack(fill="both", expand=True); txt.insert("1.0", msg)
        ttk.Button(win, text="✖ Fermer", command=win.destroy, bootstyle="secondary").pack(pady=5)

    # ==========================================
    # --- QSL CARD DESIGNER ---
    # ==========================================
    def _build_qslcard_tab(self, parent):
        ctrl = tk.Frame(parent, bg="#11273f"); ctrl.pack(fill="x")
        ttk.Label(ctrl, text="Sélectionnez un QSO dans le Journal puis cliquez :",
                  font=("Arial",10), foreground="#aaa").pack(side="left", padx=5)
        ttk.Button(ctrl, text="🖨️ Générer QSL Card", command=self._generate_qsl_card,
                   bootstyle="success").pack(side="left", padx=10)
        ttk.Button(ctrl, text="💾 Enregistrer PNG", command=self._save_qsl_card,
                   bootstyle="info-outline").pack(side="left", padx=5)
        ttk.Button(ctrl, text="🖨️ Imprimer", command=self._print_qsl_card,
                   bootstyle="warning-outline").pack(side="left", padx=5)

        # Options design
        opt = ttk.Labelframe(parent, text="Options de la carte QSL", padding=8, bootstyle="primary")
        opt.pack(fill="x", padx=8, pady=4)
        opt_f = tk.Frame(opt, bg="#11273f"); opt_f.pack(fill="x")
        ttk.Label(opt_f, text="Thème:").pack(side="left", padx=5)
        self.qsl_theme_var = tk.StringVar(value="Classique")
        ttk.Combobox(opt_f, textvariable=self.qsl_theme_var,
                     values=["Classique","Nuit DX","Vintage","Contest"], width=12).pack(side="left", padx=3)
        ttk.Label(opt_f, text="  Message:").pack(side="left", padx=5)
        self.qsl_msg_var = tk.StringVar(value="Confirming our QSO with many thanks!")
        ttk.Entry(opt_f, textvariable=self.qsl_msg_var, width=35).pack(side="left", padx=3)
        ttk.Label(opt_f, text="  QTH:").pack(side="left", padx=5)
        self.qsl_qth_var = tk.StringVar(value="Belgium")
        ttk.Entry(opt_f, textvariable=self.qsl_qth_var, width=14).pack(side="left", padx=3)

        # Canvas d'aperçu
        self._qsl_canvas_frame = tk.Frame(parent, bg="#11273f"); self._qsl_canvas_frame.pack(fill="both", expand=True)
        self._qsl_canvas = tk.Canvas(self._qsl_canvas_frame, bg="#0d1b2e", width=680, height=437)
        self._qsl_canvas.pack(expand=True)
        self._qsl_last_qso = None
        self._draw_qsl_card_preview()

    def _get_selected_qso(self):
        sel = self.tree.selection()
        if not sel: return None
        v = self.tree.item(sel[0])['values']
        return {'id':v[0],'country':v[1],'date':v[2],'time':v[3],'call':v[4],
                'name':v[5],'qth':v[6],'band':v[7],'mode':v[8],
                'rst_s':v[9],'rst_r':v[10],'dist':v[11],
                'ant': v[12] if len(v)>12 else ''}

    def _draw_qsl_card_preview(self, qso=None):
        self._qsl_last_qso = qso
        c = self._qsl_canvas
        c.delete("all")
        W, H = 680, 420

        GOLD  = "#c8a800"
        DARK  = "#0a1520"
        MID   = "#0d1b2e"
        LIGHT = "#f5f0e0"
        LGRAY = "#8899aa"

        # ── 1. HEADER (y=0–55) ─────────────────────────────────────────────
        c.create_rectangle(0, 0, W, 55, fill=DARK, outline="")
        c.create_line(0, 55, W, 55, fill=GOLD, width=2)
        c.create_text(18, 10, text="ON5AM", anchor="nw",
                      fill=GOLD, font=("Courier", 24, "bold"))
        c.create_text(W//2, 10, anchor="n",
                      text="Albert  •  Ans, Wallonie, Belgique  •  JO20SP",
                      fill=LGRAY, font=("Arial", 9))
        c.create_text(W//2, 27, anchor="n",
                      text="Rig: FlexRadio 6500  •  Membre UBA",
                      fill=LGRAY, font=("Arial", 8))
        c.create_text(W//2, 42, anchor="n",
                      text="LoTW  •  eQSL  •  ClubLog  •  QRZ.com",
                      fill="#5577aa", font=("Arial", 8))
        c.create_text(W-8, 10, anchor="ne",
                      text="CONFIRMING OUR QSO",
                      fill="#ffffff", font=("Courier", 9, "bold"))
        c.create_text(W-8, 27, anchor="ne",
                      text="PSE QSL — TNX 73 !",
                      fill=GOLD, font=("Courier", 9))
        c.create_text(W-8, 42, anchor="ne",
                      text="hamanalyst.org",
                      fill=LGRAY, font=("Arial", 8))

        # ── 2. ZONE CENTRALE (y=57–335) ────────────────────────────────────
        c.create_rectangle(0, 57, W, 335, fill=MID, outline="")
        c.create_text(18, 64, text="CONFIRMING QSO WITH :", anchor="nw",
                      fill=LGRAY, font=("Arial", 8))

        dx_call    = str(qso.get("call",    "") or "——") if qso else "——"
        dx_country = str(qso.get("country", "") or "")   if qso else ""
        dx_qth     = str(qso.get("qth",     "") or "")   if qso else ""
        c.create_text(18, 78, text=dx_call, anchor="nw",
                      fill=GOLD, font=("Courier", 26, "bold"))
        if qso:
            if dx_country:
                c.create_text(240, 80, text=dx_country, anchor="nw",
                              fill="#ffffff", font=("Arial", 11))
            if dx_qth:
                c.create_text(240, 100, text=dx_qth, anchor="nw",
                              fill=LGRAY, font=("Arial", 9))
        else:
            c.create_text(18, 94, anchor="nw",
                          text="← Sélectionnez un QSO dans l'onglet Journal",
                          fill="#334455", font=("Arial", 10, "italic"))

        c.create_line(18, 128, W-18, 128, fill="#1e3a5a", width=1)

        def field(x, y, label, value):
            c.create_text(x, y,    text=label, anchor="nw",
                          fill=LGRAY, font=("Arial", 7))
            c.create_text(x, y+13, text=value, anchor="nw",
                          fill="#ffffff", font=("Courier", 11, "bold"))

        def qval(key, default="——"):
            return str(qso.get(key) or default) if qso else "——"

        if qso:
            try:
                from tab_qsl import _freq_mhz
                _f = _freq_mhz(qso.get("freq", ""))
                freq_disp = f"{_f} MHz" if _f else str(qso.get("band") or "——")
            except Exception:
                freq_disp = str(qso.get("band") or "——")
        else:
            freq_disp = "——"

        qso_cols = [
            ("DATE",     qval("date")),  ("TIME UTC", qval("time")),
            ("BAND",     qval("band")),  ("MODE",     qval("mode")),
            ("FREQ",     freq_disp),     ("RST SENT", qval("rst_s")),
            ("RST RCVD", qval("rst_r")),
        ]
        col_w = (W - 36) // len(qso_cols)
        for i, (lbl, val) in enumerate(qso_cols):
            field(18 + i * col_w, 136, lbl, val)

        c.create_line(18, 178, W-18, 178, fill="#1e3a5a", width=1)

        sta_cols = [
            ("RIG",     "FlexRadio 6500"), ("ANTENNA", qval("ant")),
            ("POWER",   "100W"),           ("GRID",    "JO20SP"),
            ("QSL VIA", "Bureau / Direct / LoTW"),
        ]
        col_w2 = (W - 36) // len(sta_cols)
        for i, (lbl, val) in enumerate(sta_cols):
            field(18 + i * col_w2, 186, lbl, val)

        c.create_line(18, 226, W-18, 226, fill="#1e3a5a", width=1)
        c.create_text(W//2, 238, anchor="n",
                      text="Confirming our QSO with pleasure !",
                      fill="#7799bb", font=("Arial", 9, "italic"))
        c.create_text(W//2, 258, anchor="n",
                      text="✓ LoTW    ✓ eQSL    ✓ ClubLog    ✓ QRZ.com",
                      fill="#3a7a4a", font=("Courier", 9))
        c.create_line(18, 282, W-18, 282, fill="#1e3a5a", width=1)
        c.create_text(18, 294, anchor="nw",
                      text="CQ: 14  •  ITU: 27  •  Region 1  •  UBA",
                      fill=LGRAY, font=("Arial", 8))
        c.create_text(W-18, 294, anchor="ne",
                      text="hamanalyst.org/qsl", fill="#446688", font=("Arial", 8))

        # ── 3. ZONE DONNÉES IMPRIMÉES (y=335–410) ──────────────────────────
        c.create_rectangle(0, 335, W, 410, fill=LIGHT, outline="")
        c.create_line(0, 335, W, 335, fill=GOLD, width=2)

        cols_bot = [
            ("TO / CALLSIGN", 116), ("DATE UTC", 82), ("TIME UTC", 70),
            ("BAND", 56), ("MODE", 56), ("FREQ MHz", 82),
            ("RST SENT", 70), ("RST RCVD", 70), ("QSL", 66),
        ]
        vals_bot = (
            [str(qso.get("call","") or ""), str(qso.get("date","") or ""),
             str(qso.get("time","") or ""), str(qso.get("band","") or ""),
             str(qso.get("mode","") or ""), freq_disp,
             str(qso.get("rst_s","") or ""), str(qso.get("rst_r","") or ""), ""]
            if qso else [""] * len(cols_bot)
        )
        cx_ = 6
        for i, (col_lbl, col_w3) in enumerate(cols_bot):
            if i > 0:
                c.create_line(cx_-1, 336, cx_-1, 409, fill="#c4bda0", width=1)
            c.create_text(cx_+2, 340, text=col_lbl, anchor="nw",
                          fill="#445566", font=("Arial", 6, "bold"))
            c.create_line(cx_, 368, cx_+col_w3-4, 368, fill="#aaa08a", width=1)
            if col_lbl == "QSL":
                c.create_text(cx_+2, 371, text="☐ YES  ☐ NO", anchor="nw",
                              fill="#445566", font=("Arial", 7))
            elif i < len(vals_bot) and vals_bot[i]:
                c.create_text(cx_+2, 350, text=vals_bot[i], anchor="nw",
                              fill="#1a2a3a", font=("Arial", 9, "bold"))
            cx_ += col_w3

        # ── 4. PIED (y=410–420) ────────────────────────────────────────────
        c.create_rectangle(0, 410, W, 420, fill=DARK, outline="")
        c.create_text(W//2, 415, anchor="center",
                      text="ON5AM  •  Ans, JO20SP  •  Belgique  •  73 de Albert  •  hamanalyst.org",
                      fill="#446688", font=("Arial", 7))

    def _generate_qsl_card(self):
        qso = self._get_selected_qso()
        if not qso:
            messagebox.showinfo("QSL Card","Sélectionnez d'abord un QSO dans l'onglet Journal.")
            return
        self._draw_qsl_card_preview(qso)

    def _save_qsl_card(self):
        if not self._qsl_last_qso:
            messagebox.showinfo("QSL", "Générez d'abord une carte."); return
        from tab_qsl import generate_qsl_pdf
        fn = filedialog.asksaveasfilename(defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            title="Enregistrer la QSL Card")
        if not fn:
            return
        try:
            import shutil
            pdf = generate_qsl_pdf(self._qsl_last_qso)
            shutil.move(pdf, fn)
            messagebox.showinfo("QSL Card", f"Carte enregistrée :\n{fn}")
            self.status_var.set(f"🖨️ QSL Card sauvegardée : {os.path.basename(fn)}")
        except Exception as exc:
            messagebox.showerror("Erreur", str(exc))

    def _print_qsl_card(self):
        if not self._qsl_last_qso:
            messagebox.showinfo("QSL", "Générez d'abord une carte."); return
        from tab_qsl import generate_qsl_pdf
        import subprocess
        try:
            tmp = generate_qsl_pdf(self._qsl_last_qso)
            if os.name == 'nt':
                os.startfile(tmp, "print")
            else:
                subprocess.Popen(["lpr", tmp])
            self.status_var.set("🖨️ QSL Card envoyée à l'imprimante")
        except Exception as exc:
            messagebox.showinfo("Impression",
                f"Fichier PDF créé.\nOuvrez-le et imprimez manuellement.\n\n{exc}")

    # ==========================================
    # --- WIKI / AIDE ---
    # ==========================================
    def _build_wiki_tab(self, parent):
        from tab_wiki import (
            wiki_quickstart, wiki_dashboard, wiki_journal, wiki_cluster,
            wiki_cluster_enrichi, wiki_spot_history, wiki_flex, wiki_awards,
            wiki_graphs, wiki_heatmap, wiki_propagation, wiki_grayline,
            wiki_psk, wiki_qsl, wiki_cat, wiki_config, wiki_troubleshoot,
            wiki_ft8_decodium, wiki_spe_expert,
        )
        nb_wiki = ttk.Notebook(parent, bootstyle="info")
        nb_wiki.pack(fill="both", expand=True, padx=5, pady=5)

        sections = {
            "🚀 Démarrage rapide": wiki_quickstart(),
            "🏠 Dashboard":        wiki_dashboard(),
            "📖 Journal":          wiki_journal(),
            "🌍 Carte & DX Cluster": wiki_cluster(),
            "📡 DX Cluster enrichi": wiki_cluster_enrichi(),
            "📜 Spot History":     wiki_spot_history(),
            "📻 Flex-6500":        wiki_flex(),
            "🏆 DXCC & Awards":    wiki_awards(),
            "📊 Graphiques & Stats": wiki_graphs(),
            "🗺️ Heatmap":          wiki_heatmap(),
            "🌐 Propagation":      wiki_propagation(),
            "🌙 Grayline":         wiki_grayline(),
            "📻 PSK Reporter":     wiki_psk(),
            "🖨️ QSL & LoTW":       wiki_qsl(),
            "📻 Mémoires & CAT":   wiki_cat(),
            "⚙️ Configuration":    wiki_config(),
            "📡 FT8 & Decodium":   wiki_ft8_decodium(),
            "⚡ Ampli SPE Expert":  wiki_spe_expert(),
            "🔧 Dépannage":        wiki_troubleshoot(),
        }
        for title, content in sections.items():
            frame = tk.Frame(nb_wiki, bg="#11273f")
            nb_wiki.add(frame, text=title)
            txt = tk.Text(frame, font=("Consolas",10), bg="#11273f", fg="#e8f0fe",
                          padx=20, pady=15, wrap="word", spacing1=2, spacing2=1)
            txt.pack(fill="both", expand=True)
            sb = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
            txt.configure(yscroll=sb.set); sb.pack(side="right", fill="y"); txt.pack(side="left",fill="both",expand=True)
            txt.tag_configure("h1", font=("Impact",16), foreground="#f39c12", spacing1=8, spacing3=4)
            txt.tag_configure("h2", font=("Arial",12,"bold"), foreground="#3daee9", spacing1=6, spacing3=2)
            txt.tag_configure("h3", font=("Arial",10,"bold"), foreground="#3fb950", spacing1=4)
            txt.tag_configure("code", font=("Consolas",9), foreground="#e67e22", background="#11273f")
            txt.tag_configure("tip",  font=("Arial",9,"italic"), foreground="#f39c12")
            txt.tag_configure("warn", font=("Arial",9,"bold"), foreground="#f85149")
            txt.tag_configure("ok",   font=("Arial",9), foreground="#3fb950")
            for line in content:
                tag, text = line
                txt.insert("end", text + "\n", tag)
            txt.config(state="disabled")

    # ==========================================
    # --- FENÊTRE DE CONFIGURATION ---
    # ==========================================
    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("⚙️ Paramètres de la station")
        win.geometry("560x600")
        win.resizable(False, False)
        win.grab_set()

        nb = ttk.Notebook(win, bootstyle="primary")
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        cfg = configparser.ConfigParser(); cfg.read(CONFIG_FILE)

        def get(section, key, fallback=""):
            try: return cfg.get(section, key)
            except: return fallback

        entries = {}

        def make_tab(parent, fields):
            frm = ttk.Frame(parent, padding=15)
            for i, (lbl, sec, key, default, show) in enumerate(fields):
                ttk.Label(frm, text=lbl, width=24, anchor="e").grid(row=i, column=0, pady=6, padx=5, sticky="e")
                e = ttk.Entry(frm, width=30, show=show)
                e.insert(0, get(sec, key, default))
                e.grid(row=i, column=1, pady=6, padx=5, sticky="w")
                entries[(sec, key)] = e
            return frm

        # Station
        tab_station = ttk.Frame(nb); nb.add(tab_station, text="🏠 Station")
        make_tab(tab_station, [
            ("Indicatif (Callsign):", "USER", "Callsign", MY_CALL, ""),
            ("Locator (Grid square):", "USER", "Grid", MY_GRID, ""),
        ]).pack(fill="x")
        ttk.Label(tab_station, text="Exemple de locator: JO20SP", foreground="gray").pack(pady=2)

        # CAT
        tab_cat = ttk.Frame(nb); nb.add(tab_cat, text="📻 CAT Transceiver")
        make_tab(tab_cat, [
            ("Port série:", "CAT", "Port", CAT_PORT, ""),
            ("Vitesse (baud):", "CAT", "Baud", str(CAT_BAUD), ""),
        ]).pack(fill="x")
        ttk.Label(tab_cat, text="Ex: COM4 (Windows) ou /dev/ttyUSB0 (Linux)", foreground="gray").pack(pady=2)
        ttk.Label(tab_cat, text="Vitesses courantes: 4800, 9600, 19200, 38400", foreground="gray").pack(pady=2)

        # API
        tab_api = ttk.Frame(nb); nb.add(tab_api, text="🔑 API / Comptes")
        make_tab(tab_api, [
            ("QRZ Utilisateur:", "API", "QRZ_User", get("API","QRZ_User",""), ""),
            ("QRZ Mot de passe:", "API", "QRZ_Pass", "", "*"),
            ("QRZ API Key (XML):", "API", "QRZ_Key", get("API","QRZ_Key",""), "*"),
            ("QRZ Logbook Key:", "API", "QRZ_Log_Key", get("API","QRZ_Log_Key",""), "*"),
            ("TQSL Chemin:", "LOTW", "Tqsl_Path", get("LOTW","Tqsl_Path","C:\\Program Files (x86)\\TrustedQSL\\tqsl.exe"), ""),
            ("LoTW Indicatif:", "LOTW", "Callsign", get("LOTW","Callsign",MY_CALL), ""),
            ("LoTW Utilisateur:", "LOTW", "User", get("LOTW","User",MY_CALL), ""),
            ("LoTW Mot de passe:", "LOTW", "Pass", "", "*"),
            ("eQSL Utilisateur:", "API", "EQSL_User", get("API","EQSL_User",""), ""),
            ("eQSL Mot de passe:", "API", "EQSL_Pass", "", "*"),
            ("ClubLog Email:", "API", "Club_Email", get("API","Club_Email",""), ""),
            ("ClubLog Password:", "API", "Club_Pass", "", "*"),
            ("ClubLog Callsign:", "API", "Club_Call", get("API","Club_Call",""), ""),
            ("ClubLog API Key:", "API", "Club_Key", get("API","Club_Key",""), "*"),
        ]).pack(fill="x")

        # DX Cluster
        tab_cl = ttk.Frame(nb); nb.add(tab_cl, text="📡 DX Cluster")
        make_tab(tab_cl, [
            ("Serveur (host):", "CLUSTER", "Host", get("CLUSTER","Host","on0dxk.dyndns.org"), ""),
            ("Port:", "CLUSTER", "Port", get("CLUSTER","Port","8000"), ""),
            ("Indicatif login:", "CLUSTER", "Call", get("CLUSTER","Call",MY_CALL), ""),
        ]).pack(fill="x")

        # LoTW
        tab_lotw = ttk.Frame(nb); nb.add(tab_lotw, text="📋 LoTW / TQSL")
        frm_lotw = make_tab(tab_lotw, [
            ("Indicatif LoTW:", "LOTW", "Callsign", get("LOTW","Callsign",MY_CALL), ""),
            ("Chemin TQSL:", "LOTW", "Tqsl_Path", get("LOTW","Tqsl_Path","C:\\Program Files (x86)\\TQSL\\tqsl.exe"), ""),
        ])
        frm_lotw.pack(fill="x")
        ttk.Label(tab_lotw, text="Chemin vers tqsl.exe pour ouverture automatique après export.", foreground="gray", wraplength=480).pack(padx=15, pady=3, anchor="w")

        # DXCC Alertes
        tab_dxcc = ttk.Frame(nb); nb.add(tab_dxcc, text="🏆 DXCC Alertes")
        make_tab(tab_dxcc, [
            ("Bandes alertes:", "DXCC", "Alert_Bands", get("DXCC","Alert_Bands","20m,15m,10m"), ""),
            ("Pays alertes:", "DXCC", "Alert_Countries", get("DXCC","Alert_Countries",""), ""),
        ]).pack(fill="x")
        ttk.Label(tab_dxcc, text="Ex bandes: 20m,15m,10m\nEx pays: Japan,USA,Australia", foreground="gray", justify="left").pack(padx=15, anchor="w")

        # UDP / WSJT-X
        tab_udp = ttk.Frame(nb); nb.add(tab_udp, text="📻 UDP / WSJT-X")
        frm_udp = ttk.Frame(tab_udp, padding=15); frm_udp.pack(fill="x")

        ttk.Label(frm_udp, text="Configuration UDP — Réception des QSOs depuis WSJT-X / GridTracker",
                  font=("Arial",10,"bold"), foreground="#f39c12").grid(row=0, column=0, columnspan=2, pady=(0,12), sticky="w")

        # Source
        ttk.Label(frm_udp, text="Source à écouter :", width=24, anchor="e").grid(row=1, column=0, padx=5, pady=6, sticky="e")
        udp_source_var = tk.StringVar(value=get("UDP","Source","wsjtx"))
        cb_source = ttk.Combobox(frm_udp, textvariable=udp_source_var, width=28,
                                  values=["wsjtx", "gridtracker", "les_deux"], state="readonly")
        cb_source.grid(row=1, column=1, padx=5, pady=6, sticky="w")

        # Port WSJT-X
        ttk.Label(frm_udp, text="Port WSJT-X :", width=24, anchor="e").grid(row=2, column=0, padx=5, pady=6, sticky="e")
        e_wsjtx_port = ttk.Entry(frm_udp, width=10)
        e_wsjtx_port.insert(0, get("UDP","WsjtxPort","2237"))
        e_wsjtx_port.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        entries[("UDP","WsjtxPort")] = e_wsjtx_port

        # Multicast IP
        ttk.Label(frm_udp, text="IP Multicast WSJT-X :", width=24, anchor="e").grid(row=3, column=0, padx=5, pady=6, sticky="e")
        e_mcast = ttk.Entry(frm_udp, width=16)
        e_mcast.insert(0, get("UDP","MulticastIP","224.0.0.1"))
        e_mcast.grid(row=3, column=1, padx=5, pady=6, sticky="w")
        entries[("UDP","MulticastIP")] = e_mcast

        # Port GridTracker ADIF
        ttk.Label(frm_udp, text="Port GridTracker (ADIF) :", width=24, anchor="e").grid(row=4, column=0, padx=5, pady=6, sticky="e")
        e_gt_port = ttk.Entry(frm_udp, width=10)
        e_gt_port.insert(0, get("UDP","GridtrackerPort","2333"))
        e_gt_port.grid(row=4, column=1, padx=5, pady=6, sticky="w")
        entries[("UDP","GridtrackerPort")] = e_gt_port

        # Aide
        ttk.Separator(frm_udp).grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
        help_text = (
            "wsjtx      → Écoute uniquement WSJT-X sur le port WSJT-X (recommandé)\n"
            "gridtracker → Écoute uniquement GridTracker sur le port ADIF\n"
            "les_deux   → Écoute les deux (risque de doublons si GridTracker\n"
            "              retransmet aussi vers ce logbook)\n\n"
            "Configuration WSJT-X (File → Settings → Reporting) :\n"
            "  UDP Server : 224.0.0.1   Port : 2237\n"
            "  ✅ Accept UDP requests\n\n"
            "Si vous utilisez GridTracker : désactivez dans GridTracker\n"
            "le renvoi ADIF vers ce logbook, et choisissez 'wsjtx'."
        )
        ttk.Label(frm_udp, text=help_text, foreground="#aaa", font=("Consolas",8),
                  justify="left").grid(row=6, column=0, columnspan=2, padx=5, sticky="w")

        # Lier la variable source (pas dans entries car c'est un StringVar)
        def _save_udp_source():
            new_cfg = configparser.ConfigParser(); new_cfg.read(CONFIG_FILE)
            if not new_cfg.has_section("UDP"): new_cfg.add_section("UDP")
            new_cfg.set("UDP", "Source", udp_source_var.get())
            with open(CONFIG_FILE, 'w') as f: new_cfg.write(f)
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy()))

        # Backup
        tab_bk = ttk.Frame(nb); nb.add(tab_bk, text="💾 Backup")
        frm_bk = ttk.Frame(tab_bk, padding=15); frm_bk.pack(fill="x")
        ttk.Label(frm_bk, text="Dossier de backup :", font=("Arial",10)).pack(anchor="w", pady=(0,5))
        bk_dir_var = tk.StringVar(value=get("BACKUP","Dir", BACKUP_DIR))
        frm_bk2 = ttk.Frame(frm_bk); frm_bk2.pack(fill="x")
        e_bkdir = ttk.Entry(frm_bk2, textvariable=bk_dir_var, width=40)
        e_bkdir.pack(side="left", padx=(0,5))
        def browse_bk():
            d = filedialog.askdirectory(title="Choisir le dossier de backup")
            if d: bk_dir_var.set(d)
        ttk.Button(frm_bk2, text="📁 Parcourir", command=browse_bk, bootstyle="info-outline").pack(side="left")
        ttk.Separator(frm_bk).pack(fill="x", pady=10)
        ttk.Label(frm_bk, text="💡 Une sauvegarde est créée automatiquement\n   à chaque fermeture de Station Master.\n   Les 10 derniers backups sont conservés.",
                  foreground="gray", font=("Arial",9), justify="left").pack(anchor="w")
        entries[("BACKUP","Dir")] = e_bkdir

        # Boutons
        btn_frm = ttk.Frame(win); btn_frm.pack(fill="x", padx=10, pady=10)

        def save_and_close():
            global BACKUP_DIR
            new_cfg = configparser.ConfigParser(); new_cfg.read(CONFIG_FILE)
            for (sec, key), widget in entries.items():
                if not new_cfg.has_section(sec): new_cfg.add_section(sec)
                val = widget.get().strip()
                if val or key not in ("QRZ_Pass","EQSL_Pass","Club_Pass","Club_Key","QRZ_Key"):
                    new_cfg.set(sec, key, val)
            # Sauvegarder la source UDP (StringVar, pas dans entries)
            if not new_cfg.has_section("UDP"): new_cfg.add_section("UDP")
            new_cfg.set("UDP", "Source", udp_source_var.get())
            with open(CONFIG_FILE, 'w') as f: new_cfg.write(f)
            load_config_safe()
            self._load_cluster_filters()
            self._reload_udp_config()
            self.root.title(f"{MY_CALL} Station Master V21.0")
            self.status_var.set("✅ Configuration sauvegardée — Redémarrez pour appliquer tous les changements.")
            win.destroy()

        ttk.Button(btn_frm, text="💾 Enregistrer", command=save_and_close, bootstyle="success", width=18).pack(side="left", padx=5)
        ttk.Button(btn_frm, text="✖ Annuler", command=win.destroy, bootstyle="secondary", width=12).pack(side="right", padx=5)

    # ==========================================
    # --- ACTIONS ---
    # ==========================================
    # ==========================================
    # --- RECHERCHE AVANCÉE ---
    # ==========================================
    def _open_advanced_search(self):
        """Fenêtre de recherche avancée multi-critères."""
        win = tk.Toplevel(self.root)
        win.title("🔎 Recherche avancée")
        win.geometry("560x480")
        win.resizable(False, False)
        win.grab_set()
        win.configure(bg="#11273f")

        ttk.Label(win, text="🔎 Recherche avancée", font=("Consolas",16,"bold"),
                  foreground="#f39c12").pack(pady=(15,8))

        frm = ttk.Frame(win, padding=15); frm.pack(fill="x")

        def row(label, widget_factory, row_idx):
            ttk.Label(frm, text=label, width=22, anchor="e",
                      font=("Arial",10), foreground="#aaa").grid(row=row_idx, column=0, padx=8, pady=5, sticky="e")
            w = widget_factory()
            w.grid(row=row_idx, column=1, padx=8, pady=5, sticky="w")
            return w

        # Indicatif (partiel)
        e_call = row("Indicatif (partiel) :", lambda: ttk.Entry(frm, width=18, font=("Consolas",11)), 0)

        # Nom
        e_name = row("Nom :", lambda: ttk.Entry(frm, width=18), 1)

        # Pays
        e_country = row("Pays :", lambda: ttk.Entry(frm, width=18), 2)

        # QTH
        e_qth = row("QTH :", lambda: ttk.Entry(frm, width=18), 3)

        # Bande
        band_var = tk.StringVar(value="Toutes")
        e_band = row("Bande :", lambda: ttk.Combobox(frm, textvariable=band_var, width=10,
                     values=["Toutes","160m","80m","60m","40m","30m","20m","17m","15m","12m","10m","6m"]), 4)

        # Mode
        mode_var = tk.StringVar(value="Tous")
        e_mode = row("Mode :", lambda: ttk.Combobox(frm, textvariable=mode_var, width=10,
                     values=["Tous","SSB","CW","FT8","FT4","DIG","FM","AM"]), 5)

        # Plage de dates
        ttk.Label(frm, text="Date du :", width=22, anchor="e",
                  font=("Arial",10), foreground="#aaa").grid(row=6, column=0, padx=8, pady=5, sticky="e")
        date_frm = ttk.Frame(frm); date_frm.grid(row=6, column=1, padx=8, pady=5, sticky="w")
        e_date_from = ttk.Entry(date_frm, width=11, font=("Consolas",10))
        e_date_from.pack(side="left"); e_date_from.insert(0, "2020-01-01")
        ttk.Label(date_frm, text=" au ", foreground="#aaa").pack(side="left")
        e_date_to = ttk.Entry(date_frm, width=11, font=("Consolas",10))
        e_date_to.pack(side="left"); e_date_to.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # QSL statut
        qsl_var = tk.StringVar(value="Tous")
        e_qsl = row("Statut QSL :", lambda: ttk.Combobox(frm, textvariable=qsl_var, width=18,
                    values=["Tous","LoTW confirmé","LoTW en attente","eQSL confirmé","Non confirmé"]), 7)

        # Distance minimale
        ttk.Label(frm, text="Distance min. (km) :", width=22, anchor="e",
                  font=("Arial",10), foreground="#aaa").grid(row=8, column=0, padx=8, pady=5, sticky="e")
        dist_frm = ttk.Frame(frm); dist_frm.grid(row=8, column=1, padx=8, pady=5, sticky="w")
        e_dist_min = ttk.Entry(dist_frm, width=7, font=("Consolas",10)); e_dist_min.pack(side="left")
        ttk.Label(dist_frm, text="  max. :", foreground="#aaa").pack(side="left")
        e_dist_max = ttk.Entry(dist_frm, width=7, font=("Consolas",10)); e_dist_max.pack(side="left")

        # Commentaire
        e_comment = row("Commentaire :", lambda: ttk.Entry(frm, width=18), 9)

        # Résultat
        result_var = tk.StringVar(value="")
        ttk.Label(win, textvariable=result_var, foreground="#f39c12",
                  font=("Consolas",10)).pack(pady=3)

        def do_search():
            """Exécute la recherche et applique les filtres au journal."""
            c = self.conn.cursor()
            q = ("SELECT id, qso_date, time_on, callsign, name, qth, band, mode, "
                 "rst_sent, rst_rcvd, distance, grid, lotw_stat, eqsl_stat, comment "
                 "FROM qsos WHERE 1=1")
            params = []

            call_v = e_call.get().strip().upper()
            if call_v:
                q += " AND callsign LIKE ?"; params.append(f"%{call_v}%")

            name_v = e_name.get().strip()
            if name_v:
                q += " AND UPPER(name) LIKE ?"; params.append(f"%{name_v.upper()}%")

            qth_v = e_qth.get().strip()
            if qth_v:
                q += " AND UPPER(qth) LIKE ?"; params.append(f"%{qth_v.upper()}%")

            band_v = band_var.get()
            if band_v and band_v != "Toutes":
                q += " AND UPPER(band)=?"; params.append(band_v.upper())

            mode_v = mode_var.get()
            if mode_v and mode_v != "Tous":
                q += " AND mode=?"; params.append(mode_v)

            df = e_date_from.get().strip()
            dt = e_date_to.get().strip()
            if df: q += " AND qso_date >= ?"; params.append(df)
            if dt: q += " AND qso_date <= ?"; params.append(dt)

            qsl_v = qsl_var.get()
            if qsl_v == "LoTW confirmé":
                q += " AND UPPER(lotw_stat) IN ('OK','YES','Y','LOTW')"
            elif qsl_v == "LoTW en attente":
                q += " AND (lotw_stat IS NULL OR lotw_stat='Wait' OR lotw_stat='')"
            elif qsl_v == "eQSL confirmé":
                q += " AND UPPER(eqsl_stat) IN ('OK','YES','Y')"
            elif qsl_v == "Non confirmé":
                q += " AND (lotw_stat IS NULL OR lotw_stat NOT IN ('OK','YES','Y','LOTW'))"

            comment_v = e_comment.get().strip()
            if comment_v:
                q += " AND UPPER(comment) LIKE ?"; params.append(f"%{comment_v.upper()}%")

            q += " ORDER BY qso_date DESC, time_on DESC"
            rows = c.execute(q, params).fetchall()

            # Filtre distance (post-SQL car distance est texte)
            dist_min = e_dist_min.get().strip()
            dist_max = e_dist_max.get().strip()
            country_filter = e_country.get().strip().lower()

            filtered = []
            for r in rows:
                # Filtre pays
                if country_filter:
                    country_r = get_country_name(r[3]).lower()
                    if country_filter not in country_r: continue
                # Filtre distance
                try:
                    d_km, _ = calculate_dist_bearing(MY_GRID, r[11])
                    if d_km:
                        if dist_min and int(d_km) < int(dist_min): continue
                        if dist_max and int(d_km) > int(dist_max): continue
                except: pass
                filtered.append(r)

            result_var.set(f"✅ {len(filtered)} QSO(s) trouvé(s)")

            # Remplir le journal principal avec les résultats
            for item in self.tree.get_children():
                self.tree.delete(item)
            for r in filtered:
                d_km, bearing = calculate_dist_bearing(MY_GRID, r[11])
                country = get_country_name(r[3])
                self.tree.insert("", "end", values=(
                    r[0], country, r[1], r[2], r[3], r[4], r[5],
                    r[6], r[7], r[8], r[9],
                    d_km, f"{bearing}°" if bearing else "",
                    "", "", r[12], "", r[14], r[11]
                ))
            self.lbl_count.config(text=f"Résultats: {len(filtered)}")
            self.status_var.set(f"🔎 Recherche avancée : {len(filtered)} QSO(s) — Cliquez X dans Recherche pour réinitialiser")
            win.destroy()
            # Aller sur l'onglet Journal
            self.nb.select(1)

        def reset():
            self.e_s.delete(0, tk.END)
            self.cb_band.set("All")
            self.cb_mode.set("All")
            self.load_data()
            win.destroy()

        btn_f = ttk.Frame(win, padding=10); btn_f.pack(fill="x")
        ttk.Button(btn_f, text="🔍 Rechercher", command=do_search,
                   bootstyle="success", width=18).pack(side="left", padx=5)
        ttk.Button(btn_f, text="🔄 Réinitialiser journal", command=reset,
                   bootstyle="warning-outline", width=20).pack(side="left", padx=5)
        ttk.Button(btn_f, text="✖ Annuler", command=win.destroy,
                   bootstyle="secondary", width=12).pack(side="right", padx=5)

        # Bind Enter
        win.bind("<Return>", lambda e: do_search())

    def load_data(self, flt=""):
        for r in self.tree.get_children(): self.tree.delete(r)
        c = self.conn.cursor()
        q = ('SELECT id, "", qso_date, time_on, callsign, name, qth, band, mode, '
             'rst_sent, rst_rcvd, distance, "", qrz_stat, eqsl_stat, lotw_stat, '
             'club_stat, comment, grid FROM qsos WHERE 1=1')
        params = []
        search_term = self.e_s.get().upper()
        if search_term:
            if len(search_term) <= 3:
                q += " AND callsign LIKE ?"; params.append(search_term + "%")
            else:
                q += " AND (callsign LIKE ? OR name LIKE ?)"
                params.extend([f"%{search_term}%", f"%{search_term}%"])
        b_flt = self.cb_band.get(); m_flt = self.cb_mode.get()
        if b_flt and b_flt != "All": q += " AND UPPER(band)=?"; params.append(b_flt.upper())
        if m_flt and m_flt != "All": q += " AND mode=?"; params.append(m_flt)
        q += " ORDER BY qso_date DESC, time_on DESC"
        c.execute(q, params)
        rows = c.fetchall()
        for r in rows:
            d, b = calculate_dist_bearing(MY_GRID, r[18])
            country = get_country_name(r[4])
            nr = list(r); nr[1] = country; nr[11] = d; nr[12] = f"{b}°"
            self.tree.insert("", "end", values=nr)
        self.lbl_count.config(text=f"Total: {len(rows)}")

    def do_backup(self):
        global BACKUP_DIR
        try:
            bdir = BACKUP_DIR or os.path.join(os.path.dirname(os.path.abspath(__file__)), "Backups")
            if not os.path.exists(bdir): os.makedirs(bdir)
            fname = os.path.join(bdir, f"station_master_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db")
            shutil.copy("station_master.db", fname)
            messagebox.showinfo("Backup", f"✅ Sauvegarde réussie !\n\n📁 {fname}")
            self.status_var.set(f"💾 Backup : {os.path.basename(fname)}")
        except Exception as e:
            messagebox.showerror("Backup", f"Erreur : {e}")

    def _update_top_smeter(self, smeter_dbm):
        pass  # S-meter supprimé (non disponible via AetherSDR rigctld)

    def update_radio_info(self, t, v):
        if t == "FREQ":
            txt = f"VFO A: {int(v)/1000:,.1f} kHz"
            self.lbl_radio.config(text=txt, bootstyle="success-inverse")
            self.current_freq_hz = str(v)
        if t == "MODE": self.e_mode.delete(0,tk.END); self.e_mode.insert(0,v)
        if t == "SMETER":
            self.pb_smeter['value'] = v
            # Convertir valeur CAT (0-30) en dBm pour la barre rose
            dbm = -140.0 + (v / 30.0) * 107.0
            self._update_top_smeter(dbm)
        if t == "TX_STATUS":
            if v: self.lbl_radio.config(text="🔥 ON AIR 🔥", bootstyle="danger-inverse")
            else: self.lbl_radio.config(bootstyle="success-inverse")

    def on_cluster_spot(self, freq, call, comment, spotter, time_z, source="Cluster"):
        """Reçoit un nouveau spot DX (Cluster TCP ou DXHeat)."""
        band    = freq_to_band(freq)
        mode    = get_mode_from_freq(freq)
        country = get_country_name(call) or "Unknown"
        cont    = get_continent(call)

        spot = {
            "freq": freq, "call": call, "comment": comment,
            "spotter": spotter, "time_z": time_z, "band": band,
            "mode": mode, "country": country, "continent": cont,
            "source": source, "ts": datetime.now(timezone.utc),
        }
        self._all_spots.insert(0, spot)
        if len(self._all_spots) > 300:
            self._all_spots = self._all_spots[:300]

        # Stats session
        self._cluster_session_count += 1
        if country: self._cluster_session_countries.add(country)

        # Compteur activité par bande
        if hasattr(self, "_cluster_band_counts") and band:
            self._cluster_band_counts[band] = self._cluster_band_counts.get(band, 0) + 1

        # Alerte sonore
        if self.cluster_alert_var.get():
            tag = self._get_spot_tag(band, country, call)
            if tag in ("alert", "new_dxcc", "watchlist"):
                threading.Thread(target=_play_alert_sound, args=(1000, 300), daemon=True).start()
                label = {"new_dxcc":"🆕 Nouveau DXCC !","watchlist":"⭐ Watchlist !",
                         "alert":"🔔 Alerte DX Cluster"}.get(tag, "🔔 DX")
                threading.Thread(target=_send_toast,
                    args=(label, f"{call} — {country}\n{freq} kHz  {band}  {mode}  [{source}]"),
                    daemon=True).start()

        self.root.after(0, self._apply_cluster_filter)

    def on_cluster_click(self, e):
        """Double-clic sur un spot → syntonise la radio (colonne Freq = index 2)."""
        sel = self.tree_cl.selection()
        if sel:
            f_str = self.tree_cl.item(sel[0])["values"][2]  # index 2 = Freq
            try: self.cat.set_freq(float(f_str) * 1000)
            except: pass

    def _cluster_right_click(self, event):
        """Clic droit sur le cluster → menu contextuel."""
        row = self.tree_cl.identify_row(event.y)
        if not row:
            return
        self.tree_cl.selection_set(row)
        vals = self.tree_cl.item(row)["values"]
        # vals = (time_z, age, freq, band, mode, cont, country, call, az, km, spotter, source, comment)
        if not vals or len(vals) < 8:
            return
        freq    = vals[2]
        band    = vals[3]
        mode    = vals[4]
        country = vals[6]
        call    = vals[7]

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label=f"📋 Logger {call}  [{band} {mode}]",
            command=lambda: self._prefill_from_spot(call, freq, mode, country))
        menu.add_command(
            label=f"📻 Syntoniser radio → {freq} kHz",
            command=lambda: self._tune_spot_freq(freq, mode))
        menu.add_separator()
        menu.add_command(
            label=f"🔍 QRZ.com : {call}",
            command=lambda: __import__('webbrowser').open(f"https://www.qrz.com/db/{call}"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _prefill_from_spot(self, call, freq, mode, country):
        """Pré-remplit le formulaire Nouveau Contact depuis un spot cluster."""
        self.e_call.delete(0, tk.END)
        self.e_call.insert(0, call.upper())
        mode_clean = mode.upper() if mode else "SSB"
        self.e_mode.delete(0, tk.END)
        self.e_mode.insert(0, mode_clean)
        try:
            self.current_freq_hz = str(int(float(freq) * 1000))
        except Exception:
            pass
        self.e_comment.delete(0, tk.END)
        self.e_comment.insert(0, f"Spot: {country}")
        self._check_duplicate(None)
        self.nb.select(0)           # revenir au Dashboard / Journal
        self.e_call.focus_set()
        self.status_var.set(f"📋 Formulaire pré-rempli depuis spot : {call}  {freq} kHz  {mode_clean}")

    def _tune_spot_freq(self, freq, mode):
        """Syntonise la radio sur la fréquence d'un spot cluster."""
        try:
            freq_hz = float(freq) * 1000
            self.current_freq_hz = str(int(freq_hz))
            self.cat.set_freq(freq_hz)
            self.status_var.set(f"📻 Radio accordée : {freq} kHz  {mode}")
        except Exception as e:
            self.status_var.set(f"⚠️ Erreur syntonisation : {e}")

    def on_tree_select(self, e):
        sel = self.tree.selection()
        if not sel: return
        v = self.tree.item(sel[0])['values']
        if len(v) < 19: return
        pos = grid_to_latlon(v[18])
        if pos:
            if self.dx_marker: self.dx_marker.delete()
            if self.path_line: self.path_line.delete()
            self.dx_marker = self.map_widget.set_marker(pos[0], pos[1], text=v[4])
            h = grid_to_latlon(MY_GRID)
            if h: self.path_line = self.map_widget.set_path([h, pos], color="red", width=2); self.map_widget.set_position(pos[0], pos[1])
        callsign = v[4]
        threading.Thread(target=self._load_qrz_card, args=(callsign,), daemon=True).start()

        # ── Mise à jour automatique de la carte QSL ──────────────────────────
        qso = self._get_selected_qso()
        if qso:
            self.root.after(50, lambda q=qso: self._draw_qsl_card_preview(q))

    def _load_qrz_card(self, callsign):
        self.root.after(0, lambda: self.status_var.set(f"🔍 Recherche QRZ : {callsign}…"))
        info = self.qrz.get_info(callsign)
        self.root.after(0, lambda: self._open_qrz_window(callsign, info))

    def _open_qrz_window(self, callsign, info):
        if hasattr(self, '_qrz_win') and self._qrz_win and self._qrz_win.winfo_exists():
            self._qrz_win.destroy()

        win = tk.Toplevel(self.root)
        win.title(f"📋 Fiche QRZ — {callsign}")
        win.geometry("520x540")
        win.resizable(True, True)
        self._qrz_win = win

        hdr = ttk.Frame(win, bootstyle="dark", padding=12); hdr.pack(fill="x")
        ttk.Label(hdr, text=callsign, font=("Consolas", 24, "bold"), bootstyle="inverse-dark").pack(side="left", padx=10)

        # Photo QRZ (si PIL disponible et URL fournie)
        if info and _PIL_OK and info.get('image'):
            def _load_photo():
                try:
                    resp = requests.get(info['image'], timeout=8)
                    img = Image.open(io.BytesIO(resp.content))
                    img.thumbnail((90, 90), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    def _show():
                        lbl_photo = tk.Label(hdr, image=photo, bg="#11273f", bd=2, relief="groove")
                        lbl_photo.image = photo  # keep ref
                        lbl_photo.pack(side="right", padx=10)
                    win.after(0, _show)
                except Exception as e:
                    print(f"QRZ photo load error: {e}")
            threading.Thread(target=_load_photo, daemon=True).start()

        if not info:
            ttk.Label(win, text="❌ Aucune information trouvée sur QRZ.com\n\nVérifiez vos identifiants dans ⚙️ Paramètres → API / Comptes",
                      font=("Arial", 12), foreground="#f85149", justify="center").pack(expand=True)
            ttk.Button(win, text="🌐 Ouvrir sur QRZ.com", bootstyle="info-outline",
                       command=lambda: __import__('webbrowser').open(f"https://www.qrz.com/db/{callsign}")).pack(pady=10)
            self.status_var.set(f"QRZ: aucune info pour {callsign}")
            return

        sub = ttk.Frame(hdr, bootstyle="dark"); sub.pack(side="left", padx=10)
        ttk.Label(sub, text=info.get('name',''), font=("Arial", 14, "bold"), bootstyle="inverse-dark").pack(anchor="w")
        country_line = " · ".join(filter(None, [info.get('city',''), info.get('state',''), info.get('country','')]))
        ttk.Label(sub, text=country_line, font=("Arial", 10), bootstyle="inverse-dark", foreground="#aaaaaa").pack(anchor="w")

        body_frame = ttk.Frame(win); body_frame.pack(fill="both", expand=True, padx=15, pady=10)

        def row(label, value, highlight=False):
            if not value: return
            f = ttk.Frame(body_frame); f.pack(fill="x", pady=2)
            ttk.Label(f, text=label, width=18, anchor="e", font=("Arial", 10), foreground="#888").pack(side="left")
            color = "#f1c40f" if highlight else "white"
            ttk.Label(f, text=value, font=("Arial", 10, "bold"), foreground=color, wraplength=320, anchor="w").pack(side="left", padx=8)

        row("📡 Indicatif",   info.get('call',''))
        row("👤 Prénom",      info.get('fname',''))
        row("🏠 Adresse",     info.get('addr1',''))
        row("🏙️ Ville",       " ".join(filter(None,[info.get('zip',''), info.get('city',''), info.get('state','')])))
        row("🌍 Pays",        info.get('country',''))
        row("📍 Grid square", info.get('grid',''), highlight=True)
        row("🎂 Né en",       info.get('born',''))
        row("🪪 Classe",      info.get('lic_class',''), highlight=True)
        row("📅 Licence",     info.get('efdate',''))
        row("⏳ Expiration",  info.get('expdate',''))
        row("📧 Email",       info.get('email',''))
        row("📬 QSL Manager", info.get('qslmgr',''), highlight=True)
        row("📇 Alias(es)",   info.get('aliases',''))

        qsl_frame = ttk.Frame(body_frame); qsl_frame.pack(fill="x", pady=6)
        ttk.Label(qsl_frame, text="QSL électronique :", width=18, anchor="e", foreground="#888", font=("Arial",10)).pack(side="left")
        for label, val in [("LoTW", info.get('lotw','')), ("eQSL", info.get('eqsl',''))]:
            color = "#2ecc71" if val == "Y" else "#e74c3c"
            symbol = "✅" if val == "Y" else "❌"
            ttk.Label(qsl_frame, text=f"{symbol} {label}", foreground=color, font=("Arial", 10, "bold")).pack(side="left", padx=10)

        ttk.Separator(win).pack(fill="x", padx=15, pady=5)

        btn_fr = ttk.Frame(win); btn_fr.pack(fill="x", padx=15, pady=8)
        ttk.Button(btn_fr, text="🌐 Ouvrir sur QRZ.com", bootstyle="info",
                   command=lambda: __import__('webbrowser').open(f"https://www.qrz.com/db/{callsign}")).pack(side="left", padx=5)
        if info.get('bio'):
            ttk.Button(btn_fr, text="📖 Biographie", bootstyle="secondary",
                       command=lambda: __import__('webbrowser').open(info['bio'])).pack(side="left", padx=5)
        ttk.Button(btn_fr, text="✖ Fermer", bootstyle="danger-outline", command=win.destroy).pack(side="right", padx=5)

        self.status_var.set(f"QRZ ✅ {callsign} — {info.get('name','')} — {info.get('country','')}")

    def confirm_quit(self):
        if messagebox.askyesno("Quitter", "Fermer Station Master ?", icon="question"):
            self._do_auto_backup_on_quit()
            self.root.destroy()

    def _do_auto_backup_on_quit(self):
        """Backup automatique à la fermeture dans le dossier configuré."""
        global BACKUP_DIR
        try:
            bdir = BACKUP_DIR or os.path.join(os.path.dirname(os.path.abspath(__file__)), "Backups")
            if not os.path.exists(bdir):
                os.makedirs(bdir)
            fname = os.path.join(bdir, f"station_master_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db")
            shutil.copy("station_master.db", fname)
            # Garder seulement les 10 derniers backups automatiques
            all_bk = sorted([
                f for f in os.listdir(bdir)
                if f.startswith("station_master_") and f.endswith(".db")
            ])
            while len(all_bk) > 10:
                try: os.remove(os.path.join(bdir, all_bk.pop(0)))
                except: pass
        except Exception as e:
            print(f"Auto-backup error: {e}")

    def edit_qso(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        v = self.tree.item(sel[0])['values']
        qso_id = v[0]
        row = self.conn.cursor().execute(
            "SELECT qso_date, time_on, callsign, band, mode, rst_sent, rst_rcvd, name, qth, grid, freq, comment "
            "FROM qsos WHERE id=?", (qso_id,)).fetchone()
        if not row: return

        win = tk.Toplevel(self.root)
        win.title(f"✏️ Éditer QSO — {row[2]}")
        win.geometry("420x380")
        win.resizable(False, False)
        win.grab_set()

        fields = [
            ("Date (YYYY-MM-DD)",  row[0]),
            ("Heure UTC (HH:MM)",  row[1]),
            ("Indicatif",          row[2]),
            ("Bande",              row[3]),
            ("Mode",               row[4]),
            ("RST Envoyé",         row[5]),
            ("RST Reçu",           row[6]),
            ("Nom",                row[7]),
            ("QTH",                row[8]),
            ("Grid square",        row[9]),
            ("Fréquence (Hz)",     row[10] or ""),
            ("Commentaire",        row[11] or ""),
        ]
        keys = ["qso_date","time_on","callsign","band","mode","rst_sent","rst_rcvd","name","qth","grid","freq","comment"]

        frm = ttk.Frame(win, padding=15); frm.pack(fill="both", expand=True)
        entries = {}
        for i, (lbl, val) in enumerate(fields):
            ttk.Label(frm, text=lbl, anchor="e", width=20).grid(row=i, column=0, pady=3, padx=5, sticky="e")
            e = ttk.Entry(frm, width=25); e.insert(0, val if val is not None else "")
            e.grid(row=i, column=1, pady=3, padx=5, sticky="w")
            entries[keys[i]] = e

        def save():
            c = self.conn.cursor()
            c.execute(
                "UPDATE qsos SET qso_date=?, time_on=?, callsign=?, band=?, mode=?, "
                "rst_sent=?, rst_rcvd=?, name=?, qth=?, grid=?, freq=?, comment=? WHERE id=?",
                tuple(entries[k].get().strip() for k in keys) + (qso_id,)
            )
            self.conn.commit(); self.load_data(); win.destroy()

        btn_frm = ttk.Frame(win); btn_frm.pack(fill="x", padx=15, pady=8)
        ttk.Button(btn_frm, text="💾 Enregistrer", command=save, bootstyle="success", width=16).pack(side="left")
        ttk.Button(btn_frm, text="✖ Annuler", command=win.destroy, bootstyle="secondary", width=12).pack(side="right")

    def select_all(self):
        all_items = self.tree.get_children()
        if all_items:
            self.tree.selection_set(all_items)
            self.tree.focus(all_items[0])

    def clear_logbook(self):
        total = len(self.tree.get_children())
        if total == 0: messagebox.showinfo("Logbook vide", "Le journal est déjà vide."); return
        if not messagebox.askyesno("⚠️ Attention", f"Vous allez supprimer {total} QSO(s).\n\nCette opération est IRRÉVERSIBLE.\n\nVoulez-vous continuer ?", icon="warning"): return
        confirm = messagebox.askokcancel("Confirmation finale", f"Supprimer DÉFINITIVEMENT les {total} QSO(s) ?\n\nUn backup automatique sera créé.", icon="warning")
        if not confirm: return
        try:
            if not os.path.exists("Backups"): os.makedirs("Backups")
            fname = f"Backups/avant_effacement_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db"
            shutil.copy("station_master.db", fname)
        except Exception as e:
            messagebox.showwarning("Backup échoué", f"Impossible de sauvegarder :\n{e}\n\nAnnulation.")
            return
        self.conn.cursor().execute("DELETE FROM qsos")
        self.conn.commit()
        self.load_data()
        self.status_var.set(f"🗑️ Logbook vidé — backup : {fname}")

    def del_qso(self):
        sel = self.tree.selection()
        if not sel: return
        n = len(sel)
        if messagebox.askyesno("Supprimer", f"Supprimer {n} QSO(s) sélectionné(s) ?"):
            c = self.conn.cursor()
            for item in sel:
                c.execute("DELETE FROM qsos WHERE id=?", (self.tree.item(item)['values'][0],))
            self.conn.commit(); self.load_data()

    def manual_mark(self, col):
        sel = self.tree.selection()
        if not sel: return
        c = self.conn.cursor()
        for item in sel:
            c.execute(f"UPDATE qsos SET {col}='OK' WHERE id=?", (self.tree.item(item)['values'][0],))
        self.conn.commit(); self.load_data()

    def export_selection(self):
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("Info", "Sélectionnez des lignes d'abord"); return
        fn = filedialog.asksaveasfilename(defaultextension=".adi", filetypes=[("ADIF", "*.adi")])
        if not fn: return
        try:
            with open(fn, "w") as f:
                f.write(f"ADIF Export by {MY_CALL} Station Master\n<EOH>\n")
                for item in sel:
                    v = self.tree.item(item)['values']
                    row = self.conn.cursor().execute("SELECT freq FROM qsos WHERE id=?", (v[0],)).fetchone()
                    freq_mhz = ""
                    if row and row[0]:
                        try: freq_mhz = f"{float(row[0])/1e6:.6f}" if float(row[0]) > 1e4 else f"{float(row[0]):.6f}"
                        except: freq_mhz = ""
                    def adif(tag, val):
                        val = str(val) if val else ""
                        return f"<{tag}:{len(val)}>{val}" if val else ""
                    rec  = adif("CALL", v[4])
                    rec += adif("QSO_DATE", str(v[2]).replace('-',''))
                    rec += adif("TIME_ON",  str(v[3]).replace(':',''))
                    rec += adif("BAND",  v[7])
                    rec += adif("MODE",  v[8])
                    rec += adif("FREQ",  freq_mhz)
                    rec += adif("RST_SENT", v[9])
                    rec += adif("RST_RCVD", v[10])
                    rec += adif("NAME",  v[5])
                    rec += adif("QTH",   v[6])
                    rec += adif("GRIDSQUARE", v[18])
                    rec += adif("COMMENT",    v[17])
                    rec += "<EOR>\n"
                    f.write(rec)
            messagebox.showinfo("Export", "Fichier ADIF créé !")
        except Exception as e: messagebox.showerror("Err", str(e))

    def manual_lookup(self):
        i = self.qrz.get_info(self.e_call.get().upper())
        if i:
            self.e_name.delete(0, tk.END); self.e_name.insert(0, i['name']); self.current_manual_grid = i['grid']
            d, b = calculate_dist_bearing(MY_GRID, i['grid'])
            self.status_var.set(f"Info: {i['name']} - {d} km - {b}°")

    def add_manual_qso(self):
        callsign = self.e_call.get().strip().upper()
        if not callsign: messagebox.showwarning("Attention", "Veuillez saisir un indicatif !"); return
        try:
            now = datetime.now(timezone.utc)
            info = self.qrz.get_info(callsign)
            qth  = info['city'] if info else ""
            grid = info['grid'] if info else self.current_manual_grid
            com  = self.e_comment.get()
            d_km, bearing = calculate_dist_bearing(MY_GRID, grid)
            d = (now.strftime('%Y-%m-%d'), now.strftime('%H:%M'), callsign,
                 freq_to_band(self.current_freq_hz), self.e_mode.get(),
                 self.e_rst_s.get(), self.e_rst_r.get(), self.e_name.get(),
                 qth, "", "", str(d_km) if d_km else "", grid, self.current_freq_hz,
                 "Wait", "Wait", "No", "Wait", com)
            c = self.conn.cursor()
            c.execute("INSERT INTO qsos (qso_date, time_on, callsign, band, mode, "
                      "rst_sent, rst_rcvd, name, qth, qsl_sent, qsl_rcvd, distance, "
                      "grid, freq, qrz_stat, eqsl_stat, lotw_stat, club_stat, comment) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", d)
            lid = c.lastrowid; self.conn.commit()
            threading.Thread(target=self.process_uploads, args=(d, lid), daemon=True).start()
            self.e_call.delete(0, tk.END); self.e_name.delete(0, tk.END)
            self.e_comment.delete(0, tk.END); self.current_manual_grid = ""
            self.load_data()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ajouter le QSO :\n{e}")

    def udp_listener(self):
        """Écoute les paquets UDP WSJT-X sur le port configuré (défaut 2237).
        
        Supporte :
        - Type 5  : QSO Logged directement depuis WSJT-X
        - Type 12 : ADIF QSO Logged (format texte ADIF)
        """
        port     = self._udp_wsjtx_port
        mcast_ip = self._udp_mcast_ip
        print(f"WSJT-X UDP listener démarré — port {port}  multicast {mcast_ip}")
        while True:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass  # SO_REUSEPORT absent sur certains kernels
                sock.settimeout(5.0)
                sock.bind(('', port))
                try:
                    # ip_mreq = 8 bytes : 4 (groupe) + 4 (interface locale)
                    # "4sl" natif = 16 bytes sur Linux 64-bit → setsockopt échoue !
                    # Rejoindre sur INADDR_ANY (interface réseau par défaut)
                    mreq = socket.inet_aton(mcast_ip) + b'\x00\x00\x00\x00'
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                except: pass
                try:
                    # Rejoindre aussi sur loopback (Decodium envoie via l'interface lo)
                    mreq_lo = socket.inet_aton(mcast_ip) + socket.inet_aton("127.0.0.1")
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq_lo)
                except: pass
                self.root.after(0, lambda: self.lbl_data.config(
                    text=f"RX DATA ✅ (port {port})", foreground="#3fb950"))

                while True:
                    try:
                        d, _ = sock.recvfrom(4096)
                    except socket.timeout:
                        continue

                    self.root.after(0, lambda: self.lbl_data.config(foreground="green"))
                    self.root.after(200, lambda: self.lbl_data.config(foreground="#3fb950"))

                    if len(d) < 12:
                        continue  # paquet trop court

                    # Vérifie le magic WSJT-X 0xADBCCBDA avant de parser
                    if struct.unpack('>I', d[:4])[0] != 0xADBCCBDA:
                        continue  # paquet non-WSJT-X (ADIF texte, GridTracker, etc.)

                    if self._ft8_monitor:
                        self._ft8_monitor.on_raw_packet(d)

                    try:
                        p = WSJTXPacket(d)

                        # ── Type 5 : QSO Logged (binaire WSJT-X) ──────────────────────
                        if p.msg_type == 5:
                            p.read_str()          # Id (nom appli ex "WSJT-X")
                            p.read_qdatetime()    # DateTimeOff (fin QSO)
                            call     = p.read_str()
                            grid     = p.read_str()
                            freq_hz  = p.read_u64()
                            mode     = p.read_str()
                            rst_sent = p.read_str()
                            rst_rcvd = p.read_str()
                            # tx_power = p.read_str()  # non utilisé
                            # comments = p.read_str()  # non utilisé

                            if not call: continue
                            self._store_wsjtx_qso(call, grid, freq_hz, mode, rst_sent, rst_rcvd)

                        # ── Type 12 : ADIF QSO Logged ─────────────────────────────────
                        # WSJT-X envoie type 5 ET type 12 pour chaque QSO.
                        # On traite le type 12 UNIQUEMENT pour GridTracker (qui n'envoie pas type 5).
                        # Pour wsjtx, le type 5 (_store_wsjtx_qso) suffit — le type 12 causerait un doublon.
                        elif p.msg_type == 12 and self._udp_source == "gridtracker":
                            p.read_str()   # Id
                            adif_str = p.read_str()
                            if adif_str:
                                self._parse_adif_string(adif_str)

                    except Exception as e:
                        print(f"UDP parse error: {e}")

            except Exception as e:
                self.root.after(0, lambda: self.lbl_data.config(text="RX DATA ⚠️", foreground="#f85149"))
                print(f"UDP listener error: {e}")
            finally:
                try: sock.close()
                except: pass
            time.sleep(3)

    def adif_broadcast_listener(self):
        """Écoute le broadcast ADIF UDP sur le port GridTracker configuré (défaut 2333)."""
        port = self._udp_gt_port
        print(f"ADIF UDP listener actif sur port {port}")
        while True:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(5.0)
                sock.bind(('', port))

                while True:
                    try:
                        d, addr = sock.recvfrom(65535)
                    except socket.timeout:
                        continue

                    try:
                        text = d.decode('utf-8', errors='ignore')
                        # Le paquet ADIF commence souvent par un header, on cherche <CALL:
                        if '<CALL:' in text.upper() or '<QSO_DATE:' in text.upper():
                            self._parse_adif_string(text)
                            self.root.after(0, lambda: self.lbl_data.config(
                                text="RX ADIF ✅", foreground="#3fb950"))
                            self.root.after(3000, lambda: self.lbl_data.config(
                                text="RX DATA ✅", foreground="#3fb950"))
                    except Exception as e:
                        print(f"ADIF broadcast parse error: {e}")

            except Exception as e:
                print(f"ADIF broadcast listener error: {e}")
            finally:
                try: sock.close()
                except: pass
            time.sleep(3)

    def _store_wsjtx_qso(self, call, grid, freq_hz, mode, rst_sent, rst_rcvd):
        """Enregistre un QSO reçu depuis WSJT-X dans la base de données.
        
        Fenêtre anti-doublon 3 min : évite les doublons quand GridTracker
        ET WSJT-X envoient le même QSO sur leurs ports respectifs.
        """
        now_utc  = datetime.now(timezone.utc)
        now_date = now_utc.strftime('%Y-%m-%d')
        now_time = now_utc.strftime('%H:%M')
        band     = freq_to_band(str(freq_hz))
        now_mins = now_utc.hour * 60 + now_utc.minute
        print(f"[FT8] Reçu QSO: {call}  {band}  {mode}  freq={freq_hz}")

        # Cherche un doublon dans les 3 dernières minutes (même call + même bande)
        rows = self.conn.cursor().execute(
            "SELECT time_on FROM qsos WHERE callsign=? AND UPPER(band)=UPPER(?) AND qso_date=?",
            (call, band, now_date)
        ).fetchall()
        for (t,) in rows:
            try:
                h, m = int(t[:2]), int(t[3:5])
                if abs((h * 60 + m) - now_mins) <= 3:
                    print(f"[FT8] Doublon ignoré: {call} {band}")
                    return
            except: pass

        nm = ""; qth = ""; g = grid
        try:
            i = self.qrz.get_info(call)
            if i: nm = i['name']; qth = i['city']; g = g or i['grid']
        except: pass

        dt = (now_date, now_time, call, band, mode, rst_sent, rst_rcvd,
              nm, qth, "", "", "", g, str(freq_hz),
              "Wait", "Wait", "No", "Wait", "")
        c = self.conn.cursor()
        c.execute("INSERT INTO qsos (qso_date, time_on, callsign, band, mode, "
                  "rst_sent, rst_rcvd, name, qth, qsl_sent, qsl_rcvd, distance, "
                  "grid, freq, qrz_stat, eqsl_stat, lotw_stat, club_stat, comment) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", dt)
        self.conn.commit()
        print(f"[FT8] QSO sauvegardé: {call} {band} {mode}")
        # Réinitialise les filtres Journal pour que le nouveau QSO soit visible
        self.root.after(0, lambda: (
            self.cb_band.set("All"),
            self.cb_mode.set("All"),
            self.load_data(),
            self.status_var.set(f"✅ FT8 QSO : {call}  {band}  {mode}")
        ))

    def _parse_adif_string(self, adif_text):
        """Parse une string ADIF et enregistre les QSOs trouvés."""
        adif_upper = adif_text.upper()
        # Split sur <EOR> pour avoir les enregistrements
        records = re.split(r'<EOR>', adif_upper, flags=re.IGNORECASE)
        c = self.conn.cursor()
        inserted = 0
        for r in records:
            if '<CALL:' not in r: continue
            def gf(tag):
                m = re.search(rf'<{tag}:\d+(?::\w)?>([^<]+)', r, re.IGNORECASE)
                return m.group(1).strip() if m else ""
            call = gf("CALL")
            if not call: continue
            d_raw = gf("QSO_DATE")
            t_raw = gf("TIME_ON")
            qso_date = f"{d_raw[:4]}-{d_raw[4:6]}-{d_raw[6:]}" if len(d_raw) == 8 else \
                       datetime.now(timezone.utc).strftime('%Y-%m-%d')
            qso_time = f"{t_raw[:2]}:{t_raw[2:4]}" if len(t_raw) >= 4 else \
                       datetime.now(timezone.utc).strftime('%H:%M')
            band = gf("BAND") or freq_to_band(gf("FREQ"))
            mode = gf("MODE") or "FT8"
            rst_s = gf("RST_SENT") or "-59"
            rst_r = gf("RST_RCVD") or "-59"
            grid  = gf("GRIDSQUARE")
            name  = gf("NAME")
            qth   = gf("QTH")
            freq  = gf("FREQ")
            comment = gf("COMMENT")

            # Anti-doublon : même call + même bande dans ±3 min
            qso_mins = 0
            try:
                qso_mins = int(qso_time[:2]) * 60 + int(qso_time[3:5])
            except: pass
            rows_dup = c.execute(
                "SELECT time_on FROM qsos WHERE callsign=? AND UPPER(band)=UPPER(?) AND qso_date=?",
                (call, band, qso_date)
            ).fetchall()
            is_dup = False
            for (t,) in rows_dup:
                try:
                    h, m = int(t[:2]), int(t[3:5])
                    if abs((h * 60 + m) - qso_mins) <= 3:
                        is_dup = True; break
                except: pass
            if is_dup: continue

            c.execute("INSERT INTO qsos (qso_date, time_on, callsign, band, mode, "
                      "rst_sent, rst_rcvd, name, qth, qsl_sent, qsl_rcvd, distance, "
                      "grid, freq, qrz_stat, eqsl_stat, lotw_stat, club_stat, comment) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (qso_date, qso_time, call, band, mode, rst_s, rst_r,
                       name, qth, "", "", "", grid, freq,
                       "ADIF", "ADIF", "No", "ADIF", comment))
            inserted += 1  
        if (not name or not qth) and hasattr(self, 'qrz') and self.qrz:
                        row_id = c.lastrowid
                        threading.Thread(target=self._auto_qrz_lookup,
                                        args=(call, row_id), daemon=True).start()
        if inserted > 0:
            self.conn.commit()
            print(f"ADIF: {inserted} QSO(s) importé(s)")
            self.root.after(0, lambda: (
                self.cb_band.set("All"),
                self.cb_mode.set("All"),
                self.load_data(),
                self.status_var.set(f"✅ ADIF QSO importé ({inserted})")
            ))
    def _auto_qrz_lookup(self, call, row_id):
        """Lookup QRZ automatique après réception ADIF — complète nom/qth/grid."""
        try:
            info = self.qrz.get_info(call)
            if not info:
                return
            name = info.get('name', '')
            qth  = info.get('city', '')
            grid = info.get('grid', '')
            if name or qth or grid:
                c = self.conn.cursor()
                c.execute("UPDATE qsos SET name=COALESCE(NULLIF(name,''),?), "
                          "qth=COALESCE(NULLIF(qth,''),?), "
                          "grid=COALESCE(NULLIF(grid,''),?) WHERE id=?",
                          (name, qth, grid, row_id))
                self.conn.commit()
                self.root.after(0, self.load_data)
        except Exception as e:
            print(f"[QRZ auto-lookup] {e}")        

    def _upload_lotw_tqsl(self, d, row_id):
        """Signe et envoie automatiquement un QSO à LoTW via TQSL en ligne de commande.
        Commande : tqsl.exe -d -u -a compliant -c ON5AM <fichier.adi>
          -d = mode silencieux (pas de dialogue)
          -u = upload immédiat après signature
          -a compliant = ignore les doublons
          -c = indicatif du certificat
        """
        import subprocess, tempfile, os
        tqsl_path = CONF.get('LOTW', 'Tqsl_Path', fallback='') if CONF else ''
        if not tqsl_path or not os.path.exists(tqsl_path):
            print(f"[LoTW] TQSL introuvable : {tqsl_path}")
            return False

        # Construire le fichier ADIF temporaire
        date, time_, call, band, mode = d[0], d[1], d[2], d[3], d[4]
        rst_s, rst_r = d[5], d[6]
        date_adif = date.replace("-","")
        time_adif = time_.replace(":","")[:4]

        # Mode ADIF normalisé pour LoTW
        submodes = {"FT8":("MFSK","FT8"),"FT4":("MFSK","FT4"),
                    "JS8":("MFSK","JS8CALL"),"WSPR":("WSPR",""),"JT65":("JT65",""),"JT9":("JT9","")}
        mode_up = mode.upper()
        if mode_up in submodes:
            mode_adif, submode = submodes[mode_up]
        else:
            mode_adif, submode = mode_up, ""

        def af(tag, val):
            val = str(val).strip()
            return f"<{tag}:{len(val)}>{val} " if val else ""

        rec  = af("CALL", call)
        rec += af("QSO_DATE", date_adif)
        rec += af("TIME_ON", time_adif)
        rec += af("BAND", band)
        rec += af("MODE", mode_adif)
        if submode: rec += af("SUBMODE", submode)
        rec += af("RST_SENT", rst_s)
        rec += af("RST_RCVD", rst_r)
        rec += af("STATION_CALLSIGN", MY_CALL)
        rec += af("MY_GRIDSQUARE", MY_GRID)
        rec += "<EOR>\n"

        adif_content = f"<ADIF_VER:5>2.2.7 <EOH>\n{rec}"

        try:
            # Écrire le fichier ADIF temporaire
            tmp = tempfile.NamedTemporaryFile(
                suffix=".adi", mode="w", encoding="utf-8", delete=False)
            tmp.write(adif_content)
            tmp.flush(); tmp.close()
            adif_path = tmp.name

            # Lancer TQSL en mode silencieux
            lotw_call = CONF.get('LOTW', 'Callsign', fallback=MY_CALL) if CONF else MY_CALL
            cmd = [tqsl_path, "-d", "-u", "-a", "compliant",
                   "-c", lotw_call, adif_path]
            print(f"[LoTW] Commande : {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            ok = result.returncode == 0
            print(f"[LoTW] upload {call}: {'✅' if ok else '❌'} (code {result.returncode})")
            if result.stderr: print(f"[LoTW] stderr: {result.stderr[:200]}")

            # Nettoyer le fichier temp
            try: os.unlink(adif_path)
            except: pass

            return ok
        except subprocess.TimeoutExpired:
            print("[LoTW] Timeout — TQSL a mis trop de temps"); return False
        except Exception as e:
            print(f"[LoTW] Erreur : {e}"); return False

    def process_uploads(self, d, row_id):
        """Envoie le QSO vers eQSL, QRZ Logbook, Club Log et LoTW en arrière-plan."""
        call = d[2]
        updates = {}

        # ── eQSL ──────────────────────────────────────────────────────────────
        if self.eqsl.u and self.eqsl.p:
            ok = self.eqsl.upload_qso(d)
            updates['eqsl_stat'] = 'Sent' if ok else 'Wait'
            self.root.after(0, lambda ok=ok: self.status_var.set(
                f"{'✅' if ok else '❌'} eQSL : {call}"))

        # ── QRZ Logbook ───────────────────────────────────────────────────────
        if self.qrz_log.key:
            ok = self.qrz_log.upload_qso(d)
            updates['qrz_stat'] = 'Sent' if ok else 'Wait'

        # ── Club Log ──────────────────────────────────────────────────────────
        if self.club.email and self.club.p:
            ok = self.club.upload_qso(d)
            updates['club_stat'] = 'Sent' if ok else 'Wait'

        # ── LoTW via TQSL ─────────────────────────────────────────────────────
        tqsl_path = CONF.get('LOTW', 'Tqsl_Path', fallback='') if CONF else ''
        if tqsl_path and os.path.exists(tqsl_path):
            ok = self._upload_lotw_tqsl(d, row_id)
            updates['lotw_stat'] = 'Sent' if ok else 'Wait'
            self.root.after(0, lambda ok=ok: self.status_var.set(
                f"{'✅' if ok else '❌'} LoTW : {call}"))

        # Mettre à jour la DB
        if updates:
            try:
                c = self.conn.cursor()
                for col, val in updates.items():
                    c.execute(f"UPDATE qsos SET {col}=? WHERE id=?", (val, row_id))
                self.conn.commit()
                self.root.after(0, self.load_data)
            except Exception as e:
                print(f"[Upload] DB update error: {e}")

    def _resend_selected_qso(self):
        """Renvoie le QSO sélectionné vers eQSL/QRZ/ClubLog."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("QSL", "Sélectionnez d'abord un QSO dans le journal."); return
        v = self.tree.item(sel[0])['values']
        # Reconstruire le tuple d compatible avec upload_qso
        # (date, time, call, band, mode, rst_s, rst_r, ...)
        d = (v[2], v[3], v[4], v[7], v[8], v[9], v[10], v[5], v[6],
             "", "", v[11], "", "", "Wait", "Wait", "No", "Wait", "")
        row_id = v[0]
        threading.Thread(target=self.process_uploads, args=(d, row_id), daemon=True).start()
        self.status_var.set(f"📤 Envoi QSL en cours pour {v[4]}…")

    def check_incoming_qsl(self):
        """Vérifie les QSL reçues sur eQSL, QRZ et LoTW, met à jour le journal."""
        def _do():
            self.root.after(0, lambda: self.status_var.set("🔄 Vérification QSL reçues…"))
            total = 0

            # ── eQSL incoming ─────────────────────────────────────────────────
            confirmed_eqsl = self.eqsl.check_incoming()
            for q in confirmed_eqsl:
                try:
                    c = self.conn.cursor()
                    rows = c.execute(
                        "SELECT id FROM qsos WHERE callsign=? AND band=? COLLATE NOCASE",
                        (q['call'], q['band'])).fetchall()
                    for (rid,) in rows:
                        c.execute("UPDATE qsos SET eqsl_stat='OK' WHERE id=?", (rid,))
                        total += 1
                    self.conn.commit()
                except: pass

            # ── QRZ Logbook incoming ──────────────────────────────────────────
            confirmed_qrz = self.qrz_log.check_incoming()
            for q in confirmed_qrz:
                try:
                    c = self.conn.cursor()
                    rows = c.execute(
                        "SELECT id FROM qsos WHERE callsign=? AND band=? COLLATE NOCASE",
                        (q['call'], q['band'])).fetchall()
                    for (rid,) in rows:
                        c.execute("UPDATE qsos SET qrz_stat='OK' WHERE id=?", (rid,))
                        total += 1
                    self.conn.commit()
                except: pass

            # ── LoTW incoming via API ARRL ─────────────────────────────────────
            lotw_user = CONF.get('LOTW', 'User', fallback='') if CONF else ''
            lotw_pass = CONF.get('LOTW', 'Pass', fallback='') if CONF else ''
            confirmed_lotw = self._check_lotw_incoming(lotw_user, lotw_pass)
            for q in confirmed_lotw:
                try:
                    c = self.conn.cursor()
                    rows = c.execute(
                        "SELECT id FROM qsos WHERE callsign=? AND band=? COLLATE NOCASE",
                        (q['call'], q['band'])).fetchall()
                    for (rid,) in rows:
                        c.execute("UPDATE qsos SET lotw_stat='OK' WHERE id=?", (rid,))
                        total += 1
                    self.conn.commit()
                except: pass

            self.root.after(0, self.load_data)
            self.root.after(0, lambda: self.status_var.set(
                f"✅ {total} nouvelles confirmations QSL reçues"
                if total else "ℹ️ Aucune nouvelle confirmation QSL"))
            msg_detail = (f"  • eQSL  : {len(confirmed_eqsl)}\n"
                         f"  • QRZ   : {len(confirmed_qrz)}\n"
                         f"  • LoTW  : {len(confirmed_lotw)}")
            if total > 0:
                self.root.after(0, lambda: messagebox.showinfo(
                    "QSL Reçues",
                    f"✅ {total} nouvelles confirmations QSL !\n\n"
                    f"{msg_detail}\n\n"
                    "Les colonnes sont mises à jour dans le Journal."))
            else:
                self.root.after(0, lambda: messagebox.showinfo(
                    "QSL Reçues",
                    f"ℹ️ Aucune nouvelle confirmation.\n\n{msg_detail}"))

        threading.Thread(target=_do, daemon=True).start()

    def _check_lotw_incoming(self, user, password):
        """Télécharge les confirmations reçues sur LoTW via API ARRL.
        URL : https://lotw.arrl.org/lotwuser/lotwreport.adi
        """
        if not user or not password:
            print("[LoTW] Login non configuré — vérification impossible")
            return []
        try:
            url = "https://lotw.arrl.org/lotwuser/lotwreport.adi"
            params = {
                "login":           user,
                "password":        password,
                "qso_query":       "1",
                "qso_qsl":         "yes",
                "qso_withoutcall": "",
                "qso_qslsince":    "",
                "qso_owncall":     user,
            }
            print(f"[LoTW] Interrogation API pour {user}…")
            r = requests.get(url, params=params, timeout=30)

            if "login incorrect" in r.text.lower() or "password" in r.text.lower():
                print("[LoTW] ❌ Login incorrect")
                self.root.after(0, lambda: messagebox.showwarning(
                    "LoTW", "❌ Login LoTW incorrect.\nVérifiez dans ⚙️ Paramètres → LoTW."))
                return []

            # Parser l'ADIF reçu
            confirmed = []
            # Format ADIF : <CALL:N>callsign ... <BAND:N>band ...
            records = r.text.split('<EOR>')
            for rec in records:
                rec = rec.upper()
                m_call = re.search(r'<CALL:\d+>(\S+)', rec)
                m_band = re.search(r'<BAND:\d+>(\S+)', rec)
                m_date = re.search(r'<QSO_DATE:\d+>(\S+)', rec)
                if m_call and m_band:
                    confirmed.append({
                        'call': m_call.group(1).strip(),
                        'band': m_band.group(1).strip().lower(),
                        'date': m_date.group(1).strip() if m_date else '',
                    })
            print(f"[LoTW] {len(confirmed)} confirmations reçues")
            return confirmed
        except Exception as e:
            print(f"[LoTW] check_incoming error: {e}")
            return []

    def import_adif(self):
        fn = filedialog.askopenfilename(
            filetypes=[("ADIF files", "*.adi *.adif"), ("All files", "*.*")])
        if not fn: return
        with open(fn, 'r', errors='ignore') as f: content = f.read().upper()
        recs = content.split('<EOR>')
        cur = self.conn.cursor()
        inserted = skipped = 0
        for r in recs:
            if "<CALL:" not in r: continue
            def g(t): m = re.search(fr'<{t}:\d+>([^<]+)', r); return m.group(1).strip() if m else ""
            d = g("QSO_DATE"); ti = g("TIME_ON")
            df = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d
            tf = f"{ti[:2]}:{ti[2:4]}" if len(ti) >= 4 else ti
            call = g("CALL"); band = g("BAND"); mode = g("MODE")
            # Lire les vrais statuts QSL depuis l'ADIF
            def qsl_val(field):
                v = g(field)
                return 'Y' if v in ('Y', 'YES') else ('N' if v == 'N' else '')
            lotw  = qsl_val("LOTW_QSL_RCVD")
            eqsl  = qsl_val("EQSL_QSL_RCVD")
            qslr  = qsl_val("QSL_RCVD")
            qsls  = qsl_val("QSL_SENT")
            if not lotw: lotw = 'No'
            if not eqsl: eqsl = g("APP_EQSL_QSL_RCVD") or 'No'
            # Éviter les doublons (même call + date + heure + bande + mode)
            exists = cur.execute(
                "SELECT 1 FROM qsos WHERE callsign=? AND qso_date=? AND time_on=? AND band=? AND mode=?",
                (call, df, tf, band, mode)).fetchone()
            if exists:
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO qsos (qso_date, time_on, callsign, band, mode, rst_sent, rst_rcvd, "
                "name, qth, distance, grid, freq, qrz_stat, eqsl_stat, lotw_stat, club_stat, qsl_rcvd, qsl_sent, comment) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'Import',?,?,'Import',?,?,?)",
                (df, tf, call, band, mode, g("RST_SENT"), g("RST_RCVD"),
                 g("NAME"), g("QTH"), "", g("GRIDSQUARE"), "",
                 eqsl, lotw, qslr, qsls, g("COMMENT")))
            inserted += 1
        self.conn.commit()
        self.load_data()
        messagebox.showinfo("Import ADIF",
            f"✅ Import terminé\n\n"
            f"  Importés  : {inserted}\n"
            f"  Doublons  : {skipped} (ignorés)")

    # ==========================================
    # --- ONGLET FLEX-6500 ---
    # ==========================================
    def _build_flex_tab(self, parent):
        """Onglet Flex-6500 — VFO, TX/RX, Puissance, Infos radio."""
        BG  = "#11273f"
        BG2 = "#0d1e30"
        BG3 = "#0a1625"

        def lf(p, title, color="#f39c12"):
            return tk.LabelFrame(p, text=title, bg=BG, fg=color,
                                 font=("Arial", 10, "bold"),
                                 bd=1, relief="groove", padx=10, pady=8)

        # ── Barre connexion ──────────────────────────────────────────────────
        conn_fr = tk.Frame(parent, bg=BG2, pady=6)
        conn_fr.pack(fill="x", padx=6, pady=(6, 2))
        tk.Label(conn_fr, text="📡 FLEX-6500", bg=BG2, fg="#58a6ff",
                 font=("Consolas", 12, "bold")).pack(side="left", padx=10)
        tk.Label(conn_fr, text="IP:", bg=BG2, fg="#c9d1d9",
                 font=("Consolas", 10)).pack(side="left", padx=(14, 2))
        self._flex_ip_var = tk.StringVar(value="192.168.1.5")
        tk.Entry(conn_fr, textvariable=self._flex_ip_var, width=15,
                 bg="#21262d", fg="white", insertbackground="white",
                 relief="flat", font=("Consolas", 10)).pack(side="left")
        tk.Label(conn_fr, text="Port:", bg=BG2, fg="#c9d1d9",
                 font=("Consolas", 10)).pack(side="left", padx=(8, 2))
        self._flex_port_var = tk.StringVar(value="4992")
        tk.Entry(conn_fr, textvariable=self._flex_port_var, width=6,
                 bg="#21262d", fg="white", insertbackground="white",
                 relief="flat", font=("Consolas", 10)).pack(side="left")
        self._flex_conn_btn = tk.Button(
            conn_fr, text="  Connecter  ", bg="#238636", fg="white",
            relief="flat", font=("Consolas", 10, "bold"), cursor="hand2",
            activebackground="#2ea043", activeforeground="white",
            command=self._flex_toggle_connect)
        self._flex_conn_btn.pack(side="left", padx=14)
        self._flex_status_var = tk.StringVar(value="⚫  Non connecté")
        tk.Label(conn_fr, textvariable=self._flex_status_var, bg=BG2,
                 fg="#8b949e", font=("Consolas", 10)).pack(side="left", padx=6)

        # ── Barre propagation ────────────────────────────────────────────────
        prop_fr = tk.Frame(parent, bg=BG2, pady=5)
        prop_fr.pack(fill="x", padx=6, pady=(0, 4))
        tk.Label(prop_fr, text="☀  PROPAGATION", bg=BG2, fg="#3fb950",
                 font=("Consolas", 10, "bold")).pack(side="left", padx=(10, 12))
        self._flex_prop_lbls = {}
        for key, label, w in [("sfi","SFI",5),("ssn","SSN",5),
                               ("k","K-idx",5),("a","A-idx",5),
                               ("xray","X-Ray",6),("aurora","Aurora",6)]:
            frm = tk.Frame(prop_fr, bg=BG2); frm.pack(side="left", padx=10)
            tk.Label(frm, text=label, bg=BG2, fg="#8b949e",
                     font=("Consolas", 8)).pack()
            lbl = tk.Label(frm, text="—", bg=BG2, fg="#e6edf3",
                           font=("Consolas", 11, "bold"), width=w)
            lbl.pack()
            self._flex_prop_lbls[key] = lbl
        self._flex_prop_upd = tk.Label(prop_fr, text="", bg=BG2,
                                       fg="#8b949e", font=("Consolas", 8))
        self._flex_prop_upd.pack(side="right", padx=10)
        if not hasattr(self, "_flex_solar_started"):
            self._flex_solar_started = True
            threading.Thread(target=self._flex_solar_loop, daemon=True).start()

        # ── Corps principal (2 colonnes) ─────────────────────────────────────
        main = tk.Frame(parent, bg=BG)
        main.pack(fill="both", expand=True, padx=6, pady=4)
        left  = tk.Frame(main, bg=BG); left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(main, bg=BG, width=280)
        right.pack(side="left", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        # ── VFO ──────────────────────────────────────────────────────────────
        vfo_fr = lf(left, "🎚  Fréquence Active", "#58a6ff")
        vfo_fr.pack(fill="x", pady=(0, 8))

        # Bandeau indicateur de bande
        self._flex_band_canvas = tk.Canvas(vfo_fr, height=20, bg="#333333",
                                            highlightthickness=0)
        self._flex_band_canvas.pack(fill="x", pady=(0, 4))
        self._flex_band_rect = self._flex_band_canvas.create_rectangle(
            0, 0, 4000, 20, fill="#333333", outline="")
        self._flex_band_text = self._flex_band_canvas.create_text(
            10, 10, text="", fill="#11273f",
            font=("Consolas", 11, "bold"), anchor="w")

        # Fréquence — Frame wrapper pour isoler le bg du thème ttkbootstrap
        freq_wrap = tk.Frame(vfo_fr, bg=BG3)
        freq_wrap.pack(fill="x", pady=(2, 0))
        self._flex_freq_var = tk.StringVar(value="---.---")
        self._flex_freq_lbl = tk.Label(freq_wrap, textvariable=self._flex_freq_var,
                 font=("Consolas", 52, "bold"), fg="#e6edf3", bg=BG3,
                 anchor="w", padx=8)
        self._flex_freq_lbl.pack(fill="x")

        info_row = tk.Frame(vfo_fr, bg=BG); info_row.pack(fill="x", pady=(4, 0))
        self._flex_mode_var = tk.StringVar(value="MODE: —")
        self._flex_filt_var = tk.StringVar(value="Filtre: — Hz")
        self._flex_band_var = tk.StringVar(value="—")

        # Badge bande dans Frame coloré
        self._flex_band_frame = tk.Frame(info_row, bg="#555555", padx=12, pady=4)
        self._flex_band_frame.pack(side="right", padx=8)
        self._flex_band_lbl = tk.Label(self._flex_band_frame,
                 textvariable=self._flex_band_var,
                 font=("Consolas", 16, "bold"), fg="#11273f", bg="#555555")
        self._flex_band_lbl.pack()

        tk.Label(info_row, textvariable=self._flex_mode_var,
                 font=("Consolas", 14, "bold"), fg="#3fb950", bg=BG).pack(side="left", padx=6)
        tk.Label(info_row, textvariable=self._flex_filt_var,
                 font=("Consolas", 11), fg="#8b949e", bg=BG).pack(side="left", padx=10)

        # ── TX / RX ───────────────────────────────────────────────────────────
        txrx_fr = lf(left, "📶  TX / RX", "#f85149")
        txrx_fr.pack(fill="x", pady=(0, 8))
        txrx_row = tk.Frame(txrx_fr, bg=BG); txrx_row.pack(fill="x")
        self._flex_txrx_canvas = tk.Canvas(txrx_row, width=32, height=32,
                                            bg=BG, highlightthickness=0)
        self._flex_txrx_canvas.pack(side="left", padx=6)
        self._flex_txrx_dot = self._flex_txrx_canvas.create_oval(
            4, 4, 28, 28, fill="#3fb950", outline="")
        self._flex_txrx_lbl = tk.Label(txrx_row, text="RX  |  READY",
                 font=("Consolas", 13, "bold"), fg="#3fb950", bg=BG)
        self._flex_txrx_lbl.pack(side="left")
        self._flex_ilock_var = tk.StringVar(value="Interlock: READY")
        tk.Label(txrx_fr, textvariable=self._flex_ilock_var,
                 font=("Consolas", 10), fg="#8b949e", bg=BG).pack(anchor="w", padx=4, pady=(4,0))

        # ── Mesures ───────────────────────────────────────────────────────────
        msr_fr = lf(left, "📊  Mesures", "#d29922")
        msr_fr.pack(fill="x", pady=(0, 8))

        # ── Forward Power — VU-mètre vert→jaune→rouge ───────────────────────
        pwr_row = tk.Frame(msr_fr, bg=BG); pwr_row.pack(fill="x", pady=(0, 3))
        tk.Label(pwr_row, text="Puissance TX:", width=14, anchor="e",
                 font=("Consolas", 10), fg="#8b949e", bg=BG).pack(side="left")
        self._flex_pwr_val = tk.Label(pwr_row, text="0 W",
                 font=("Consolas", 22, "bold"), fg="#3fb950", bg=BG)
        self._flex_pwr_val.pack(side="left", padx=8)

        pwr_bar_fr = tk.Frame(msr_fr, bg=BG); pwr_bar_fr.pack(fill="x", padx=4, pady=(0,2))
        self._flex_pwr_canvas = tk.Canvas(pwr_bar_fr, width=400, height=28,
                                           bg="#0d1117", highlightthickness=1,
                                           highlightbackground="#21262d")
        self._flex_pwr_canvas.pack(fill="x")
        # Fond fantôme
        self._flex_pwr_canvas.create_rectangle(0, 0, 4000, 28, fill="#0a1a0a", outline="")
        # 3 segments VU-mètre : vert (0-55%), jaune (55-82%), rouge (82-100%)
        self._flex_pwr_seg_green  = self._flex_pwr_canvas.create_rectangle(0, 0, 0, 28, fill="#3fb950", outline="")
        self._flex_pwr_seg_yellow = self._flex_pwr_canvas.create_rectangle(0, 0, 0, 28, fill="#ffd93d", outline="")
        self._flex_pwr_seg_red    = self._flex_pwr_canvas.create_rectangle(0, 0, 0, 28, fill="#f85149", outline="")
        # Graduations verticales style VU
        for pct in [25, 50, 75, 90]:
            x = int(4000 * pct / 100)
            self._flex_pwr_canvas.create_line(x, 0, x, 28, fill="#1a2a1a", width=1)

        pwr_lbl_fr = tk.Frame(msr_fr, bg=BG); pwr_lbl_fr.pack(fill="x", padx=4)
        for txt in ["0","25 W","50 W","75 W","90 W","100W"]:
            tk.Label(pwr_lbl_fr, text=txt, fg="#555", bg=BG,
                     font=("Consolas", 7)).pack(side="left", expand=True)

        # SWR + ALC sur une ligne
        swr_row = tk.Frame(msr_fr, bg=BG); swr_row.pack(fill="x", pady=(6, 0))
        # SWR
        tk.Label(swr_row, text="SWR:", width=7, anchor="e",
                 font=("Consolas", 10), fg="#8b949e", bg=BG).pack(side="left")
        self._flex_swr_canvas = tk.Canvas(swr_row, width=180, height=16,
                                           bg="#0d1117", highlightthickness=1,
                                           highlightbackground="#21262d")
        self._flex_swr_canvas.pack(side="left", padx=4)
        self._flex_swr_canvas.create_rectangle(0, 0, 4000, 16, fill="#0d2e14", outline="")
        self._flex_swr_bar = self._flex_swr_canvas.create_rectangle(
            0, 0, 5, 16, fill="#3fb950", outline="")  # petit tick à 0 toujours visible
        self._flex_swr_val = tk.Label(swr_row, text="1.00:1", width=8,
                 font=("Consolas", 10, "bold"), fg="#3fb950", bg=BG, anchor="w")
        self._flex_swr_val.pack(side="left")
        # ALC
        tk.Label(swr_row, text="ALC:", width=5, anchor="e",
                 font=("Consolas", 10), fg="#8b949e", bg=BG).pack(side="left", padx=(12,0))
        self._flex_alc_canvas = tk.Canvas(swr_row, width=140, height=16,
                                           bg="#0d1117", highlightthickness=1,
                                           highlightbackground="#21262d")
        self._flex_alc_canvas.pack(side="left", padx=4)
        self._flex_alc_canvas.create_rectangle(0, 0, 4000, 16, fill="#1a0d2e", outline="")
        self._flex_alc_bar = self._flex_alc_canvas.create_rectangle(
            0, 0, 0, 16, fill="#bc8cff", outline="")
        self._flex_alc_val = tk.Label(swr_row, text="0.0 dB", width=8,
                 font=("Consolas", 10, "bold"), fg="#bc8cff", bg=BG, anchor="w")
        self._flex_alc_val.pack(side="left")

        # ── Infos Radio (colonne droite) ─────────────────────────────────────
        info_fr = lf(right, "📻  Infos Radio", "#3fb950")
        info_fr.pack(fill="x", pady=(0, 8))
        self._flex_info_vars = {}
        for key, label in [("rx_ant","Ant RX"), ("tx_ant","Ant TX"),
                            ("slices","Slices"), ("panadapts","Panadapts"),
                            ("filter","Filtre BF")]:
            row = tk.Frame(info_fr, bg=BG); row.pack(fill="x", pady=3)
            tk.Label(row, text=f"{label}:", width=12, anchor="e",
                     font=("Consolas", 10), fg="#8b949e", bg=BG).pack(side="left")
            var = tk.StringVar(value="—")
            tk.Label(row, textvariable=var, font=("Consolas", 10, "bold"),
                     fg="#e6edf3", bg=BG, anchor="w").pack(side="left", padx=4)
            self._flex_info_vars[key] = var

        # ── Bandes & Modes rapides ────────────────────────────────────────────
        band_fr = lf(parent, "Bandes & Modes rapides", "#c9d1d9")
        band_fr.pack(fill="x", padx=6, pady=(0, 6))
        band_row = tk.Frame(band_fr, bg=BG); band_row.pack(fill="x")
        BAND_COLS_BTN = {
            "160m":"#ff6b6b","80m":"#ff9f43","40m":"#ffd93d","30m":"#6bcb77",
            "20m":"#4d96ff","17m":"#c77dff","15m":"#ff6bff","12m":"#ff9fff",
            "10m":"#ff4757","6m":"#eccc68",
        }
        for bname, bfreq in [("160m",1.840),("80m",3.573),("40m",7.074),
                              ("30m",10.136),("20m",14.074),("17m",18.100),
                              ("15m",21.074),("12m",24.915),("10m",28.074),("6m",50.313)]:
            col = BAND_COLS_BTN.get(bname, "#888")
            tk.Button(band_row, text=bname, bg="#161b22", fg=col,
                      relief="flat", font=("Consolas", 10, "bold"),
                      cursor="hand2", padx=8, pady=4,
                      activebackground="#21262d", activeforeground=col,
                      command=lambda f=bfreq: self._flex_set_freq(f)
                      ).pack(side="left", padx=3, pady=2)
        mode_row = tk.Frame(band_fr, bg=BG); mode_row.pack(fill="x", pady=(4, 0))
        tk.Label(mode_row, text="Modes:", bg=BG, fg="#8b949e",
                 font=("Consolas", 10)).pack(side="left", padx=4)
        for mname in ["CW","LSB","USB","AM","FM","DIGU","RTTY"]:
            tk.Button(mode_row, text=mname, bg="#161b22", fg="#c9d1d9",
                      relief="flat", font=("Consolas", 10), cursor="hand2",
                      padx=10, pady=3, activebackground="#21262d",
                      command=lambda m=mname: self._flex_set_mode(m)
                      ).pack(side="left", padx=2)

    def _flex_toggle_connect(self):
        if not _FLEX_OK:
            messagebox.showerror("Flex-6500",
                "flex_client.py introuvable.\n\nPlacez flex_client.py dans le même dossier.")
            return
        if self._flex_client and self._flex_client.state.connected:
            self._flex_client.disconnect()
            self._flex_client = None
            self._flex_conn_btn.config(text="  Connecter  ", bg="#238636")
            self._flex_status_var.set("⚫  Non connecté")
            try:
                self.lbl_radio.config(text="RADIO OFF", bootstyle="danger-inverse")
            except Exception: pass
            return
        ip   = self._flex_ip_var.get().strip()
        port = int(self._flex_port_var.get().strip())
        self._flex_status_var.set(f"⏳  Connexion à {ip}:{port}...")
        self._flex_conn_btn.config(state="disabled")
        def _do():
            try:
                fc = FlexClient(ip=ip, port=port)
                fc.on_update = lambda st: self._tk_queue.put(lambda s=st: self._flex_on_update(s))
                ok = fc.connect()
                self._flex_client = fc if ok else None
                def _ui():
                    self._flex_conn_btn.config(state="normal")
                    if ok:
                        self._flex_conn_btn.config(text=" Déconnecter ", bg="#8b1a1a")
                        self._flex_status_var.set(f"🟢  Connecté — {ip}")
                    else:
                        self._flex_status_var.set("🔴  Connexion échouée")
                        self._flex_conn_btn.config(text="  Connecter  ", bg="#238636")
                self._tk_queue.put(_ui)
            except Exception as e:
                self._tk_queue.put(lambda err=e: (
                    self._flex_status_var.set(f"🔴  Erreur : {err}"),
                    self._flex_conn_btn.config(state="normal",
                                               text="  Connecter  ", bg="#238636")
                ))
        threading.Thread(target=_do, daemon=True).start()

    def _flex_solar_loop(self):
        time.sleep(5.0)  # attendre que la mainloop soit bien démarrée
        while True:
            try:
                resp = requests.get("https://www.hamqsl.com/solarxml.php", timeout=10)
                root_xml = ET.fromstring(resp.content)
                sol  = root_xml.find("solardata")
                def g(t): el = sol.find(t); return el.text.strip() if el is not None and el.text else "?"
                data = {"sfi":g("solarflux"),"ssn":g("sunspots"),
                        "k":g("kindex"),"a":g("aindex"),
                        "xray":g("xray"),"aurora":g("latdegree")}
                def _upd(d=data):
                    try:
                        if not hasattr(self, "_flex_prop_lbls"): return
                        for key, lbl in self._flex_prop_lbls.items():
                            val = d.get(key, "?")
                            color = "#e6edf3"
                            if key == "k":
                                try: ki=float(val); color="#3fb950" if ki<=2 else "#d29922" if ki<=4 else "#f85149"
                                except: pass
                            elif key == "a":
                                try: ai=float(val); color="#3fb950" if ai<=7 else "#d29922" if ai<=20 else "#f85149"
                                except: pass
                            elif key == "xray":
                                color="#f85149" if val and val[0] in "MX" else "#d29922" if val and val[0]=="C" else "#3fb950"
                            lbl.config(text=val, fg=color)
                        self._flex_prop_upd.config(text=f"Mis à jour {datetime.now().strftime('%H:%M')}")
                    except Exception:
                        pass
                try:
                    self.root.after(0, _upd)
                except Exception:
                    pass
            except Exception as e:
                print(f"[FlexSolar] {e}")
            time.sleep(1800)

    def _flex_on_update(self, state):
        if not hasattr(self, "_flex_freq_var"): return

        BAND_COLS = {
            "160m":"#ff6b6b","80m":"#ff9f43","40m":"#ffd93d","30m":"#6bcb77",
            "20m":"#4d96ff","17m":"#c77dff","15m":"#ff6bff","12m":"#ff9fff",
            "10m":"#ff4757","6m":"#eccc68",
        }

        # ── Fréquence : BLANC en RX, ROUGE en TX ─────────────────────────────
        khz = int(state.frequency * 1000)
        freq_str = f"{khz // 1000}.{khz % 1000:03d}"
        fg_freq = "#ff4444" if state.tx_active else "#e6edf3"
        self._flex_freq_var.set(freq_str)
        self._flex_freq_lbl.config(fg=fg_freq)

        # ── Mise à jour du label "RADIO OFF/ON AIR" en haut de fenêtre ────────
        try:
            if state.tx_active:
                self.lbl_radio.config(text="🔥 ON AIR 🔥", bootstyle="danger-inverse")
            else:
                self.lbl_radio.config(text=f"RX  {freq_str} MHz", bootstyle="success-inverse")
        except Exception: pass

        # ── Bande + indicateur coloré ─────────────────────────────────────────
        band = freq_to_band(str(state.frequency))
        self._flex_band_var.set(band)
        col  = BAND_COLS.get(band, "#555555")
        try:
            self._flex_band_canvas.itemconfig(self._flex_band_rect, fill=col)
            self._flex_band_canvas.itemconfig(self._flex_band_text,
                                               text=f"  ▌ {band}", fill="#11273f")
        except: pass
        try:
            self._flex_band_frame.config(bg=col)
            self._flex_band_lbl.config(bg=col, fg="#11273f" if col!="#555555" else "#fff")
        except: pass

        # ── Mode + filtre ─────────────────────────────────────────────────────
        self._flex_mode_var.set(f"MODE: {state.mode}")
        bw = state.filter_hi - state.filter_lo
        self._flex_filt_var.set(f"Filtre: {state.filter_lo}–{state.filter_hi} Hz  ({bw} Hz)")

        # ── TX/RX dot ─────────────────────────────────────────────────────────
        if state.tx_active:
            self._flex_txrx_canvas.itemconfig(self._flex_txrx_dot, fill="#f85149")
            self._flex_txrx_lbl.config(text="TX  |  TRANSMITTING", fg="#f85149")
        else:
            self._flex_txrx_canvas.itemconfig(self._flex_txrx_dot, fill="#3fb950")
            self._flex_txrx_lbl.config(text="RX  |  READY", fg="#3fb950")
        self._flex_ilock_var.set(f"Interlock: {state.interlock_state}")

        # ── Forward Power — VU-mètre 3 segments vert/jaune/rouge ─────────────
        pwr_pct = max(0.0, min(1.0, state.power_fwd / 100.0))
        try:
            w = max(50, self._flex_pwr_canvas.winfo_reqwidth())
            px       = int(w * pwr_pct)
            px_green  = int(w * 0.55)   # vert  : 0 → 55W
            px_yellow = int(w * 0.82)   # jaune : 55 → 82W
            # Segment vert
            self._flex_pwr_canvas.coords(self._flex_pwr_seg_green,
                0, 0, min(px, px_green), 28)
            # Segment jaune
            if px > px_green:
                self._flex_pwr_canvas.coords(self._flex_pwr_seg_yellow,
                    px_green, 0, min(px, px_yellow), 28)
            else:
                self._flex_pwr_canvas.coords(self._flex_pwr_seg_yellow, 0, 0, 0, 28)
            # Segment rouge
            if px > px_yellow:
                self._flex_pwr_canvas.coords(self._flex_pwr_seg_red,
                    px_yellow, 0, px, 28)
            else:
                self._flex_pwr_canvas.coords(self._flex_pwr_seg_red, 0, 0, 0, 28)
        except: pass
        # Valeur en watts — couleur selon niveau
        if state.power_fwd <= 0:
            pwr_fg = "#8b949e"
        elif pwr_pct < 0.55:
            pwr_fg = "#3fb950"
        elif pwr_pct < 0.82:
            pwr_fg = "#ffd93d"
        else:
            pwr_fg = "#f85149"
        self._flex_pwr_val.config(text=f"{state.power_fwd:.0f} W", fg=pwr_fg)

        # ── SWR ───────────────────────────────────────────────────────────────
        swr_pct = max(0.0, min(1.0, (state.swr - 1.0) / 2.0))
        try:
            w = max(50, self._flex_swr_canvas.winfo_reqwidth())
            px = int(w * swr_pct)
            swr_col = "#3fb950" if state.swr < 1.5 else "#d29922" if state.swr < 2.0 else "#f85149"
            self._flex_swr_canvas.coords(self._flex_swr_bar, 0, 0, px, 16)
            self._flex_swr_canvas.itemconfig(self._flex_swr_bar, fill=swr_col)
        except: pass
        swr_col2 = "#3fb950" if state.swr < 1.5 else "#d29922" if state.swr < 2.0 else "#f85149"
        self._flex_swr_val.config(text=f"{state.swr:.2f}:1", fg=swr_col2)

        # ── ALC ───────────────────────────────────────────────────────────────
        alc_pct = max(0.0, min(1.0, (state.alc + 20) / 20.0))
        try:
            w = max(50, self._flex_alc_canvas.winfo_reqwidth())
            self._flex_alc_canvas.coords(self._flex_alc_bar, 0, 0, int(w * alc_pct), 16)
        except: pass
        self._flex_alc_val.config(text=f"{state.alc:.1f} dB")

        # ── Infos Radio — toujours mettre à jour ──────────────────────────────
        if hasattr(self, "_flex_info_vars"):
            if state.rx_ant and state.rx_ant != "?":
                self._flex_info_vars["rx_ant"].set(state.rx_ant)
            if state.tx_ant and state.tx_ant != "?":
                self._flex_info_vars["tx_ant"].set(state.tx_ant)
            self._flex_info_vars["slices"].set(str(state.slices) if state.slices else "—")
            self._flex_info_vars["panadapts"].set(str(state.panadapters) if state.panadapters else "—")
            if state.filter_lo or state.filter_hi:
                self._flex_info_vars["filter"].set(
                    f"{state.filter_lo} / {state.filter_hi} Hz")

    def _flex_update_bar(self, key, value, label_text=""):
        pass  # Toutes les barres sont gérées directement dans _flex_on_update

    def _flex_set_freq(self, freq_mhz):
        if self._flex_client and self._flex_client.state.connected:
            self._flex_client.set_frequency(freq_mhz)
        else:
            try: self.cat.set_freq(freq_mhz * 1e6)
            except: pass

    def _flex_set_mode(self, mode):
        if self._flex_client and self._flex_client.state.connected:
            self._flex_client.set_mode(mode)


def show_splash(root):
    """Affiche un splash screen professionnel pendant le chargement."""
    splash = tk.Toplevel()
    splash.overrideredirect(True)
    splash.configure(bg="#11273f")

    # Centrer le splash
    w, h = 520, 320
    sw = splash.winfo_screenwidth(); sh = splash.winfo_screenheight()
    splash.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # Bordure décorative
    canvas = tk.Canvas(splash, width=w, height=h, bg="#11273f", highlightthickness=2,
                        highlightbackground="#f39c12")
    canvas.pack(fill="both", expand=True)

    # Titre
    canvas.create_text(w//2, 70, text="STATION MASTER", font=("Impact", 42),
                        fill="#f39c12", anchor="center")
    canvas.create_text(w//2, 115, text=f"ON5AM  •  {MY_GRID}",
                        font=("Consolas", 16), fill="#3498db", anchor="center")
    canvas.create_line(40, 135, w-40, 135, fill="#f39c12", width=2)

    # Sous-titre
    canvas.create_text(w//2, 160, text="Ham Radio Station Management",
                        font=("Arial", 11), fill="#aaaaaa", anchor="center")
    canvas.create_text(w//2, 185, text="V21.0  —  Python Edition",
                        font=("Consolas", 10), fill="#5588aa", anchor="center")

    # Barre de progression
    bar_bg = canvas.create_rectangle(60, 230, w-60, 255, fill="#1a3655", outline="#3498db")
    bar_fill = canvas.create_rectangle(60, 230, 60, 255, fill="#3498db", outline="")
    status_lbl = canvas.create_text(w//2, 275, text="Initialisation...",
                                     font=("Arial", 9), fill="#888888", anchor="center")

    steps = [
        (20,  "Chargement de la configuration..."),
        (40,  "Connexion à la base de données..."),
        (60,  "Initialisation de l'interface..."),
        (80,  "Connexion DX Cluster & CAT..."),
        (100, "Démarrage..."),
    ]

    def animate(i=0):
        if i >= len(steps): return
        try:
            # Vérifier que le splash n'a pas déjà été détruit
            if not splash.winfo_exists(): return
            pct, msg = steps[i]
            x_end = 60 + (w-120) * pct // 100
            canvas.coords(bar_fill, 60, 230, x_end, 255)
            canvas.itemconfig(status_lbl, text=msg)
            splash.update()
            splash.after(280, lambda: animate(i+1))
        except Exception:
            pass  # Splash déjà détruit, on ignore

    animate()
    return splash


def ask_backup_dir_first_time():
    """Demande à l'utilisateur de choisir un dossier de backup au premier lancement."""
    global BACKUP_DIR, CONF
    if BACKUP_DIR:
        return  # Déjà configuré
    
    # Fenêtre de bienvenue / choix backup
    dlg = tk.Tk()
    dlg.withdraw()
    
    result = messagebox.askyesno(
        "🗂️ Configuration du dossier de backup",
        f"Bienvenue dans Station Master V21.0 !\n\n"
        f"Aucun dossier de backup n'est encore configuré.\n\n"
        f"Voulez-vous choisir maintenant le dossier où\n"
        f"vos sauvegardes seront enregistrées à la fermeture ?\n\n"
        f"(Vous pourrez le modifier plus tard dans ⚙️ Paramètres)",
        icon="question"
    )
    
    if result:
        chosen = filedialog.askdirectory(
            title="Choisir le dossier de backup automatique",
            mustexist=False
        )
        if chosen:
            BACKUP_DIR = chosen
            # Sauvegarder dans config.ini
            cfg = configparser.ConfigParser()
            cfg.read(CONFIG_FILE)
            if not cfg.has_section('BACKUP'): cfg.add_section('BACKUP')
            cfg.set('BACKUP', 'Dir', chosen)
            with open(CONFIG_FILE, 'w') as f: cfg.write(f)
            messagebox.showinfo("✅ Backup configuré",
                f"Dossier de backup :\n{chosen}\n\n"
                "Une sauvegarde sera créée automatiquement à chaque fermeture.")
    else:
        # Dossier par défaut local
        default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Backups")
        BACKUP_DIR = default
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_FILE)
        if not cfg.has_section('BACKUP'): cfg.add_section('BACKUP')
        cfg.set('BACKUP', 'Dir', default)
        with open(CONFIG_FILE, 'w') as f: cfg.write(f)
    
    dlg.destroy()


if __name__ == "__main__":
    if load_config_safe():
        try:
            ask_backup_dir_first_time()

            # "darkly" est nativement sombre — beaucoup plus facile à surcharger
            # vers #11273f que "superhero" qui ré-applique ses gris au démarrage
            app = ttk.Window(themename="darkly")
            app.withdraw()

            # Pré-forcer avant l'affichage
            BG = "#11273f"
            app.configure(bg=BG)
            _s = ttk.Style()
            _s.configure(".", background=BG, foreground="white",
                         fieldbackground=BG, selectbackground="#1a5276")
            _s.configure("Treeview", background=BG, fieldbackground=BG, foreground="white")
            _s.configure("Treeview.Heading", background="#0d1e30", foreground="#f39c12")

            # Splash screen
            splash = show_splash(app)
            app.after(1700, splash.destroy)
            app.after(1800, app.deiconify)

            StationMasterApp(app)
            app.mainloop()
        except Exception as e:
            print("CRASH:", e); traceback.print_exc(); input()