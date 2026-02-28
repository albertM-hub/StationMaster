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

# --- GLOBALS ---
MY_GRID = "JO20SP"
MY_CALL = "ON5AM"
CAT_PORT = "COM4"
CAT_BAUD = 9600
CONF = None
BACKUP_DIR = ""  # Dossier de backup choisi par l'utilisateur

# ==========================================
# --- CONFIGURATION ---
# ==========================================
CONFIG_FILE = "config.ini"

def load_config_safe():
    global CONF, MY_GRID, MY_CALL, CAT_PORT, CAT_BAUD, BACKUP_DIR
    config = configparser.ConfigParser()
    DEFAULTS = {
        'USER': {'Callsign': 'ON5AM', 'Grid': 'JO20SP'},
        'CAT': {'Port': 'COM4', 'Baud': '9600'}, 
        'API': {'QRZ_User': 'ON5AM', 'QRZ_Pass': '', 'QRZ_Key': '', 'EQSL_User': 'ON5AM', 'EQSL_Pass': '', 'Club_Email': '', 'Club_Pass': '', 'Club_Call': 'ON5AM', 'Club_Key': ''},
        'CLUSTER': {'Host': 'on0dxk.dyndns.org', 'Port': '8000', 'Call': 'ON5AM'},
        'DXCC': {'Alert_Bands': '20m,15m,10m', 'Alert_Countries': ''},
        'LOTW': {'Callsign': 'ON5AM', 'Tqsl_Path': 'C:\\Program Files (x86)\\TQSL\\tqsl.exe'},
        'BACKUP': {'Dir': ''},
        'UDP': {'Source': 'wsjtx', 'WsjtxPort': '2237', 'MulticastIP': '224.0.0.1', 'GridtrackerPort': '2333'},
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
# --- DICTIONNAIRE PAYS / DXCC ---
# ==========================================
PREFIX_MAP = {
    'ON': 'Belgium', 'F': 'France', 'K': 'USA', 'W': 'USA', 'N': 'USA', 'A': 'USA',
    'G': 'England', 'M': 'England', '2E': 'England', 'I': 'Italy', 'DL': 'Germany', 'EA': 'Spain',
    'JA': 'Japan', 'VK': 'Australia', 'ZL': 'New Zealand', 'VE': 'Canada', 'PY': 'Brazil',
    'UA': 'Russia', 'R': 'Russia', 'SP': 'Poland', 'OK': 'Czech Rep', 'PA': 'Netherlands',
    'LX': 'Luxembourg', 'HB': 'Switzerland', 'CT': 'Portugal', 'OE': 'Austria', 'OH': 'Finland',
    'SM': 'Sweden', 'LA': 'Norway', 'OZ': 'Denmark', 'ES': 'Estonia', 'YL': 'Latvia', 'LY': 'Lithuania',
    'YO': 'Romania', 'LZ': 'Bulgaria', 'SV': 'Greece', '9A': 'Croatia', 'S5': 'Slovenia', 'E7': 'Bosnia',
    'YU': 'Serbia', 'TR': 'Turkey', '4X': 'Israel', 'CN': 'Morocco', 'YB': 'Indonesia', 'BY': 'China',
    'BV': 'Taiwan', 'VR': 'Hong Kong', 'HL': 'South Korea', 'HS': 'Thailand', 'DU': 'Philippines',
    '9V': 'Singapore', '9M': 'Malaysia', 'VU': 'India', '4S': 'Sri Lanka', '7X': 'Algeria',
    'SU': 'Egypt', '5Z': 'Kenya', 'CE': 'Chile', 'CX': 'Uruguay', 'OA': 'Peru', 'HK': 'Colombia',
    'YV': 'Venezuela', 'HI': 'Dom. Rep', 'KP4': 'Puerto Rico', 'XE': 'Mexico', 'CO': 'Cuba',
    'TF': 'Iceland', 'EI': 'Ireland', 'GI': 'N. Ireland', 'GW': 'Wales', 'GM': 'Scotland',
    'GD': 'Isle of Man', 'GJ': 'Jersey', 'GU': 'Guernsey', 'OY': 'Faroe Is.', 'TF': 'Iceland',
    'Z3': 'N. Macedonia', 'HA': 'Hungary', 'OM': 'Slovakia', 'YU': 'Serbia', 'OA': 'Peru',
    'FY': 'French Guiana', 'FM': 'Martinique', 'FG': 'Guadeloupe', 'TO': 'Saint-Martin',
    'ZB': 'Gibraltar', 'IS0': 'Sardinia', 'IT9': 'Sicily', 'IG9': 'Pantelleria',
    'VK9': 'Christmas Is', 'VK9X': 'Cocos Keeling', 'VK0M': 'Macquarie Is',
    'ZL7': 'Chatham Is', 'ZL8': 'Kermadec Is', 'ZL9': 'Campbell Is',
    'KH6': 'Hawaii', 'KH8': 'American Samoa', 'KH9': 'Wake Is', 'KH0': 'Mariana Is',
    'KP2': 'US Virgin Is', 'KP4': 'Puerto Rico', 'KG4': 'Guantanamo',
    'JD1': 'Ogasawara', 'JD1': 'Minami Torishima',
    'HS': 'Thailand', 'XW': 'Laos', 'XV': 'Vietnam', 'XU': 'Cambodia', 'XZ': 'Myanmar',
    'A6': 'UAE', 'A7': 'Qatar', 'A9': 'Bahrain', '9K': 'Kuwait', 'OD': 'Lebanon',
    'YK': 'Syria', 'EP': 'Iran', 'EK': 'Armenia', '4J': 'Azerbaijan', '4K': 'Azerbaijan',
    'UK': 'Uzbekistan', 'EX': 'Kyrgyzstan', 'EY': 'Tajikistan', 'EZ': 'Turkmenistan',
    'UN': 'Kazakhstan', 'TA': 'Turkey', '5B': 'Cyprus', 'P2': 'Papua New Guinea',
    'T8': 'Palau', 'V6': 'Micronesia', 'KH2': 'Guam', 'NH0': 'N. Mariana Is',
    'ZK1': 'S. Cook Is', 'ZK2': 'Niue', 'ZK3': 'Tokelau', 'FO': 'French Polynesia',
    'FW': 'Wallis & Futuna', 'FK': 'New Caledonia', 'KH5': 'Palmyra Is',
    'H4': 'Solomon Is', 'YJ': 'Vanuatu', 'A3': 'Tonga', 'T2': 'Tuvalu',
    'T3': 'W. Kiribati', 'T31': 'C. Kiribati', 'T32': 'E. Kiribati',
    'VP9': 'Bermuda', 'VP2E': 'Anguilla', 'VP2M': 'Montserrat', 'VP2V': 'BVI',
    'VP5': 'Turks & Caicos', 'J3': 'Grenada', 'J6': 'St Lucia', 'J7': 'Dominica',
    'J8': 'St Vincent', 'V2': 'Antigua', 'V4': 'St Kitts', 'V7': 'Marshall Is',
    '8P': 'Barbados', '9Y': 'Trinidad', 'ZF': 'Cayman Is', 'HR': 'Honduras',
    'TG': 'Guatemala', 'TI': 'Costa Rica', 'HP': 'Panama', 'YS': 'El Salvador',
    'HH': 'Haiti', '6Y': 'Jamaica', 'VP': 'Falkland Is', 'LU': 'Argentina',
    'ZP': 'Paraguay', 'ZS': 'South Africa', '9J': 'Zambia', 'ZE': 'Zimbabwe',
    'C9': 'Mozambique', '7Q': 'Malawi', 'XT': 'Burkina Faso', 'TY': 'Benin',
    '5N': 'Nigeria', '5U': 'Niger', 'TJ': 'Cameroon', 'TL': 'C. African Rep',
    'TT': 'Chad', '6W': 'Senegal', '9G': 'Ghana', 'TR': 'Gabon', '5H': 'Tanzania',
    '7O': 'Yemen', 'A4': 'Oman', '8Z4': 'Saudi Arabia', 'HZ': 'Saudi Arabia',
    '9N': 'Nepal', 'S2': 'Bangladesh', 'AP': 'Pakistan', '4Z': 'Israel'
}

def get_country_name(callsign):
    if not callsign: return ""
    c = callsign.upper()
    for i in range(4, 0, -1):
        if len(c) >= i:
            p = c[:i]
            if p in PREFIX_MAP: return PREFIX_MAP[p]
            if i > 1 and p[-1].isdigit() and p[:-1] in PREFIX_MAP: return PREFIX_MAP[p[:-1]]
    return ""

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
        if 1.8 <= f <= 2.0: return "160m"
        if 3.5 <= f <= 4.0: return "80m"
        if 7.0 <= f <= 7.3: return "40m"
        if 10.1 <= f <= 10.15: return "30m"
        if 14.0 <= f <= 14.35: return "20m"
        if 18.068 <= f <= 18.168: return "17m"
        if 21.0 <= f <= 21.45: return "15m"
        if 24.89 <= f <= 24.99: return "12m"
        if 28.0 <= f <= 29.7: return "10m"
        if 50.0 <= f <= 54.0: return "6m"
        return "20m"
    except: return "20m"

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
    def __init__(self, host, port, callsign, callback_spot):
        super().__init__(); self.host = host; self.port = int(port); self.callsign = callsign; self.callback = callback_spot; self.running = True
    def run(self):
        while self.running:
            try:
                tn = socket.socket(socket.AF_INET, socket.SOCK_STREAM); tn.settimeout(10); tn.connect((self.host, self.port))
                time.sleep(2)
                tn.sendall(f"{self.callsign}\r\n".encode())
                while self.running:
                    data = tn.recv(4096).decode('utf-8', errors='ignore')
                    if not data: break
                    for line in data.split('\n'):
                        if "DX de" in line:
                            try:
                                parts = line.split()
                                if len(parts) > 4:
                                    spotter = parts[2].replace(':', ''); freq = parts[3]; dx_call = parts[4]; time_z = parts[-1]
                                    comment = " ".join(parts[5:-1]) if len(parts) > 5 else ""
                                    self.callback(freq, dx_call, comment, spotter, time_z)
                            except: pass
            except: time.sleep(10)

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
    def __init__(self, u, p): pass
    def upload_qso(self, d): return False

class ClubLogManager:
    def __init__(self, e, p, c, k=""): pass
    def upload_qso(self, d): return False

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
        """Saute un QDateTime Qt : u64 (julian ms) + u8 (timespec) [+ u32 offset si timespec==2]."""
        self.cursor += 8   # julian day ms (u64)
        ts = self.read_u8()  # timespec : 0=local,1=UTC,2=offset,3=timezone
        if ts == 2:
            self.cursor += 4  # offset en secondes
        return 0

    def read_bool(self):
        v = self.d[self.cursor]; self.cursor += 1; return bool(v)

# ==========================================
# --- APP PRINCIPALE ---
# ==========================================
class HamLogbookApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{MY_CALL} Station Master V21.0")
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
        self._all_spots = []  # buffer spots cluster
        
        self.status_var = ttk.StringVar(value=f"Station Prête - {MY_GRID}")
        self.solar_var = ttk.StringVar(value="SFI: --")
        self.utc_time_var = ttk.StringVar(value="00:00:00 UTC")

        # Filtres cluster
        self._cluster_alert_bands = set()
        self._cluster_alert_countries = set()
        self._load_cluster_filters()

        self.qrz = QRZManager("","",""); self.eqsl = EQSLManager("",""); self.club = ClubLogManager("","","")
        if CONF:
            self.qrz = QRZManager(CONF['API']['QRZ_User'], CONF['API']['QRZ_Pass'], CONF['API']['QRZ_Key'])
            self.eqsl = EQSLManager(CONF['API']['EQSL_User'], CONF['API']['EQSL_Pass'])
            self.club = ClubLogManager(CONF['API']['Club_Email'], CONF['API']['Club_Pass'], CONF['API']['Club_Call'], CONF['API']['Club_Key'])
        
        self.conn = sqlite3.connect('mon_logbook.db', check_same_thread=False)
        self.create_table()

        # Charger la config UDP
        self._udp_source      = "wsjtx"       # wsjtx | gridtracker | les_deux
        self._udp_wsjtx_port  = 2237
        self._udp_mcast_ip    = "224.0.0.1"
        self._udp_gt_port     = 2333
        self._load_udp_config()

        self.setup_ui()
        try: self.load_data()
        except: pass
        self.update_clock()

        self._start_udp_threads()
        
        self.cat = RadioCAT(CAT_PORT, CAT_BAUD, self.update_radio_info)
        self.cat.daemon = True; self.cat.start()
        
        if CONF:
            self.cluster = ClusterThread(CONF['CLUSTER']['Host'], CONF['CLUSTER']['Port'], CONF['CLUSTER']['Call'], self.on_cluster_spot)
            self.cluster.daemon = True; self.cluster.start()
        
        sol_t = SolarThread(lambda d: self.solar_var.set(d)); sol_t.daemon = True; sol_t.start()

        # PSK Reporter thread
        self._psk_spots = []
        self._psk_thread = PSKReporterThread(MY_CALL, self._on_psk_spots)
        self._psk_thread.start()

        # Variables dashboard (mise à jour périodique)
        self.root.after(2000, self._refresh_dashboard)

    def _load_cluster_filters(self):
        if CONF:
            bands_str = CONF.get('DXCC', 'Alert_Bands', fallback='')
            countries_str = CONF.get('DXCC', 'Alert_Countries', fallback='')
            self._cluster_alert_bands = set(b.strip().lower() for b in bands_str.split(',') if b.strip())
            self._cluster_alert_countries = set(c.strip().lower() for c in countries_str.split(',') if c.strip())

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
            text=f"RX: {labels.get(src, src)}", foreground="#3498db"))

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

    def update_clock(self):
        self.utc_time_var.set(datetime.now(timezone.utc).strftime('%H:%M:%S UTC'))
        self.root.after(1000, self.update_clock)

    # ==========================================
    # --- SETUP UI ---
    # ==========================================
    def setup_ui(self):
        top = ttk.Frame(self.root, padding=10, bootstyle="dark"); top.pack(fill="x")
        f_left = ttk.Frame(top, bootstyle="dark"); f_left.pack(side="left")
        ttk.Label(f_left, text=f"{MY_CALL} STATION MASTER", font=("Impact", 24), bootstyle="inverse-dark").pack(side="left")
        
        f_radio = ttk.Frame(top, bootstyle="dark", padding=(20,0)); f_radio.pack(side="left", padx=20)
        self.lbl_radio = ttk.Label(f_radio, text="RADIO OFF", font=("Consolas", 16, "bold"), bootstyle="danger-inverse", padding=5)
        self.lbl_radio.pack(side="top", pady=2)
        self.pb_smeter = ttk.Progressbar(f_radio, value=0, maximum=30, bootstyle="success-striped", length=200)
        self.pb_smeter.pack(side="bottom", pady=2)
        
        f_info = ttk.Frame(top, bootstyle="dark", padding=20); f_info.pack(side="left")
        ttk.Label(f_info, textvariable=self.utc_time_var, font=("Consolas", 18, "bold"), foreground="white").pack(side="top")
        dn = get_day_night_status()
        ttk.Label(f_info, text=f"{dn} | ", font=("Arial", 10), foreground="#3498db").pack(side="left")
        ttk.Label(f_info, textvariable=self.solar_var, font=("Arial", 10), foreground="#f39c12").pack(side="left")
        
        self.lbl_data = ttk.Label(top, text="RX DATA", font=("Arial", 8), foreground="#555")
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
        self.e_call = ttk.Entry(f1, font=("Arial", 12, "bold"), width=10); self.e_call.pack(side="left", padx=5)
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

        # --- Onglet Journal ---
        t_log = tk.Frame(self.nb, bg=BG); self.nb.add(t_log, text="📖 Journal")
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
        self.menu.add_command(label="❌ Supprimer la sélection", command=self.del_qso)
        self.menu.add_separator()
        self.menu.add_command(label="🗑️ Vider tout le logbook…", command=self.clear_logbook)
        self.tree.bind("<Button-3>", lambda e: self.menu.post(e.x_root, e.y_root))

        # --- Onglet Carte ---
        t_map = tk.Frame(self.nb, bg=BG); self.nb.add(t_map, text="🌍 Carte Live")
        map_ctrl = tk.Frame(t_map, bg=BG); map_ctrl.pack(fill="x", padx=5, pady=3)
        self.greyline_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(map_ctrl, text="🌓 Greyline animée", variable=self.greyline_var,
                        command=self._toggle_greyline, bootstyle="info-round-toggle").pack(side="left", padx=5)
        self.greyline_info_var = tk.StringVar(value="")
        ttk.Label(map_ctrl, textvariable=self.greyline_info_var, foreground="#3498db", font=("Consolas",9)).pack(side="left", padx=10)
        self.map_widget = TkinterMapView(t_map, corner_radius=10); self.map_widget.pack(fill="both", expand=True, padx=5, pady=5)
        self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        home_pos = grid_to_latlon(MY_GRID)
        if home_pos:
            self.map_widget.set_position(home_pos[0], home_pos[1])
            self.map_widget.set_zoom(5)
            self.home_marker = self.map_widget.set_marker(home_pos[0], home_pos[1], text=f"🏠 {MY_CALL}")
        self._greyline_markers = []
        self._update_greyline_map()  # Premier tracé immédiat

        # --- Onglet DX Cluster avec filtres ---
        t_clus = tk.Frame(self.nb, bg=BG); self.nb.add(t_clus, text="📡 DX Cluster")
        self._build_cluster_tab(t_clus)

        # --- Onglet Statistiques avancées ---
        t_stat = tk.Frame(self.nb, bg=BG); self.nb.add(t_stat, text="📈 Statistiques")
        self._build_stats_tab(t_stat)

        # --- Onglet DXCC ---
        t_dxcc = tk.Frame(self.nb, bg=BG); self.nb.add(t_dxcc, text="🏆 DXCC")
        self._build_dxcc_tab(t_dxcc)

        # --- Onglet Graphiques ---
        t_graphs = tk.Frame(self.nb, bg=BG); self.nb.add(t_graphs, text="📊 Graphiques")
        self._build_graphs_tab(t_graphs)

        # --- Onglet Propagation ---
        t_prop = tk.Frame(self.nb, bg=BG); self.nb.add(t_prop, text="🌐 Propagation")
        self._build_propagation_tab(t_prop)

        # --- Onglet DX World ---
        t_dxworld = tk.Frame(self.nb, bg=BG); self.nb.add(t_dxworld, text="🌍 DX World")
        self._build_dxworld_tab(t_dxworld)

        # --- Onglet Awards ---
        t_awards = tk.Frame(self.nb, bg=BG); self.nb.add(t_awards, text="🏅 Awards")
        self._build_awards_tab(t_awards)

        # --- Onglet QSL Reminder ---
        t_qslrem = tk.Frame(self.nb, bg=BG); self.nb.add(t_qslrem, text="📬 QSL Reminder")
        self._build_qsl_reminder_tab(t_qslrem)

        # --- Onglet Mémoires fréquences ---
        t_mem = tk.Frame(self.nb, bg=BG); self.nb.add(t_mem, text="📻 Mémoires")
        self._build_memories_tab(t_mem)

        # --- Onglet Heatmap ---
        t_heat = tk.Frame(self.nb, bg=BG); self.nb.add(t_heat, text="🗺️ Heatmap")
        self._build_heatmap_tab(t_heat)

        # --- Onglet PSK Reporter ---
        t_psk = tk.Frame(self.nb, bg=BG); self.nb.add(t_psk, text="📻 PSK Reporter")
        self._build_psk_tab(t_psk)

        # --- Onglet QSL Card ---
        t_qslcard = tk.Frame(self.nb, bg=BG); self.nb.add(t_qslcard, text="🖨️ QSL Card")
        self._build_qslcard_tab(t_qslcard)

        # --- Onglet Wiki ---
        t_wiki = tk.Frame(self.nb, bg=BG); self.nb.add(t_wiki, text="📖 Wiki")
        self._build_wiki_tab(t_wiki)

        # Barre de statut (TOUJOURS en dernier pour être en bas)
        self.lbl_count = ttk.Label(self.root, text="QSO: 0", font=("Arial", 10, "bold"), bootstyle="primary")
        self.lbl_count.pack(side="bottom", anchor="e", padx=10)
        self.lbl_status = ttk.Label(self.root, textvariable=self.status_var, font=("Helvetica", 12, "bold"), foreground="#7698d0", padding=5)
        self.lbl_status.pack(side="bottom", fill="x")

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
            calls = c.execute("SELECT callsign FROM qsos").fetchall()
            countries = set()
            for (call,) in calls:
                cn = get_country_name(call)
                if cn: countries.add(cn)
            confirmed = c.execute("SELECT COUNT(*) FROM dxcc_confirmed WHERE confirmed=1").fetchone()[0]
            self.dash_dxcc_var.set(str(len(countries)))
            self.dash_dxcc_conf_var.set(f"{confirmed} confirmés")

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
    # --- ONGLET CLUSTER AVEC FILTRES ---
    # ==========================================
    def _build_cluster_tab(self, parent):
        # Barre de filtres
        flt_fr = tk.Frame(parent, bg="#11273f"); flt_fr.pack(fill="x")
        ttk.Label(flt_fr, text="Filtres Cluster :").pack(side="left", padx=5)
        
        ttk.Label(flt_fr, text="Bande:").pack(side="left")
        self.cluster_band_var = tk.StringVar(value="All")
        cb_band = ttk.Combobox(flt_fr, textvariable=self.cluster_band_var,
                                values=["All","160m","80m","40m","20m","17m","15m","12m","10m","6m"], width=6)
        cb_band.pack(side="left", padx=3)
        cb_band.bind("<<ComboboxSelected>>", lambda e: self._apply_cluster_filter())

        ttk.Label(flt_fr, text="Pays:").pack(side="left", padx=(10,2))
        self.cluster_country_var = tk.StringVar()
        self.cluster_country_entry = ttk.Entry(flt_fr, textvariable=self.cluster_country_var, width=18)
        self.cluster_country_entry.pack(side="left", padx=3)
        self.cluster_country_entry.bind("<KeyRelease>", lambda e: self._apply_cluster_filter())

        ttk.Label(flt_fr, text="Appel:").pack(side="left", padx=(10,2))
        self.cluster_call_var = tk.StringVar()
        cluster_call_entry = ttk.Entry(flt_fr, textvariable=self.cluster_call_var, width=10)
        cluster_call_entry.pack(side="left", padx=3)
        cluster_call_entry.bind("<KeyRelease>", lambda e: self._apply_cluster_filter())

        self.cluster_alert_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(flt_fr, text="🔔 Alerte sonore", variable=self.cluster_alert_var).pack(side="left", padx=10)

        ttk.Button(flt_fr, text="Effacer filtres", command=self._clear_cluster_filters, bootstyle="secondary-outline", width=14).pack(side="left", padx=5)
        ttk.Button(flt_fr, text="⚙️ Config alertes", command=self.open_cluster_alert_config, bootstyle="warning-outline", width=16).pack(side="left", padx=5)

        # Compteur
        self.cluster_count_var = tk.StringVar(value="0 spots")
        ttk.Label(flt_fr, textvariable=self.cluster_count_var, foreground="#f39c12").pack(side="right", padx=10)

        # Treeview cluster
        style = ttk.Style()
        style.configure("Cluster.Treeview",
            rowheight=25, font=('Arial', 10),
            background="#11273f", fieldbackground="#11273f",
            foreground="white")
        style.configure("Cluster.Treeview.Heading",
            background="#1a3a5c", foreground="#f39c12",
            font=("Arial", 9, "bold"), relief="flat")
        style.map("Cluster.Treeview",
            background=[("selected", "#1a5276")],
            foreground=[("selected", "white")])
        col_cl = ("UTC","Freq","Band","Mode","Ant","Pays","DX Call","Spotter","Comment")
        self.tree_cl = ttk.Treeview(parent, columns=col_cl, show='headings', style="Cluster.Treeview")
        self.tree_cl.heading("UTC", text="UTC"); self.tree_cl.column("UTC", width=55, anchor="center")
        self.tree_cl.heading("Freq", text="Freq"); self.tree_cl.column("Freq", width=75, anchor="center")
        self.tree_cl.heading("Band", text="Bande"); self.tree_cl.column("Band", width=55, anchor="center")
        self.tree_cl.heading("Mode", text="Mode"); self.tree_cl.column("Mode", width=55, anchor="center")
        self.tree_cl.heading("Ant", text="Ant°"); self.tree_cl.column("Ant", width=50, anchor="center")
        self.tree_cl.heading("Pays", text="Pays"); self.tree_cl.column("Pays", width=130, anchor="w")
        self.tree_cl.heading("DX Call", text="DX Call"); self.tree_cl.column("DX Call", width=100, anchor="w")
        self.tree_cl.heading("Spotter", text="Spotter"); self.tree_cl.column("Spotter", width=100, anchor="w")
        self.tree_cl.heading("Comment", text="Info"); self.tree_cl.column("Comment", width=300, anchor="w")
        self.tree_cl.pack(fill="both", expand=True)
        self.tree_cl.bind("<Double-1>", self.on_cluster_click)
        self.tree_cl.tag_configure('odd', background='#11273f')
        self.tree_cl.tag_configure('even', background='#34495e')
        self.tree_cl.tag_configure('alert', background='#7d2020', foreground='#ffdd57')
        self.tree_cl.tag_configure('new_dxcc', background='#1a5276', foreground='#58d68d')

        # (buffer _all_spots initialisé dans __init__)

    def _apply_cluster_filter(self):
        band_f = self.cluster_band_var.get().lower()
        country_f = self.cluster_country_var.get().strip().lower()
        call_f = self.cluster_call_var.get().strip().upper()

        for item in self.tree_cl.get_children():
            self.tree_cl.delete(item)

        count = 0
        for spot in self._all_spots:
            freq, call, comment, spotter, time_z, band, mode, country = spot
            if band_f != "all" and band.lower() != band_f: continue
            if country_f and country_f not in country.lower(): continue
            if call_f and call_f not in call.upper(): continue
            
            tag = self._get_spot_tag(band, country, call)
            i = count % 2
            final_tag = tag if tag else ('even' if i == 0 else 'odd')
            self.tree_cl.insert("", "end", values=(time_z, freq, band, mode, "", country, call, spotter, comment), tags=(final_tag,))
            count += 1

        self.cluster_count_var.set(f"{count} spot{'s' if count != 1 else ''}")

    def _get_spot_tag(self, band, country, call):
        """Retourne le tag visuel pour un spot selon les alertes configurées."""
        # Vérifier si c'est un DXCC non encore travaillé
        c = self.conn.cursor()
        worked = c.execute("SELECT COUNT(*) FROM qsos WHERE callsign LIKE ?", (call[:4]+"%",)).fetchone()[0]
        if country and worked == 0:
            return 'new_dxcc'
        
        # Vérifier alertes bandes/pays configurées
        if (self._cluster_alert_bands and band.lower() in self._cluster_alert_bands) or \
           (self._cluster_alert_countries and country.lower() in self._cluster_alert_countries):
            return 'alert'
        return None

    def _clear_cluster_filters(self):
        self.cluster_band_var.set("All")
        self.cluster_country_var.set("")
        self.cluster_call_var.set("")
        self._apply_cluster_filter()

    def open_cluster_alert_config(self):
        """Fenêtre de configuration des alertes cluster."""
        win = tk.Toplevel(self.root)
        win.title("🔔 Configuration des alertes DX Cluster")
        win.geometry("460x320")
        win.grab_set()

        frm = ttk.Frame(win, padding=20); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Bandes à surveiller (séparées par virgules) :", font=("Arial",10)).pack(anchor="w", pady=(0,3))
        ttk.Label(frm, text="Ex: 20m,15m,10m", foreground="gray", font=("Arial",9)).pack(anchor="w")
        e_bands = ttk.Entry(frm, width=40); e_bands.pack(fill="x", pady=(0,12))
        if CONF: e_bands.insert(0, CONF.get('DXCC','Alert_Bands',''))

        ttk.Label(frm, text="Pays à surveiller (séparés par virgules) :", font=("Arial",10)).pack(anchor="w", pady=(0,3))
        ttk.Label(frm, text="Ex: Japan,USA,Australia", foreground="gray", font=("Arial",9)).pack(anchor="w")
        e_countries = ttk.Entry(frm, width=40); e_countries.pack(fill="x", pady=(0,12))
        if CONF: e_countries.insert(0, CONF.get('DXCC','Alert_Countries',''))

        ttk.Label(frm, text="Légende : 🟦 Nouveau DXCC (jamais travaillé) | 🟥 Bande/Pays alerte", foreground="#aaa", font=("Arial",9)).pack(anchor="w", pady=5)

        def save():
            global CONF
            cfg = configparser.ConfigParser(); cfg.read(CONFIG_FILE)
            if not cfg.has_section('DXCC'): cfg.add_section('DXCC')
            cfg.set('DXCC','Alert_Bands', e_bands.get().strip())
            cfg.set('DXCC','Alert_Countries', e_countries.get().strip())
            with open(CONFIG_FILE,'w') as f: cfg.write(f)
            load_config_safe()
            self._load_cluster_filters()
            self.status_var.set("✅ Alertes cluster sauvegardées")
            win.destroy()

        bf = ttk.Frame(win); bf.pack(fill="x", padx=20, pady=10)
        ttk.Button(bf, text="💾 Enregistrer", command=save, bootstyle="success", width=16).pack(side="left")
        ttk.Button(bf, text="✖ Annuler", command=win.destroy, bootstyle="secondary", width=12).pack(side="right")

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

    # ==========================================
    # --- ONGLET DXCC ---
    # ==========================================
    def _build_dxcc_tab(self, parent):
        top = tk.Frame(parent, bg="#11273f"); top.pack(fill="x")
        ttk.Button(top, text="🔄 Calculer depuis le log", command=self.compute_dxcc, bootstyle="primary").pack(side="left", padx=5)
        ttk.Button(top, text="✅ Marquer sélection comme CONFIRMÉ", command=self.confirm_dxcc_selection, bootstyle="success-outline").pack(side="left", padx=5)
        ttk.Button(top, text="❌ Retirer confirmation", command=self.unconfirm_dxcc, bootstyle="danger-outline").pack(side="left", padx=5)
        ttk.Button(top, text="📤 Export ADIF LoTW", command=self.export_lotw_adif, bootstyle="info-outline").pack(side="left", padx=5)

        # Compteurs
        self.dxcc_info_var = tk.StringVar(value="Entités: --  |  Travaillées: --  |  Confirmées: --")
        ttk.Label(top, textvariable=self.dxcc_info_var, font=("Consolas",11,"bold"), foreground="#f39c12").pack(side="right", padx=10)

        # Filtre bande
        flt = tk.Frame(parent, bg="#11273f"); flt.pack(fill="x")
        ttk.Label(flt, text="Filtrer bande:").pack(side="left", padx=5)
        self.dxcc_band_var = tk.StringVar(value="All")
        cb = ttk.Combobox(flt, textvariable=self.dxcc_band_var,
                           values=["All","160m","80m","40m","30m","20m","17m","15m","12m","10m","6m"], width=7)
        cb.pack(side="left", padx=3)
        cb.bind("<<ComboboxSelected>>", lambda e: self.compute_dxcc())

        ttk.Label(flt, text="Afficher:").pack(side="left", padx=(15,3))
        self.dxcc_show_var = tk.StringVar(value="All")
        cb2 = ttk.Combobox(flt, textvariable=self.dxcc_show_var,
                            values=["All","Confirmées","Non confirmées","Nouvelles (jamais travaillées)"], width=22)
        cb2.pack(side="left", padx=3)
        cb2.bind("<<ComboboxSelected>>", lambda e: self.compute_dxcc())

        # Treeview DXCC
        cols = ("Entité","QSOs","Bandes","Première date","Callsigns","Statut","Notes")
        self.tree_dxcc = ttk.Treeview(parent, columns=cols, show='headings', style="Custom.Treeview")
        self.tree_dxcc.heading("Entité", text="Entité DXCC"); self.tree_dxcc.column("Entité", width=180, anchor="w")
        self.tree_dxcc.heading("QSOs", text="QSOs"); self.tree_dxcc.column("QSOs", width=55, anchor="center")
        self.tree_dxcc.heading("Bandes", text="Bandes"); self.tree_dxcc.column("Bandes", width=150, anchor="w")
        self.tree_dxcc.heading("Première date", text="1er QSO"); self.tree_dxcc.column("Première date", width=100, anchor="center")
        self.tree_dxcc.heading("Callsigns", text="Ex. indicatifs"); self.tree_dxcc.column("Callsigns", width=180, anchor="w")
        self.tree_dxcc.heading("Statut", text="Statut"); self.tree_dxcc.column("Statut", width=100, anchor="center")
        self.tree_dxcc.heading("Notes", text="Notes"); self.tree_dxcc.column("Notes", width=200, anchor="w")
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_dxcc.yview)
        self.tree_dxcc.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree_dxcc.pack(fill="both", expand=True)
        self.tree_dxcc.tag_configure('confirmed', background='#1a5e20', foreground='#58d68d')
        self.tree_dxcc.tag_configure('worked', background='#11273f', foreground='white')
        self.tree_dxcc.tag_configure('new', background='#4a235a', foreground='#e8daef')

        # Double-clic → éditer notes
        self.tree_dxcc.bind("<Double-1>", self._edit_dxcc_notes)

    def compute_dxcc(self):
        """Recalcule les entités DXCC depuis le logbook."""
        for item in self.tree_dxcc.get_children(): self.tree_dxcc.delete(item)
        c = self.conn.cursor()

        band_f = self.dxcc_band_var.get().lower()
        show_f = self.dxcc_show_var.get()

        # Récupérer tous les QSOs
        q = "SELECT callsign, band, mode, qso_date, lotw_stat FROM qsos"
        rows = c.execute(q).fetchall()

        # Grouper par entité DXCC
        dxcc = {}
        for call, band, mode, date, lotw in rows:
            entity = get_country_name(call)
            if not entity: entity = "?? " + (call[:3] if call else "???")
            if entity not in dxcc:
                dxcc[entity] = {'qsos': 0, 'bands': set(), 'dates': [], 'calls': [], 'confirmed': False}
            dxcc[entity]['qsos'] += 1
            dxcc[entity]['bands'].add(band or "?")
            dxcc[entity]['dates'].append(date or "")
            if call and call not in dxcc[entity]['calls'][:5]: dxcc[entity]['calls'].append(call)
            if lotw and lotw.upper() in ('OK','YES','Y','LOTW'): dxcc[entity]['confirmed'] = True

        # Charger confirmations DB
        for row in c.execute("SELECT entity, confirmed FROM dxcc_confirmed"):
            if row[0] in dxcc and row[1]:
                dxcc[row[0]]['confirmed'] = True

        # Remplir le tableau
        worked_count = len(dxcc)
        confirmed_count = sum(1 for v in dxcc.values() if v['confirmed'])

        for entity, data in sorted(dxcc.items()):
            # Filtre bande
            if band_f != "all":
                if band_f not in {b.lower() for b in data['bands']}: continue
            # Filtre statut
            if show_f == "Confirmées" and not data['confirmed']: continue
            if show_f == "Non confirmées" and data['confirmed']: continue

            bands_str = ", ".join(sorted(data['bands']))
            first_date = min(data['dates']) if data['dates'] else ""
            calls_str = ", ".join(data['calls'][:4])
            statut = "✅ Confirmé" if data['confirmed'] else "📡 Travaillé"

            # Récupérer notes depuis DB
            notes_row = c.execute("SELECT notes FROM dxcc_confirmed WHERE entity=?", (entity,)).fetchone()
            notes = notes_row[0] if notes_row else ""

            tag = 'confirmed' if data['confirmed'] else 'worked'
            self.tree_dxcc.insert("", "end",
                values=(entity, data['qsos'], bands_str, first_date, calls_str, statut, notes or ""),
                tags=(tag,))

        self.dxcc_info_var.set(f"Entités: {worked_count}  |  Travaillées: {worked_count}  |  Confirmées: {confirmed_count}")

    def confirm_dxcc_selection(self):
        """Marque les entités sélectionnées comme confirmées."""
        sel = self.tree_dxcc.selection()
        if not sel: messagebox.showinfo("Info","Sélectionnez des entités d'abord"); return
        c = self.conn.cursor()
        for item in sel:
            entity = self.tree_dxcc.item(item)['values'][0]
            c.execute("INSERT OR REPLACE INTO dxcc_confirmed (entity, confirmed) VALUES (?,1)", (entity,))
        self.conn.commit()
        self.compute_dxcc()
        self.status_var.set(f"✅ {len(sel)} entité(s) marquée(s) comme confirmée(s)")

    def unconfirm_dxcc(self):
        sel = self.tree_dxcc.selection()
        if not sel: return
        c = self.conn.cursor()
        for item in sel:
            entity = self.tree_dxcc.item(item)['values'][0]
            c.execute("UPDATE dxcc_confirmed SET confirmed=0 WHERE entity=?", (entity,))
        self.conn.commit()
        self.compute_dxcc()

    def _edit_dxcc_notes(self, event=None):
        sel = self.tree_dxcc.selection()
        if not sel: return
        v = self.tree_dxcc.item(sel[0])['values']
        entity = v[0]; current_notes = v[6] if len(v) > 6 else ""

        win = tk.Toplevel(self.root)
        win.title(f"📝 Notes DXCC — {entity}"); win.geometry("400x200"); win.grab_set()
        frm = ttk.Frame(win, padding=15); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Entité : {entity}", font=("Arial",11,"bold")).pack(anchor="w", pady=(0,8))
        ttk.Label(frm, text="Notes :").pack(anchor="w")
        txt = tk.Text(frm, height=4, font=("Arial",10)); txt.pack(fill="both", expand=True, pady=5)
        txt.insert("1.0", current_notes)

        def save():
            notes = txt.get("1.0", tk.END).strip()
            c = self.conn.cursor()
            c.execute("INSERT OR REPLACE INTO dxcc_confirmed (entity, notes, confirmed) VALUES (?, ?, COALESCE((SELECT confirmed FROM dxcc_confirmed WHERE entity=?),0))",
                      (entity, notes, entity))
            self.conn.commit()
            self.compute_dxcc(); win.destroy()

        bf = ttk.Frame(win); bf.pack(fill="x", padx=15, pady=5)
        ttk.Button(bf, text="💾 OK", command=save, bootstyle="success").pack(side="left")
        ttk.Button(bf, text="✖", command=win.destroy, bootstyle="secondary").pack(side="right")

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
        ttk.Label(left, text="🌞 DONNÉES SOLAIRES", font=("Impact",14), foreground="#f39c12").pack(anchor="w", pady=(0,8))

        btn_fr = tk.Frame(left, bg="#11273f"); btn_fr.pack(fill="x", pady=5)
        ttk.Button(btn_fr, text="🔄 Actualiser", command=self._refresh_propagation, bootstyle="primary").pack(side="left")
        ttk.Button(btn_fr, text="🌐 DX Maps", command=lambda: __import__('webbrowser').open("https://www.dxmaps.com/spots/mapg.php?Lan=E&Frec=28.0&ML=M&Map=EU&HF=1"), bootstyle="info-outline").pack(side="left", padx=5)
        ttk.Button(btn_fr, text="📡 VOACAP", command=lambda: __import__('webbrowser').open("https://www.voacap.com/hf/"), bootstyle="secondary-outline").pack(side="left", padx=5)

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
        ttk.Label(left, text="🌓 GREYLINE", font=("Impact",13), foreground="#3498db").pack(anchor="w")
        self.prop_greyline_var = tk.StringVar(value="Calcul en cours...")
        ttk.Label(left, textvariable=self.prop_greyline_var, font=("Consolas",10), foreground="#3498db", wraplength=300, justify="left").pack(anchor="w", pady=5)

        ttk.Separator(left).pack(fill="x", pady=10)

        # Tableau des bandes (conditions)
        ttk.Label(left, text="📻 CONDITIONS PAR BANDE", font=("Impact",13), foreground="#2ecc71").pack(anchor="w", pady=(5,3))
        self.band_cond_frame = tk.Frame(left, bg="#11273f"); self.band_cond_frame.pack(fill="x")

        # --- Droite : graphique MUF / ionosphère ---
        ttk.Label(right, text="🔭 IONOSPHÈRE / MUF", font=("Impact",14), foreground="#2ecc71").pack(anchor="w", pady=(0,5))

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

            self.root.after(0, lambda: self._update_prop_ui(data, band_data, vhf_data))
        except Exception as e:
            print(f"Propagation fetch error: {e}")
            self.root.after(0, lambda: self.status_var.set("⚠️ Erreur lecture données propagation"))

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
    # --- ONGLET DX WORLD ---
    # ==========================================

    # Base DXCC complète : (préfixe, entité, continent, latitude, longitude)
    DXCC_DATA = [
        # Europe
        ("ON",   "Belgium",          "EU",  50.8,   4.4),
        ("F",    "France",           "EU",  46.0,   2.3),
        ("DL",   "Germany",          "EU",  51.2,  10.5),
        ("G",    "England",          "EU",  52.5,  -1.5),
        ("GW",   "Wales",            "EU",  52.3,  -3.8),
        ("GM",   "Scotland",         "EU",  56.8,  -4.2),
        ("GI",   "N. Ireland",       "EU",  54.6,  -6.7),
        ("GD",   "Isle of Man",      "EU",  54.2,  -4.5),
        ("GJ",   "Jersey",           "EU",  49.2,  -2.1),
        ("GU",   "Guernsey",         "EU",  49.5,  -2.6),
        ("I",    "Italy",            "EU",  42.5,  12.5),
        ("IS0",  "Sardinia",         "EU",  40.1,   9.0),
        ("IT9",  "Sicily",           "EU",  37.6,  14.3),
        ("EA",   "Spain",            "EU",  40.4,  -3.7),
        ("EA8",  "Canary Is.",       "AF",  28.1, -15.4),
        ("EA9",  "Ceuta & Melilla",  "AF",  35.9,  -5.3),
        ("CT",   "Portugal",         "EU",  39.4,  -8.2),
        ("CT3",  "Madeira",          "AF",  32.7, -17.0),
        ("CU",   "Azores",           "EU",  37.7, -25.7),
        ("PA",   "Netherlands",      "EU",  52.1,   5.3),
        ("LX",   "Luxembourg",       "EU",  49.8,   6.1),
        ("HB",   "Switzerland",      "EU",  47.0,   8.2),
        ("HB0",  "Liechtenstein",    "EU",  47.2,   9.5),
        ("OE",   "Austria",          "EU",  47.5,  13.5),
        ("OZ",   "Denmark",          "EU",  56.0,  10.0),
        ("OY",   "Faroe Is.",        "EU",  62.0,  -7.0),
        ("OH",   "Finland",          "EU",  64.0,  26.0),
        ("OH0",  "Aland Is.",        "EU",  60.2,  20.0),
        ("OJ0",  "Market Reef",      "EU",  60.3,  19.1),
        ("SM",   "Sweden",           "EU",  63.0,  16.0),
        ("LA",   "Norway",           "EU",  65.0,  14.0),
        ("TF",   "Iceland",          "EU",  64.9, -18.2),
        ("EI",   "Ireland",          "EU",  53.2,  -8.2),
        ("SP",   "Poland",           "EU",  52.0,  20.0),
        ("OK",   "Czech Rep.",       "EU",  50.0,  15.5),
        ("OM",   "Slovakia",         "EU",  48.7,  19.7),
        ("HA",   "Hungary",          "EU",  47.2,  19.4),
        ("YO",   "Romania",          "EU",  45.9,  24.9),
        ("LZ",   "Bulgaria",         "EU",  42.7,  25.5),
        ("SV",   "Greece",           "EU",  39.1,  21.8),
        ("SV5",  "Dodecanese",       "EU",  36.2,  28.0),
        ("SV9",  "Crete",            "EU",  35.2,  24.9),
        ("9A",   "Croatia",          "EU",  45.2,  16.5),
        ("S5",   "Slovenia",         "EU",  46.1,  14.8),
        ("E7",   "Bosnia-Herz.",     "EU",  44.2,  17.9),
        ("YU",   "Serbia",           "EU",  44.0,  21.0),
        ("Z3",   "N. Macedonia",     "EU",  41.6,  21.7),
        ("Z6",   "Kosovo",           "EU",  42.6,  20.9),
        ("T7",   "San Marino",       "EU",  43.9,  12.5),
        ("1A",   "SMOM Malta",       "EU",  35.9,  14.5),
        ("9H",   "Malta",            "EU",  35.9,  14.5),
        ("ES",   "Estonia",          "EU",  58.8,  25.5),
        ("YL",   "Latvia",           "EU",  57.0,  25.0),
        ("LY",   "Lithuania",        "EU",  56.0,  24.0),
        ("YM",   "Turkey",           "AS",  39.0,  35.0),
        ("TA",   "Turkey",           "AS",  39.0,  35.0),
        ("5B",   "Cyprus",           "AS",  35.1,  33.4),
        ("ZB",   "Gibraltar",        "EU",  36.1,  -5.4),
        ("UA",   "Russia (EU)",      "EU",  58.0,  56.0),
        ("UA2",  "Kaliningrad",      "EU",  54.7,  20.5),
        ("UA9",  "Russia (AS)",      "AS",  60.0,  80.0),
        ("EK",   "Armenia",          "AS",  40.3,  44.9),
        ("4J",   "Azerbaijan",       "AS",  40.5,  47.5),
        ("4L",   "Georgia",          "AS",  42.3,  43.4),
        ("UR",   "Ukraine",          "EU",  49.0,  32.0),
        ("EM",   "Ukraine",          "EU",  49.0,  32.0),
        ("EU",   "Belarus",          "EU",  53.7,  27.9),
        ("ER",   "Moldova",          "EU",  47.0,  28.9),
        ("OA",   "Albania",          "EU",  41.3,  20.2),
        ("ZA",   "Albania",          "EU",  41.3,  20.2),
        ("4O",   "Montenegro",       "EU",  42.8,  19.5),
        # Asie
        ("JA",   "Japan",            "AS",  36.0, 138.0),
        ("JD1",  "Minami Torishima", "OC",  24.3, 153.9),
        ("BY",   "China",            "AS",  35.0, 105.0),
        ("BV",   "Taiwan",           "AS",  23.7, 120.9),
        ("HL",   "South Korea",      "AS",  37.5, 127.0),
        ("DS",   "South Korea",      "AS",  37.5, 127.0),
        ("HS",   "Thailand",         "AS",  15.5, 101.0),
        ("XW",   "Laos",             "AS",  18.0, 103.0),
        ("XV",   "Vietnam",          "AS",  16.0, 108.0),
        ("XU",   "Cambodia",         "AS",  12.5, 104.9),
        ("XZ",   "Myanmar",          "AS",  19.8,  96.2),
        ("DU",   "Philippines",      "OC",  13.0, 122.0),
        ("YB",   "Indonesia",        "OC",  -5.0, 120.0),
        ("9V",   "Singapore",        "AS",   1.3, 103.8),
        ("9M",   "West Malaysia",    "AS",   3.0, 109.0),
        ("9M6",  "East Malaysia",    "OC",   4.5, 114.4),
        ("VU",   "India",            "AS",  22.0,  80.0),
        ("VU7",  "Lakshadweep Is.",  "AS",  10.6,  72.6),
        ("4S",   "Sri Lanka",        "AS",   7.9,  80.8),
        ("AP",   "Pakistan",         "AS",  30.0,  70.0),
        ("9N",   "Nepal",            "AS",  28.0,  84.0),
        ("S2",   "Bangladesh",       "AS",  23.7,  90.4),
        ("A5",   "Bhutan",           "AS",  27.5,  90.4),
        ("S7",   "Seychelles",       "AF",  -4.7,  55.5),
        ("EP",   "Iran",             "AS",  32.0,  53.0),
        ("YK",   "Syria",            "AS",  35.0,  38.5),
        ("OD",   "Lebanon",          "AS",  33.9,  35.5),
        ("4X",   "Israel",           "AS",  31.7,  35.1),
        ("4Z",   "Israel",           "AS",  31.7,  35.1),
        ("JY",   "Jordan",           "AS",  31.3,  37.0),
        ("HZ",   "Saudi Arabia",     "AS",  24.0,  44.0),
        ("A7",   "Qatar",            "AS",  25.3,  51.2),
        ("A9",   "Bahrain",          "AS",  26.2,  50.6),
        ("A6",   "UAE",              "AS",  24.2,  54.4),
        ("A4",   "Oman",             "AS",  22.0,  57.0),
        ("7O",   "Yemen",            "AS",  15.5,  48.5),
        ("9K",   "Kuwait",           "AS",  29.4,  47.7),
        ("YI",   "Iraq",             "AS",  33.0,  44.0),
        ("EX",   "Kyrgyzstan",       "AS",  41.5,  74.8),
        ("EY",   "Tajikistan",       "AS",  39.0,  71.0),
        ("EZ",   "Turkmenistan",     "AS",  39.0,  59.0),
        ("UK",   "Uzbekistan",       "AS",  41.0,  64.5),
        ("UN",   "Kazakhstan",       "AS",  50.0,  68.0),
        ("T2",   "Tuvalu",           "OC",  -8.5, 179.2),
        ("T3",   "W. Kiribati",      "OC",   1.4, 173.0),
        ("T31",  "C. Kiribati",      "OC",  -2.9, -171.7),
        ("T32",  "E. Kiribati",      "OC",   2.0, -157.5),
        ("YJ",   "Vanuatu",          "OC", -16.0, 167.0),
        # Afrique
        ("7X",   "Algeria",          "AF",  28.0,   3.0),
        ("CN",   "Morocco",          "AF",  32.0,  -5.0),
        ("SU",   "Egypt",            "AF",  26.0,  30.0),
        ("5Z",   "Kenya",            "AF",  -1.0,  38.0),
        ("XT",   "Burkina Faso",     "AF",  13.0,  -2.0),
        ("TY",   "Benin",            "AF",   9.5,   2.4),
        ("5N",   "Nigeria",          "AF",   9.0,   8.0),
        ("5U",   "Niger",            "AF",  17.0,   8.0),
        ("TJ",   "Cameroon",         "AF",   4.0,  12.0),
        ("TL",   "C. African Rep.",  "AF",   7.0,  21.0),
        ("TT",   "Chad",             "AF",  15.0,  19.0),
        ("6W",   "Senegal",          "AF",  14.5, -14.5),
        ("9G",   "Ghana",            "AF",   8.0,  -2.0),
        ("TR",   "Gabon",            "AF",  -0.5,  11.8),
        ("5H",   "Tanzania",         "AF",  -6.0,  35.0),
        ("9J",   "Zambia",           "AF", -13.5,  28.0),
        ("ZE",   "Zimbabwe",         "AF", -20.0,  30.0),
        ("C9",   "Mozambique",       "AF", -18.0,  35.0),
        ("7Q",   "Malawi",           "AF", -13.5,  34.0),
        ("ZS",   "South Africa",     "AF", -29.0,  25.0),
        ("ZS8",  "Marion Is.",       "AF", -46.9,  37.7),
        ("5V",   "Togo",             "AF",   8.0,   1.2),
        ("9L",   "Sierra Leone",     "AF",   8.5, -12.0),
        ("EL",   "Liberia",          "AF",   6.5,  -9.5),
        ("TU",   "Ivory Coast",      "AF",   7.5,  -5.5),
        ("9I",   "Zambia",           "AF", -13.5,  28.0),
        ("V5",   "Namibia",          "AF", -22.0,  17.0),
        ("A2",   "Botswana",         "AF", -22.0,  24.0),
        ("3DA",  "Swaziland",        "AF", -26.5,  31.5),
        ("ZD7",  "St. Helena",       "AF", -15.9,  -5.7),
        ("ZD8",  "Ascension Is.",    "AF",  -7.9, -14.4),
        ("5A",   "Libya",            "AF",  27.0,  17.0),
        ("ST",   "Sudan",            "AF",  15.0,  30.0),
        ("ET",   "Ethiopia",         "AF",   9.0,  40.0),
        ("T5",   "Somalia",          "AF",   2.0,  46.0),
        ("E3",   "Eritrea",          "AF",  15.3,  38.9),
        ("J2",   "Djibouti",         "AF",  11.8,  42.6),
        ("S0",   "W. Sahara",        "AF",  24.0, -13.0),
        ("6V",   "Senegal",          "AF",  14.5, -14.5),
        ("TZ",   "Mali",             "AF",  17.0,  -4.0),
        ("5T",   "Mauritania",       "AF",  20.0, -12.0),
        ("D4",   "Cape Verde",       "AF",  16.0, -24.0),
        ("3B9",  "Rodriguez Is.",    "AF", -19.7,  63.4),
        ("3B8",  "Mauritius",        "AF", -20.3,  57.5),
        ("3B6",  "Agalega & S.B.",   "AF", -10.4,  56.6),
        ("FR",   "Reunion",          "AF", -21.1,  55.5),
        ("FT5W", "Crozet Is.",       "AF", -46.4,  51.9),
        ("FT5X", "Kerguelen Is.",    "AF", -49.4,  70.2),
        ("FT4Y", "Antarctica",       "AN", -90.0,   0.0),
        ("ZL5",  "Antarctica",       "AN", -90.0,   0.0),
        # Amérique du Nord
        ("K",    "USA",              "NA",  38.0,  -97.0),
        ("VE",   "Canada",           "NA",  60.0, -100.0),
        ("XE",   "Mexico",           "NA",  23.0,  -102.0),
        ("KP4",  "Puerto Rico",      "NA",  18.2,  -66.6),
        ("KP2",  "US Virgin Is.",    "NA",  17.7,  -64.8),
        ("KG4",  "Guantanamo",       "NA",  20.0,  -75.1),
        ("KH6",  "Hawaii",           "OC",  21.3, -157.8),
        ("KH0",  "Mariana Is.",      "OC",  15.2, 145.8),
        ("KH2",  "Guam",             "OC",  13.5, 144.8),
        ("KH8",  "American Samoa",   "OC", -14.3, -170.7),
        ("KH9",  "Wake Is.",         "OC",  19.3, 166.6),
        ("KH5",  "Palmyra Is.",      "OC",   5.9, -162.1),
        ("VP9",  "Bermuda",          "NA",  32.3,  -64.8),
        ("TI",   "Costa Rica",       "NA",   9.8,  -84.0),
        ("TG",   "Guatemala",        "NA",  15.5,  -90.2),
        ("HR",   "Honduras",         "NA",  15.0,  -86.5),
        ("YS",   "El Salvador",      "NA",  13.7,  -89.2),
        ("HP",   "Panama",           "NA",   8.5,  -80.0),
        ("CO",   "Cuba",             "NA",  22.0,  -79.5),
        ("HH",   "Haiti",            "NA",  19.0,  -72.5),
        ("HI",   "Dom. Republic",    "NA",  19.0,  -70.7),
        ("6Y",   "Jamaica",          "NA",  18.1,  -77.3),
        ("8P",   "Barbados",         "NA",  13.2,  -59.6),
        ("VP2E", "Anguilla",         "NA",  18.2,  -63.1),
        ("VP2M", "Montserrat",       "NA",  16.7,  -62.2),
        ("VP2V", "BVI",              "NA",  18.4,  -64.6),
        ("VP5",  "Turks & Caicos",   "NA",  21.8,  -72.0),
        ("J3",   "Grenada",          "NA",  12.1,  -61.7),
        ("J6",   "St. Lucia",        "NA",  13.9,  -60.9),
        ("J7",   "Dominica",         "NA",  15.4,  -61.4),
        ("J8",   "St. Vincent",      "NA",  13.3,  -61.2),
        ("V2",   "Antigua",          "NA",  17.1,  -61.8),
        ("V4",   "St. Kitts",        "NA",  17.3,  -62.7),
        ("ZF",   "Cayman Is.",       "NA",  19.3,  -81.4),
        # Amérique du Sud
        ("PY",   "Brazil",           "SA", -15.0,  -55.0),
        ("LU",   "Argentina",        "SA", -35.0,  -64.0),
        ("CE",   "Chile",            "SA", -30.0,  -70.0),
        ("HK",   "Colombia",         "SA",   4.0,  -74.0),
        ("OA",   "Peru",             "SA", -10.0,  -76.0),
        ("CX",   "Uruguay",          "SA", -33.0,  -56.0),
        ("YV",   "Venezuela",        "SA",   8.0,  -66.0),
        ("FY",   "French Guiana",    "SA",   4.0,  -53.0),
        ("PZ",   "Suriname",         "SA",   4.0,  -56.0),
        ("GY",   "Guyana",           "SA",   5.0,  -59.0),
        ("HC",   "Ecuador",          "SA",  -2.0,  -78.0),
        ("HP",   "Panama",           "NA",   8.5,  -80.0),
        ("CP",   "Bolivia",          "SA", -17.0,  -64.0),
        ("PY0F", "Fernando Noronha", "SA",  -3.9,  -32.4),
        ("PY0S", "St. Peter & Paul", "SA",   0.9,  -29.4),
        ("PY0T", "Trindade & M.V.",  "SA", -20.5,  -29.3),
        ("VP8",  "Falkland Is.",     "SA", -51.7,  -59.0),
        ("VP8/G","South Georgia",    "SA", -54.3,  -36.5),
        ("CE9",  "Antarctica",       "AN", -90.0,   0.0),
        ("VK0",  "Antarctica",       "AN", -90.0,   0.0),
        # Océanie
        ("VK",   "Australia",        "OC", -25.0,  135.0),
        ("ZL",   "New Zealand",      "OC", -41.0,  174.0),
        ("ZL7",  "Chatham Is.",      "OC", -44.0, -176.5),
        ("ZL8",  "Kermadec Is.",     "OC", -29.3, -177.9),
        ("ZL9",  "Campbell Is.",     "OC", -52.6,  169.1),
        ("FK",   "New Caledonia",    "OC", -22.0,  167.0),
        ("FO",   "French Polynesia", "OC", -17.5, -149.6),
        ("FW",   "Wallis & Futuna",  "OC", -13.3, -176.2),
        ("H4",   "Solomon Is.",      "OC",  -9.5,  160.0),
        ("A3",   "Tonga",            "OC", -21.2, -175.2),
        ("T2",   "Tuvalu",           "OC",  -8.5,  179.2),
        ("5W",   "Samoa",            "OC", -13.8, -172.1),
        ("KH6",  "Hawaii",           "OC",  21.3, -157.8),
        ("V6",   "Micronesia",       "OC",   6.9,  158.2),
        ("T8",   "Palau",            "OC",   7.3,  134.5),
        ("KH2",  "Guam",             "OC",  13.5,  144.8),
        ("KH0",  "Mariana Is.",      "OC",  15.2,  145.8),
        ("P2",   "Papua New Guinea", "OC",  -6.0,  147.0),
        ("KH4",  "Midway Is.",       "OC",  28.2, -177.4),
        ("VK9X", "Christmas Is.",    "OC", -10.5,  105.6),
        ("VK9C", "Cocos Keeling",    "OC", -12.2,   96.8),
        ("VK9M", "Mellish Reef",     "OC", -17.4,  155.8),
        ("VK9N", "Norfolk Is.",      "OC", -29.0,  167.9),
        ("VK0M", "Macquarie Is.",    "OC", -54.6,  158.9),
    ]

    CONTINENT_NAMES = {
        "EU": "Europe", "AS": "Asie", "AF": "Afrique",
        "NA": "Am. Nord", "SA": "Am. Sud", "OC": "Océanie", "AN": "Antarctique"
    }

    def _build_dxworld_tab(self, parent):
        # Barre de contrôle
        ctrl = tk.Frame(parent, bg="#11273f"); ctrl.pack(fill="x")

        ttk.Label(ctrl, text="Recherche:").pack(side="left", padx=(5,2))
        self.dxw_search_var = tk.StringVar()
        e_search = ttk.Entry(ctrl, textvariable=self.dxw_search_var, width=18)
        e_search.pack(side="left", padx=3)
        e_search.bind("<KeyRelease>", lambda e: self._dxworld_filter())

        ttk.Label(ctrl, text="Continent:").pack(side="left", padx=(12,2))
        self.dxw_cont_var = tk.StringVar(value="Tous")
        cb_cont = ttk.Combobox(ctrl, textvariable=self.dxw_cont_var, width=12,
                                values=["Tous","Europe","Asie","Afrique","Am. Nord","Am. Sud","Océanie","Antarctique"])
        cb_cont.pack(side="left", padx=3)
        cb_cont.bind("<<ComboboxSelected>>", lambda e: self._dxworld_filter())

        ttk.Label(ctrl, text="Trier par:").pack(side="left", padx=(12,2))
        self.dxw_sort_var = tk.StringVar(value="Entité")
        cb_sort = ttk.Combobox(ctrl, textvariable=self.dxw_sort_var, width=12,
                                values=["Entité","Préfixe","Distance","Continent"])
        cb_sort.pack(side="left", padx=3)
        cb_sort.bind("<<ComboboxSelected>>", lambda e: self._dxworld_sort())

        ttk.Button(ctrl, text="X Effacer", command=self._dxworld_clear_filter,
                   bootstyle="secondary-outline", width=10).pack(side="left", padx=5)

        self.dxw_count_var = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self.dxw_count_var, foreground="#f39c12",
                  font=("Consolas", 10)).pack(side="right", padx=10)

        # Treeview
        cols = ("Préfixe", "Entité DXCC", "Continent", "Lat", "Lon",
                "Dist. km", "Short Path °", "Long Path °", "Déjà travaillé")
        self.tree_dxw = ttk.Treeview(parent, columns=cols, show='headings', style="Custom.Treeview")

        widths = [70, 200, 90, 60, 60, 90, 100, 100, 120]
        for col, w in zip(cols, widths):
            self.tree_dxw.heading(col, text=col,
                command=lambda c=col: self._dxworld_sort_col(c))
            self.tree_dxw.column(col, width=w, anchor="center")
        self.tree_dxw.column("Entité DXCC", anchor="w")

        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_dxw.yview)
        self.tree_dxw.configure(yscroll=sb.set)
        sb.pack(side="right", fill="y")
        self.tree_dxw.pack(fill="both", expand=True)

        self.tree_dxw.tag_configure('worked',    background='#1a4a1a', foreground='#58d68d')
        self.tree_dxw.tag_configure('unworked',  background='#11273f', foreground='white')
        self.tree_dxw.tag_configure('eu',        background='#1a2a4a', foreground='#85c1e9')
        self.tree_dxw.tag_configure('ant',       background='#3a2a1a', foreground='#aaa')

        # Pré-calculer toutes les distances
        self._dxworld_rows = []
        worked_entities = self._get_worked_entities()

        home = grid_to_latlon(MY_GRID)
        seen = set()
        for prefix, entity, cont, lat, lon in self.DXCC_DATA:
            key = (prefix, entity)
            if key in seen: continue
            seen.add(key)

            dist_km = ""
            short_az = ""
            long_az = ""
            if home:
                try:
                    lat1, lon1 = map(math.radians, home)
                    lat2r, lon2r = math.radians(lat), math.radians(lon)
                    dlon = lon2r - lon1
                    cos_c = math.sin(lat1)*math.sin(lat2r) + math.cos(lat1)*math.cos(lat2r)*math.cos(dlon)
                    cos_c = max(-1.0, min(1.0, cos_c))
                    dist = 6371 * math.acos(cos_c)
                    dist_km = int(dist)
                    y = math.sin(dlon) * math.cos(lat2r)
                    x = math.cos(lat1)*math.sin(lat2r) - math.sin(lat1)*math.cos(lat2r)*math.cos(dlon)
                    short_az = int((math.degrees(math.atan2(y, x)) + 360) % 360)
                    long_az = int((short_az + 180) % 360)
                except: pass

            cont_name = self.CONTINENT_NAMES.get(cont, cont)
            worked = "✅ Oui" if entity in worked_entities else "—"
            self._dxworld_rows.append({
                'prefix': prefix, 'entity': entity, 'cont': cont_name,
                'lat': f"{lat:.1f}", 'lon': f"{lon:.1f}",
                'dist': dist_km, 'short': short_az, 'long': long_az,
                'worked': worked, 'cont_code': cont
            })

        self._dxworld_filter()

    def _get_worked_entities(self):
        """Retourne l'ensemble des entités DXCC déjà travaillées dans le log."""
        c = self.conn.cursor()
        calls = c.execute("SELECT DISTINCT callsign FROM qsos").fetchall()
        entities = set()
        for (call,) in calls:
            e = get_country_name(call)
            if e: entities.add(e)
        return entities

    def _dxworld_filter(self):
        search = self.dxw_search_var.get().strip().lower()
        cont_f = self.dxw_cont_var.get()

        filtered = []
        for row in self._dxworld_rows:
            if cont_f != "Tous" and row['cont'] != cont_f: continue
            if search and search not in row['prefix'].lower() and search not in row['entity'].lower(): continue
            filtered.append(row)

        self._dxworld_display(filtered)

    def _dxworld_sort(self):
        self._dxworld_filter()

    def _dxworld_sort_col(self, col):
        col_map = {
            "Préfixe": "prefix", "Entité DXCC": "entity",
            "Continent": "cont", "Dist. km": "dist",
            "Short Path °": "short", "Long Path °": "long"
        }
        key = col_map.get(col, "entity")
        self._dxworld_rows.sort(key=lambda r: (r[key] if isinstance(r[key], str) else r[key] if r[key] != "" else 99999))
        self._dxworld_filter()

    def _dxworld_clear_filter(self):
        self.dxw_search_var.set("")
        self.dxw_cont_var.set("Tous")
        self._dxworld_filter()

    def _dxworld_display(self, rows):
        for item in self.tree_dxw.get_children(): self.tree_dxw.delete(item)

        sort_key = self.dxw_sort_var.get()
        if sort_key == "Distance":
            rows = sorted(rows, key=lambda r: r['dist'] if r['dist'] != "" else 999999)
        elif sort_key == "Entité":
            rows = sorted(rows, key=lambda r: r['entity'])
        elif sort_key == "Préfixe":
            rows = sorted(rows, key=lambda r: r['prefix'])
        elif sort_key == "Continent":
            rows = sorted(rows, key=lambda r: r['cont'])

        cont_colors = {"EU": "eu", "AN": "ant"}
        for row in rows:
            dist_str = f"{row['dist']:,}" if row['dist'] != "" else "?"
            short_str = f"{row['short']}°" if row['short'] != "" else "?"
            long_str  = f"{row['long']}°"  if row['long']  != "" else "?"
            if row['worked'] == "✅ Oui":
                tag = 'worked'
            elif row['cont_code'] == "EU":
                tag = 'eu'
            elif row['cont_code'] == "AN":
                tag = 'ant'
            else:
                tag = 'unworked'

            self.tree_dxw.insert("", "end", values=(
                row['prefix'], row['entity'], row['cont'],
                row['lat'], row['lon'],
                dist_str, short_str, long_str, row['worked']
            ), tags=(tag,))

        self.dxw_count_var.set(f"{len(rows)} entités  |  "
                                f"{sum(1 for r in rows if r['worked']=='✅ Oui')} travaillées")


    # ==========================================
    # --- 1. ALERTE DOUBLON EN TEMPS RÉEL ---
    # ==========================================
    def _check_duplicate(self, event=None):
        """Vérifie en temps réel si le callsign a déjà été travaillé."""
        call = self.e_call.get().strip().upper()
        if not call or len(call) < 3:
            self.lbl_dup.config(text="", foreground="#2ecc71")
            return
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT band, mode, qso_date FROM qsos WHERE callsign=? ORDER BY qso_date DESC",
            (call,)).fetchall()
        if not rows:
            self.lbl_dup.config(text=f"✅ {call} — Premier QSO !", foreground="#2ecc71")
            return
        # Résumé par bande
        band_modes = {}
        for band, mode, date in rows:
            key = band or "?"
            if key not in band_modes: band_modes[key] = []
            if (mode or "?") not in band_modes[key]: band_modes[key].append(mode or "?")
        summary = "  |  ".join(f"{b}: {', '.join(m)}" for b, m in sorted(band_modes.items()))
        last_date = rows[0][2] if rows else ""
        n = len(rows)
        current_band = freq_to_band(self.current_freq_hz)
        # Doublon sur la même bande ?
        same_band = [r for r in rows if r[0] == current_band]
        if same_band:
            self.lbl_dup.config(
                text=f"⚠️ DOUBLON  {call} — {n} QSO(s) dont {len(same_band)} sur {current_band}  [{summary}]  Dernier: {last_date}",
                foreground="#e74c3c")
        else:
            self.lbl_dup.config(
                text=f"🔄 Déjà travaillé  {call} — {n} QSO(s) — Bandes: {summary}  Dernier: {last_date}  ➜ Nouvelle bande possible sur {current_band}",
                foreground="#f39c12")

    # ==========================================
    # --- 2. QSL REMINDER ---
    # ==========================================
    def _build_qsl_reminder_tab(self, parent):
        ctrl = tk.Frame(parent, bg="#11273f"); ctrl.pack(fill="x")
        ttk.Label(ctrl, text="QSOs sans confirmation depuis plus de :").pack(side="left", padx=5)
        self.qslrem_days_var = tk.StringVar(value="90")
        ttk.Spinbox(ctrl, from_=7, to=730, textvariable=self.qslrem_days_var,
                    width=5, font=("Arial",10)).pack(side="left", padx=3)
        ttk.Label(ctrl, text="jours").pack(side="left", padx=2)

        ttk.Label(ctrl, text="  Système:").pack(side="left", padx=(15,2))
        self.qslrem_sys_var = tk.StringVar(value="Tous")
        ttk.Combobox(ctrl, textvariable=self.qslrem_sys_var,
                     values=["Tous","LoTW","eQSL","QRZ","ClubLog"], width=8).pack(side="left", padx=3)

        ttk.Button(ctrl, text="🔄 Rechercher", command=self._refresh_qsl_reminder,
                   bootstyle="warning").pack(side="left", padx=8)
        ttk.Button(ctrl, text="📤 Export ADIF sélection", command=self._export_reminder_adif,
                   bootstyle="info-outline").pack(side="left", padx=5)
        self.qslrem_count_var = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self.qslrem_count_var, foreground="#f39c12").pack(side="right", padx=10)

        cols = ("ID","Date","Callsign","Bande","Mode","Pays","LoTW","eQSL","QRZ","Club","Jours sans confirm.")
        self.tree_qslrem = ttk.Treeview(parent, columns=cols, show='headings', style="Custom.Treeview")
        widths = [0,90,110,60,60,130,60,60,60,60,120]
        for col, w in zip(cols, widths):
            self.tree_qslrem.heading(col, text=col)
            self.tree_qslrem.column(col, width=w, anchor="center")
        self.tree_qslrem.column("ID", width=0, stretch=tk.NO)
        self.tree_qslrem.column("Callsign", anchor="w")
        self.tree_qslrem.column("Pays", anchor="w")
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_qslrem.yview)
        self.tree_qslrem.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree_qslrem.pack(fill="both", expand=True)
        self.tree_qslrem.tag_configure('warn',  background='#4a2800', foreground='#ffa040')
        self.tree_qslrem.tag_configure('old',   background='#4a0000', foreground='#ff6060')
        self.tree_qslrem.tag_configure('lotw',  background='#003a20', foreground='#58d68d')
        # Lancer au chargement
        self.root.after(1500, self._refresh_qsl_reminder)

    def _refresh_qsl_reminder(self):
        for item in self.tree_qslrem.get_children(): self.tree_qslrem.delete(item)
        try:
            days = int(self.qslrem_days_var.get())
        except: days = 90
        sys_f = self.qslrem_sys_var.get()
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT id, qso_date, callsign, band, mode, qrz_stat, eqsl_stat, lotw_stat, club_stat "
            "FROM qsos WHERE qso_date != '' ORDER BY qso_date ASC").fetchall()
        today = datetime.now(timezone.utc).date()
        found = 0
        for row in rows:
            qso_id, date_s, call, band, mode, qrz, eqsl, lotw, club = row
            # Calculer ancienneté
            try:
                qso_date = datetime.strptime(date_s[:10], "%Y-%m-%d").date()
                age_days = (today - qso_date).days
            except: age_days = 0
            if age_days < days: continue
            # Vérifier si au moins un système non confirmé
            confirmed = {
                "LoTW": lotw and lotw.upper() in ("OK","YES","Y","LOTW"),
                "eQSL": eqsl and eqsl.upper() in ("OK","YES","Y"),
                "QRZ":  qrz  and qrz.upper()  in ("OK","YES","Y"),
                "Club": club and club.upper()  in ("OK","YES","Y","CLUBLOG"),
            }
            if sys_f == "Tous":
                pending = [k for k, v in confirmed.items() if not v]
            elif sys_f in confirmed:
                pending = [sys_f] if not confirmed[sys_f] else []
            else:
                pending = []
            if not pending: continue
            country = get_country_name(call)
            lotw_s = "✅" if confirmed["LoTW"] else "⏳"
            eqsl_s = "✅" if confirmed["eQSL"] else "⏳"
            qrz_s  = "✅" if confirmed["QRZ"]  else "⏳"
            club_s = "✅" if confirmed["Club"] else "⏳"
            tag = 'old' if age_days > 365 else 'warn'
            self.tree_qslrem.insert("", "end", values=(
                qso_id, date_s[:10], call, band or "?", mode or "?",
                country, lotw_s, eqsl_s, qrz_s, club_s, f"{age_days} j."
            ), tags=(tag,))
            found += 1
        self.qslrem_count_var.set(f"{found} QSO(s) en attente de confirmation")

    def _export_reminder_adif(self):
        """Exporte les QSOs sélectionnés depuis le reminder."""
        sel = self.tree_qslrem.selection()
        if not sel:
            # Exporter tout si rien sélectionné
            sel = self.tree_qslrem.get_children()
        if not sel: return
        fn = filedialog.asksaveasfilename(defaultextension=".adi",
            filetypes=[("ADIF","*.adi")], title="Export QSL Reminder")
        if not fn: return
        ids = [self.tree_qslrem.item(item)['values'][0] for item in sel]
        c = self.conn.cursor()
        with open(fn,"w",encoding="utf-8") as f:
            f.write(f"QSL Reminder Export -- {MY_CALL}\n<EOH>\n")
            for qso_id in ids:
                row = c.execute(
                    "SELECT callsign, qso_date, time_on, band, mode, rst_sent, rst_rcvd, grid, freq "
                    "FROM qsos WHERE id=?", (qso_id,)).fetchone()
                if not row: continue
                call, date_s, time_s, band, mode, rst_s, rst_r, grid, freq_raw = row
                def adif(t,v): v=str(v or "").strip(); return f"<{t}:{len(v)}>{v} " if v else ""
                freq_mhz=""
                try:
                    fv=float(freq_raw); freq_mhz=f"{fv/1e6:.6f}" if fv>1e4 else f"{fv:.6f}"
                except: pass
                rec  = adif("CALL",call)
                rec += adif("QSO_DATE",date_s.replace("-",""))
                rec += adif("TIME_ON",time_s.replace(":","")[:4])
                rec += adif("BAND",band); rec += adif("MODE",mode)
                rec += adif("FREQ",freq_mhz); rec += adif("RST_SENT",rst_s); rec += adif("RST_RCVD",rst_r)
                rec += adif("GRIDSQUARE",grid); rec += "<EOR>\n"
                f.write(rec)
        messagebox.showinfo("Export","Fichier ADIF créé pour QSL Reminder !")

    # ==========================================
    # --- 3. AWARDS TRACKER ---
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

    # Groupes IOTA (les plus courants Europe/Afrique/Asie)
    IOTA_GROUPS = {
        "EU-001":"Gran Canaria","EU-003":"Balearic Is","EU-004":"Corsica",
        "EU-005":"Sardinia","EU-008":"Sicily","EU-009":"Malta",
        "EU-011":"Faroe Is","EU-013":"Iceland","EU-015":"Azores",
        "EU-016":"Madeira","EU-021":"Jersey/Guernsey","EU-028":"Lofoten Is",
        "EU-037":"Gotland","EU-041":"Aland Is","EU-042":"Saaremaa",
        "AF-004":"Canary Is","AF-019":"Madeira","AF-022":"Cape Verde",
        "AF-028":"Reunion","AF-032":"Mauritius","AF-048":"Seychelles",
        "AS-001":"Ogasawara","AS-007":"Okinawa","AS-013":"Hokkaido",
        "OC-001":"VK (main)","OC-008":"Lord Howe","OC-013":"Norfolk Is",
        "NA-005":"Hawaii","NA-006":"Bermuda","NA-009":"Newfoundland",
        "SA-006":"Galapagos","SA-018":"Fernando Noronha",
    }

    def _build_awards_tab(self, parent):
        nb_awards = ttk.Notebook(parent, bootstyle="success")
        nb_awards.pack(fill="both", expand=True, padx=5, pady=5)

        # --- DXCC Award ---
        t_dxcc_aw = tk.Frame(nb_awards, bg="#11273f"); nb_awards.add(t_dxcc_aw, text="🌍 DXCC")
        self._build_award_dxcc(t_dxcc_aw)

        # --- WAZ Award ---
        t_waz = tk.Frame(nb_awards, bg="#11273f"); nb_awards.add(t_waz, text="🗺️ WAZ (40 zones)")
        self._build_award_waz(t_waz)

        # --- WAS Award ---
        t_was = tk.Frame(nb_awards, bg="#11273f"); nb_awards.add(t_was, text="🇺🇸 WAS (50 états)")
        self._build_award_was(t_was)

        # --- IOTA ---
        t_iota = tk.Frame(nb_awards, bg="#11273f"); nb_awards.add(t_iota, text="🏝️ IOTA")
        self._build_award_iota(t_iota)

        ttk.Button(parent, text="🔄 Recalculer tous les awards",
                   command=self._refresh_all_awards, bootstyle="success").pack(pady=5)

    def _build_award_dxcc(self, parent):
        info_fr = tk.Frame(parent, bg="#11273f"); info_fr.pack(fill="x")
        self.aw_dxcc_var = tk.StringVar(value="Calcul en cours...")
        ttk.Label(info_fr, textvariable=self.aw_dxcc_var,
                  font=("Impact",16), foreground="#f39c12").pack(side="left")

        # Barres de progression pour les paliers
        prog_fr = tk.Frame(parent, bg="#11273f"); prog_fr.pack(fill="x")
        self.aw_dxcc_bars = {}
        for threshold, label, color in [(100,"DXCC 100","success"),(200,"DXCC 200","info"),
                                         (300,"DXCC 300","warning"),(340,"DXCC Honor Roll","danger")]:
            f = tk.Frame(prog_fr, bg="#11273f"); f.pack(fill="x", pady=3)
            ttk.Label(f, text=f"{label}:", width=18, anchor="e").pack(side="left")
            pb = ttk.Progressbar(f, maximum=threshold, bootstyle=color+"-striped", length=400)
            pb.pack(side="left", padx=8)
            lbl = ttk.Label(f, text="0 / "+str(threshold), width=12, foreground="white")
            lbl.pack(side="left")
            self.aw_dxcc_bars[threshold] = (pb, lbl)

        # Liste des entités manquantes
        ttk.Label(parent, text="Entités travaillées :", font=("Arial",10,"bold"), foreground="#aaa").pack(anchor="w", padx=10, pady=(8,2))
        cols = ("Entité","QSOs","Confirmé")
        self.tree_aw_dxcc = ttk.Treeview(parent, columns=cols, show='headings', height=10, style="Custom.Treeview")
        for col in cols: self.tree_aw_dxcc.heading(col, text=col)
        self.tree_aw_dxcc.column("Entité", width=200, anchor="w")
        self.tree_aw_dxcc.column("QSOs", width=70, anchor="center")
        self.tree_aw_dxcc.column("Confirmé", width=100, anchor="center")
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_aw_dxcc.yview)
        self.tree_aw_dxcc.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree_aw_dxcc.pack(fill="both", expand=True, padx=5)
        self.tree_aw_dxcc.tag_configure('conf', background='#1a4a1a', foreground='#58d68d')
        self.tree_aw_dxcc.tag_configure('worked', background='#11273f')

    def _build_award_waz(self, parent):
        info_fr = tk.Frame(parent, bg="#11273f"); info_fr.pack(fill="x")
        self.aw_waz_var = tk.StringVar(value="Calcul en cours...")
        ttk.Label(info_fr, textvariable=self.aw_waz_var,
                  font=("Impact",16), foreground="#3498db").pack(side="left")
        pb_fr = tk.Frame(parent, bg="#11273f"); pb_fr.pack(fill="x")
        ttk.Label(pb_fr, text="Progression WAZ:", width=18, anchor="e").pack(side="left")
        self.aw_waz_pb = ttk.Progressbar(pb_fr, maximum=40, bootstyle="info-striped", length=400)
        self.aw_waz_pb.pack(side="left", padx=8)
        self.aw_waz_lbl = ttk.Label(pb_fr, text="0 / 40", foreground="white"); self.aw_waz_lbl.pack(side="left")

        cols = ("Zone CQ","Statut","Entités travaillées dans cette zone")
        self.tree_waz = ttk.Treeview(parent, columns=cols, show='headings', style="Custom.Treeview")
        self.tree_waz.heading("Zone CQ", text="Zone CQ"); self.tree_waz.column("Zone CQ", width=80, anchor="center")
        self.tree_waz.heading("Statut", text="Statut"); self.tree_waz.column("Statut", width=100, anchor="center")
        self.tree_waz.heading("Entités travaillées dans cette zone", text="Entités travaillées")
        self.tree_waz.column("Entités travaillées dans cette zone", width=500, anchor="w")
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_waz.yview)
        self.tree_waz.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree_waz.pack(fill="both", expand=True, padx=5, pady=5)
        self.tree_waz.tag_configure('done', background='#1a4a1a', foreground='#58d68d')
        self.tree_waz.tag_configure('miss', background='#4a1a1a', foreground='#e74c3c')

    def _build_award_was(self, parent):
        info_fr = tk.Frame(parent, bg="#11273f"); info_fr.pack(fill="x")
        self.aw_was_var = tk.StringVar(value="Calcul en cours...")
        ttk.Label(info_fr, textvariable=self.aw_was_var,
                  font=("Impact",16), foreground="#e74c3c").pack(side="left")
        pb_fr = tk.Frame(parent, bg="#11273f"); pb_fr.pack(fill="x")
        ttk.Label(pb_fr, text="Progression WAS:", width=18, anchor="e").pack(side="left")
        self.aw_was_pb = ttk.Progressbar(pb_fr, maximum=50, bootstyle="danger-striped", length=400)
        self.aw_was_pb.pack(side="left", padx=8)
        self.aw_was_lbl = ttk.Label(pb_fr, text="0 / 50", foreground="white"); self.aw_was_lbl.pack(side="left")
        ttk.Label(parent, text="Note: WAS se base sur le champ QTH des QSOs avec stations K/W/N/AA-AK",
                  foreground="gray", font=("Arial",9)).pack(padx=10, anchor="w")

        # Grille 5x10 des états
        grid_fr = tk.Frame(parent, bg="#11273f"); grid_fr.pack(fill="x", padx=10)
        self._was_state_labels = {}
        for i, state in enumerate(self.USA_STATES):
            row, col = divmod(i, 10)
            lbl = ttk.Label(grid_fr, text=state[:8], width=10, anchor="center",
                            font=("Arial",8), relief="ridge", padding=2)
            lbl.grid(row=row, column=col, padx=1, pady=1)
            self._was_state_labels[state] = lbl

    def _build_award_iota(self, parent):
        info_fr = tk.Frame(parent, bg="#11273f"); info_fr.pack(fill="x")
        self.aw_iota_var = tk.StringVar(value="Calcul en cours...")
        ttk.Label(info_fr, textvariable=self.aw_iota_var,
                  font=("Impact",16), foreground="#9b59b6").pack(side="left")
        pb_fr = tk.Frame(parent, bg="#11273f"); pb_fr.pack(fill="x")
        ttk.Label(pb_fr, text="Groupes IOTA détectés:", width=20, anchor="e").pack(side="left")
        self.aw_iota_pb = ttk.Progressbar(pb_fr, maximum=len(self.IOTA_GROUPS),
                                            bootstyle="warning-striped", length=350)
        self.aw_iota_pb.pack(side="left", padx=8)
        self.aw_iota_lbl = ttk.Label(pb_fr, text=f"0 / {len(self.IOTA_GROUPS)}", foreground="white")
        self.aw_iota_lbl.pack(side="left")
        ttk.Label(parent, text="Basé sur les commentaires de vos QSOs contenant un référence IOTA (ex: EU-005)",
                  foreground="gray", font=("Arial",9)).pack(padx=10, anchor="w")

        cols = ("Ref. IOTA","Île / Archipel","Travaillé")
        self.tree_iota = ttk.Treeview(parent, columns=cols, show='headings', style="Custom.Treeview")
        self.tree_iota.heading("Ref. IOTA",text="Ref. IOTA"); self.tree_iota.column("Ref. IOTA",width=90,anchor="center")
        self.tree_iota.heading("Île / Archipel",text="Île / Archipel"); self.tree_iota.column("Île / Archipel",width=200,anchor="w")
        self.tree_iota.heading("Travaillé",text="Travaillé"); self.tree_iota.column("Travaillé",width=100,anchor="center")
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_iota.yview)
        self.tree_iota.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree_iota.pack(fill="both", expand=True, padx=5, pady=5)
        self.tree_iota.tag_configure('done', background='#1a4a1a', foreground='#58d68d')
        self.tree_iota.tag_configure('miss', background='#11273f', foreground='#888')

    def _refresh_all_awards(self):
        threading.Thread(target=self._calc_awards, daemon=True).start()

    def _calc_awards(self):
        c = self.conn.cursor()
        rows = c.execute("SELECT callsign, band, mode, qso_date, lotw_stat, qth, comment FROM qsos").fetchall()

        # --- DXCC ---
        dxcc_worked = {}
        dxcc_confirmed = set()
        for call, band, mode, date, lotw, qth, comment in rows:
            entity = get_country_name(call)
            if not entity: continue
            if entity not in dxcc_worked: dxcc_worked[entity] = 0
            dxcc_worked[entity] += 1
            if lotw and lotw.upper() in ("OK","YES","Y","LOTW"):
                dxcc_confirmed.add(entity)
        # Charger confirmations DB
        for row in c.execute("SELECT entity FROM dxcc_confirmed WHERE confirmed=1"):
            dxcc_confirmed.add(row[0])
        total_dxcc = len(dxcc_worked)
        total_conf = len(dxcc_confirmed)

        # --- WAZ ---
        waz_worked = {}
        for call, *_ in rows:
            entity = get_country_name(call)
            zone = self.WAZ_ZONES.get(entity)
            if zone:
                if zone not in waz_worked: waz_worked[zone] = []
                if entity not in waz_worked[zone]: waz_worked[zone].append(entity)
        total_waz = len(waz_worked)

        # --- WAS ---
        was_worked = set()
        for call, band, mode, date, lotw, qth, comment in rows:
            if call and call[0].upper() in ('K','W','N'):
                for state in self.USA_STATES:
                    if qth and state.upper() in qth.upper():
                        was_worked.add(state)
        total_was = len(was_worked)

        # --- IOTA ---
        iota_comments = set()
        for call, band, mode, date, lotw, qth, comment in rows:
            if comment:
                m = re.search(r'([A-Z]{2}-\d{3})', comment.upper())
                if m: iota_comments.add(m.group(1))
        total_iota = sum(1 for ref in self.IOTA_GROUPS if ref in iota_comments)

        self.root.after(0, lambda: self._update_awards_ui(
            dxcc_worked, dxcc_confirmed, total_dxcc, total_conf,
            waz_worked, total_waz,
            was_worked, total_was,
            iota_comments, total_iota
        ))

    def _update_awards_ui(self, dxcc_worked, dxcc_confirmed, total_dxcc, total_conf,
                           waz_worked, total_waz, was_worked, total_was, iota_comments, total_iota):
        # DXCC
        self.aw_dxcc_var.set(
            f"DXCC : {total_dxcc} entités travaillées  |  {total_conf} confirmées"
            + ("  🏆 DXCC Award !" if total_dxcc >= 100 else f"  ({100-total_dxcc} restantes pour DXCC 100)")
        )
        for threshold, (pb, lbl) in self.aw_dxcc_bars.items():
            pb['value'] = min(total_dxcc, threshold)
            lbl.config(text=f"{min(total_dxcc, threshold)} / {threshold}"
                       + (" ✅" if total_dxcc >= threshold else ""))
        for item in self.tree_aw_dxcc.get_children(): self.tree_aw_dxcc.delete(item)
        for entity, count in sorted(dxcc_worked.items()):
            conf = "✅ Oui" if entity in dxcc_confirmed else "—"
            tag = 'conf' if entity in dxcc_confirmed else 'worked'
            self.tree_aw_dxcc.insert("", "end", values=(entity, count, conf), tags=(tag,))

        # WAZ
        self.aw_waz_var.set(
            f"WAZ : {total_waz} / 40 zones"
            + ("  🏆 WAZ Award !" if total_waz >= 40 else f"  ({40-total_waz} zones manquantes)")
        )
        self.aw_waz_pb['value'] = total_waz
        self.aw_waz_lbl.config(text=f"{total_waz} / 40" + (" ✅" if total_waz >= 40 else ""))
        for item in self.tree_waz.get_children(): self.tree_waz.delete(item)
        for zone in range(1, 41):
            entities = waz_worked.get(zone, [])
            tag = 'done' if entities else 'miss'
            status = "✅ Travaillé" if entities else "❌ Manquant"
            self.tree_waz.insert("", "end", values=(
                f"Zone {zone:02d}", status, ", ".join(entities) if entities else "—"
            ), tags=(tag,))

        # WAS
        self.aw_was_var.set(
            f"WAS : {total_was} / 50 états"
            + ("  🏆 WAS Award !" if total_was >= 50 else f"  ({50-total_was} états manquants)")
        )
        self.aw_was_pb['value'] = total_was
        self.aw_was_lbl.config(text=f"{total_was} / 50" + (" ✅" if total_was >= 50 else ""))
        for state, lbl in self._was_state_labels.items():
            if state in was_worked:
                lbl.config(background="#1a5e20", foreground="#58d68d")
            else:
                lbl.config(background="#4a1a1a", foreground="#aaa")

        # IOTA
        self.aw_iota_var.set(f"IOTA : {total_iota} / {len(self.IOTA_GROUPS)} groupes référencés détectés dans les commentaires")
        self.aw_iota_pb['value'] = total_iota
        self.aw_iota_lbl.config(text=f"{total_iota} / {len(self.IOTA_GROUPS)}")
        for item in self.tree_iota.get_children(): self.tree_iota.delete(item)
        for ref, name in sorted(self.IOTA_GROUPS.items()):
            done = ref in iota_comments
            tag = 'done' if done else 'miss'
            self.tree_iota.insert("", "end", values=(
                ref, name, "✅ Oui" if done else "—"
            ), tags=(tag,))

    # ==========================================
    # --- 4. MÉMOIRES FRÉQUENCES ---
    # ==========================================

    # Mémoires par défaut
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

    def _build_memories_tab(self, parent):
        # Créer la table mémoires si nécessaire
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

        # Grille de boutons mémoires
        self.mem_btn_frame = tk.Frame(parent, bg="#11273f"); self.mem_btn_frame.pack(fill="x")
        ttk.Label(self.mem_btn_frame, text="⚡ Clic = accord le transceiver via CAT :",
                  font=("Arial",9), foreground="#aaa").pack(anchor="w", pady=(0,5))
        self.mem_buttons_grid = ttk.Frame(self.mem_btn_frame)
        self.mem_buttons_grid.pack(fill="x")

        # Tableau des mémoires
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
        # Nettoyer boutons
        for w in self.mem_buttons_grid.winfo_children(): w.destroy()
        for item in self.tree_mem.get_children(): self.tree_mem.delete(item)

        rows = self.conn.cursor().execute(
            "SELECT id, freq, label, band, mode FROM freq_memories ORDER BY sort_order, id").fetchall()

        # Couleurs par mode
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
            # En-tête bande
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

            # Tableau
        for mem_id, freq, label, band, mode in rows:
            self.tree_mem.insert("", "end", values=(mem_id, freq, label, band, mode))

    def _tune_to(self, freq_mhz, mode):
        """Accorde le transceiver via CAT sur la fréquence mémoire."""
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
            tqsl_path = CONF.get('LOTW','Tqsl_Path','') if CONF else ''
            if tqsl_path and os.path.exists(tqsl_path):
                if messagebox.askyesno("LoTW Export", msg + f"Ouvrir TQSL maintenant ?\n({tqsl_path})"):
                    import subprocess
                    subprocess.Popen([tqsl_path, fn])
            else:
                messagebox.showinfo("LoTW Export", msg)

            self.status_var.set(f"📤 LoTW ADIF : {exported} QSOs exportés → {os.path.basename(fn)}")
        except Exception as e:
            messagebox.showerror("Erreur export LoTW", str(e))


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
        self.heatmap_info_var = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self.heatmap_info_var, foreground="#f39c12").pack(side="right", padx=10)
        self._heatmap_frame = tk.Frame(parent, bg="#11273f"); self._heatmap_frame.pack(fill="both", expand=True)
        self.root.after(1200, self._draw_heatmap)

    def _draw_heatmap(self):
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.patches as mpatches
            import matplotlib.cm as cm
            import numpy as np
        except ImportError:
            for w in self._heatmap_frame.winfo_children(): w.destroy()
            ttk.Label(self._heatmap_frame,
                      text="⚠️ matplotlib / numpy requis\npip install matplotlib numpy",
                      font=("Arial",13), justify="center").pack(expand=True)
            return

        for w in self._heatmap_frame.winfo_children(): w.destroy()
        c = self.conn.cursor()
        rows = c.execute("SELECT callsign, grid FROM qsos WHERE grid != ''").fetchall()
        mode = self.heatmap_mode_var.get()

        fig = Figure(figsize=(12, 6), dpi=95, facecolor='#0a1628')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#0d2240')   # bleu océan bien visible
        ax.set_xlim(-180, 182); ax.set_ylim(-90, 90)
        ax.set_xlabel("Longitude", color='#8ab0d0', fontsize=9)
        ax.set_ylabel("Latitude", color='#8ab0d0', fontsize=9)
        ax.tick_params(colors='#8ab0d0', labelsize=7)
        for sp in ax.spines.values(): sp.set_edgecolor('#2a5080')

        # ---- Fond carte : polygones continents détaillés ----
        # Format : liste de polygones (lon, lat) formant les contours continentaux
        # Europe
        europe = [(-10,36),(-9,39),(-9,44),(-5,44),(-2,44),(0,46),(2,47),(3,50),
                  (2,51),(3,53),(5,53),(8,55),(10,56),(12,56),(15,57),(18,58),
                  (20,60),(25,60),(28,62),(30,65),(28,68),(26,70),(30,71),(32,70),
                  (28,68),(32,65),(30,62),(30,58),(28,56),(25,54),(22,55),(18,55),
                  (15,54),(12,54),(10,55),(8,54),(5,52),(4,51),(2,51),(0,49),
                  (-2,47),(-5,44),(-8,44),(-10,38),(-10,36)]
        # Amérique du Nord
        n_america = [(-168,72),(-140,72),(-130,70),(-120,68),(-100,72),(-80,70),
                     (-70,63),(-65,60),(-60,47),(-67,45),(-70,43),(-75,40),
                     (-75,35),(-80,30),(-82,25),(-90,20),(-87,16),(-83,10),
                     (-78,8),(-75,10),(-78,15),(-88,16),(-92,18),(-97,20),
                     (-105,22),(-108,25),(-110,28),(-117,32),(-120,34),
                     (-125,38),(-124,42),(-124,47),(-123,50),(-130,55),
                     (-138,58),(-145,62),(-152,60),(-158,58),(-162,62),
                     (-165,65),(-168,68),(-168,72)]
        # Amérique du Sud
        s_america = [(-78,8),(-75,10),(-65,10),(-62,12),(-60,8),(-52,4),
                     (-50,0),(-48,-2),(-44,-4),(-38,-8),(-35,-8),(-35,-12),
                     (-38,-15),(-40,-20),(-42,-22),(-44,-23),(-46,-24),
                     (-48,-26),(-50,-28),(-52,-32),(-53,-34),(-58,-34),
                     (-60,-38),(-62,-42),(-65,-45),(-66,-50),(-68,-52),
                     (-68,-55),(-65,-55),(-68,-52),(-72,-48),(-72,-45),
                     (-70,-40),(-72,-35),(-70,-30),(-70,-25),(-72,-20),
                     (-75,-15),(-77,-12),(-78,-5),(-78,0),(-78,5),(-78,8)]
        # Afrique
        africa = [(-6,36),(-5,36),(0,37),(5,37),(10,37),(12,36),(15,38),
                  (18,36),(25,34),(32,30),(35,28),(38,22),(42,12),(44,12),
                  (42,10),(40,5),(38,0),(40,-5),(38,-10),(35,-18),(32,-22),
                  (28,-25),(25,-28),(20,-35),(18,-35),(15,-30),(12,-28),
                  (10,-22),(8,-18),(5,-12),(2,-5),(2,0),(0,5),(2,8),
                  (0,12),(-2,14),(-5,16),(-8,18),(-12,20),(-15,22),
                  (-17,24),(-17,28),(-14,30),(-10,32),(-8,34),(-6,36)]
        # Asie (simplifié)
        asia = [(26,42),(30,42),(35,38),(38,38),(40,36),(42,38),(45,42),
                (48,44),(52,48),(55,52),(60,55),(65,58),(70,60),(75,62),
                (80,64),(85,68),(90,72),(95,72),(100,70),(105,72),(110,70),
                (120,68),(130,65),(135,60),(140,55),(145,48),(142,46),
                (138,42),(134,38),(130,35),(128,35),(126,38),(122,38),
                (118,36),(115,32),(112,28),(110,24),(108,20),(105,16),
                (104,12),(102,2),(100,2),(98,5),(98,10),(96,18),(94,22),
                (90,22),(88,28),(84,28),(80,32),(75,35),(70,38),(65,35),
                (60,32),(55,28),(52,24),(50,18),(48,12),(44,12),(42,14),
                (40,18),(38,22),(36,28),(34,32),(32,36),(28,38),(26,40),(26,42)]
        # Australie
        australia = [(114,-22),(116,-20),(118,-18),(122,-18),(126,-18),
                     (128,-14),(130,-12),(132,-12),(136,-12),(138,-14),
                     (140,-18),(142,-20),(144,-24),(146,-26),(148,-28),
                     (150,-30),(152,-28),(154,-24),(152,-22),(150,-20),
                     (148,-20),(150,-22),(152,-26),(152,-30),(150,-34),
                     (148,-38),(146,-39),(144,-38),(142,-38),(140,-36),
                     (138,-34),(136,-32),(134,-32),(132,-34),(130,-34),
                     (128,-34),(126,-32),(124,-28),(122,-24),(118,-22),(114,-22)]

        # Couleur de terre bien visible sur fond sombre
        land_color   = '#2c4a2e'   # vert foncé — continents
        border_color = '#5aaa60'   # vert clair vif — frontières côtières
        for poly_pts in [europe, n_america, s_america, africa, asia, australia]:
            xs = [p[0] for p in poly_pts]
            ys = [p[1] for p in poly_pts]
            ax.fill(xs, ys, color=land_color, alpha=1.0, zorder=1)
            ax.plot(xs + [xs[0]], ys + [ys[0]],
                    color=border_color, linewidth=1.2, alpha=1.0, zorder=2)

        # Grille géographique
        for lon in range(-180, 181, 30):
            ax.axvline(lon, color='#1e3a5f', linewidth=0.4, alpha=0.5, zorder=1)
        for lat in range(-90, 91, 30):
            ax.axhline(lat, color='#1e3a5f', linewidth=0.4, alpha=0.5, zorder=1)
        # Équateur et tropiques
        ax.axhline(0,   color='#4a9a5a', linewidth=1.0, alpha=0.7, linestyle='--', zorder=2)
        ax.axhline(23.5,  color='#8a8a3a', linewidth=0.6, alpha=0.5, linestyle=':', zorder=2)
        ax.axhline(-23.5, color='#8a8a3a', linewidth=0.6, alpha=0.5, linestyle=':', zorder=2)
        # Légende équateur
        ax.text(182, 1, 'Éq.', color='#4a9a5a', fontsize=6, va='bottom')
        ax.text(182, 24.5, 'Tr.C.', color='#8a8a3a', fontsize=6, va='bottom')
        ax.text(182, -22.5, 'Tr.C.', color='#8a8a3a', fontsize=6, va='bottom')

        # Ligne de ma station
        home = grid_to_latlon(MY_GRID)
        if home:
            ax.plot(home[1], home[0], '*', color='#f39c12', markersize=14, zorder=10)
            ax.annotate(MY_CALL, (home[1], home[0]), color='#f39c12',
                        fontsize=7, xytext=(5,5), textcoords='offset points')

        # Points QSOs
        points = {}
        for call, grid in rows:
            pos = grid_to_latlon(grid)
            if not pos: continue
            lat, lon = pos
            entity = get_country_name(call) or "?"
            key = (round(lon,0), round(lat,0))
            if key not in points: points[key] = {'count':0,'entity':entity,'call':call}
            points[key]['count'] += 1

        if mode == "Densité QSOs":
            max_c = max((v['count'] for v in points.values()), default=1)
            colormap = cm.get_cmap('YlOrRd')
            for (lon,lat), data in points.items():
                color = colormap(data['count']/max_c)
                size = 20 + (data['count']/max_c)*80
                ax.scatter(lon, lat, s=size, color=color, alpha=0.7, zorder=5, linewidths=0)
        elif mode == "Continents":
            cont_colors = {"EU":"#3498db","AS":"#e74c3c","NA":"#2ecc71","SA":"#f39c12",
                          "AF":"#9b59b6","OC":"#1abc9c","AN":"#aaa"}
            for (lon,lat), data in points.items():
                entity = data['entity']
                cont = "EU"
                for pfx,ent,c_code,_,__ in self.DXCC_DATA:
                    if ent == entity: cont = c_code; break
                color = cont_colors.get(cont, '#aaa')
                ax.scatter(lon, lat, s=35, color=color, alpha=0.8, zorder=5, linewidths=0)
            for cont, color in cont_colors.items():
                ax.scatter([],[], s=40, color=color, label=self.CONTINENT_NAMES.get(cont,cont))
            ax.legend(loc='lower left', facecolor='#11273f', labelcolor='white', fontsize=7)
        else:  # Entités DXCC
            colors = ['#3498db','#e74c3c','#2ecc71','#f39c12','#9b59b6','#1abc9c',
                      '#e67e22','#e91e63','#00bcd4','#8bc34a','#ff5722','#607d8b']
            entities = list({d['entity'] for d in points.values()})
            ent_color = {e: colors[i % len(colors)] for i,e in enumerate(entities)}
            for (lon,lat), data in points.items():
                ax.scatter(lon, lat, s=30, color=ent_color.get(data['entity'],'#aaa'),
                          alpha=0.8, zorder=5, linewidths=0)

        # Lignes depuis station vers QSOs (short path, filtrées)
        if home and len(points) < 300:
            for (lon,lat), data in list(points.items())[:200]:
                ax.plot([home[1], lon], [home[0], lat],
                        color='#2ecc71', alpha=0.05, linewidth=0.4, zorder=3)

        total_pts = len(points)
        total_qsos = sum(v['count'] for v in points.values())
        ax.set_title(
            f"Heatmap QSOs — {MY_CALL}  |  {total_qsos} QSOs  |  {total_pts} locators  |  Mode: {mode}",
            color='#f39c12', fontsize=11)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self._heatmap_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.heatmap_info_var.set(f"{total_qsos} QSOs • {total_pts} locators uniques • {len({d['entity'] for d in points.values()})} entités")

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
                  font=("Impact",24), foreground="#3498db").pack()
        # Stats QSOs
        stats_f = tk.Frame(center, bg="#11273f"); stats_f.pack(side="left", padx=20)
        self.contest_qsos_var = tk.StringVar(value="0")
        self.contest_rate_var = tk.StringVar(value="0")
        self.contest_rate1h_var = tk.StringVar(value="0")
        ttk.Label(stats_f, text="QSOs CONTEST", font=("Arial",9), foreground="#888").pack()
        ttk.Label(stats_f, textvariable=self.contest_qsos_var,
                  font=("Impact",42), foreground="#2ecc71").pack()
        rate_f = tk.Frame(stats_f, bg="#11273f"); rate_f.pack()
        ttk.Label(rate_f, text="Rate /h:", foreground="#aaa", font=("Consolas",10)).pack(side="left")
        ttk.Label(rate_f, textvariable=self.contest_rate_var,
                  font=("Consolas",10,"bold"), foreground="#2ecc71").pack(side="left", padx=5)
        ttk.Label(rate_f, text="  Dernière heure:", foreground="#aaa", font=("Consolas",10)).pack(side="left")
        ttk.Label(rate_f, textvariable=self.contest_rate1h_var,
                  font=("Consolas",10,"bold"), foreground="#3498db").pack(side="left", padx=5)
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
        self._qsl_canvas = tk.Canvas(self._qsl_canvas_frame, bg="#11273f", width=720, height=400)
        self._qsl_canvas.pack(expand=True)
        self._qsl_fig = None
        self._draw_qsl_card_preview()

    def _get_selected_qso(self):
        sel = self.tree.selection()
        if not sel: return None
        v = self.tree.item(sel[0])['values']
        return {'id':v[0],'country':v[1],'date':v[2],'time':v[3],'call':v[4],
                'name':v[5],'qth':v[6],'band':v[7],'mode':v[8],
                'rst_s':v[9],'rst_r':v[10],'dist':v[11]}

    def _draw_qsl_card_preview(self, qso=None):
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.patches as mpatches
        except ImportError:
            return

        for w in self._qsl_canvas_frame.winfo_children(): w.destroy()

        themes = {
            "Classique": {"bg":"#0d2a0d","header":"#2ecc71","text":"white","accent":"#f39c12","border":"#2ecc71"},
            "Nuit DX":   {"bg":"#11273f","header":"#3498db","text":"white","accent":"#f39c12","border":"#3498db"},
            "Vintage":   {"bg":"#3d2b1f","header":"#c0874a","text":"#f5e6c8","accent":"#e8b86d","border":"#c0874a"},
            "Contest":   {"bg":"#1a0a2a","header":"#e74c3c","text":"white","accent":"#f39c12","border":"#e74c3c"},
        }
        theme = themes.get(self.qsl_theme_var.get(), themes["Classique"])

        fig = Figure(figsize=(7.2, 3.8), dpi=100)
        fig.patch.set_facecolor(theme['bg'])
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0,720); ax.set_ylim(0,380); ax.axis('off')
        ax.set_facecolor(theme['bg'])

        # Bordure
        for lw, alpha in [(8,0.3),(4,0.6),(2,1.0)]:
            rect = mpatches.FancyBboxPatch((5,5),710,370, boxstyle="round,pad=3",
                edgecolor=theme['border'], facecolor='none', linewidth=lw, alpha=alpha)
            ax.add_patch(rect)

        # Bande décorative haute
        ax.add_patch(mpatches.Rectangle((5,330),710,45, facecolor=theme['header'], alpha=0.85))

        # Indicatif principal
        ax.text(360, 357, MY_CALL, ha='center', va='center',
                fontsize=28, fontweight='bold', color='white',
                fontfamily='monospace')

        # Locator et QTH
        ax.text(20, 315, f"📍 {self.qsl_qth_var.get()}  |  {MY_GRID}",
                fontsize=11, color=theme['accent'], va='top')

        # Info QSO
        if qso:
            ax.text(20, 280, "CONFIRMING QSO WITH:", fontsize=9, color='#aaa', va='top')
            ax.text(20, 258, str(qso['call']), fontsize=22, fontweight='bold',
                    color=theme['accent'], va='top', fontfamily='monospace')
            if qso['name']: ax.text(220, 262, str(qso['name']), fontsize=12, color='white', va='top')
            if qso['country']: ax.text(220, 242, str(qso['country']), fontsize=10, color='#aaa', va='top')
            # Tableau données
            data = [("Date", str(qso['date'])),("UTC", str(qso['time'])),
                    ("Band", str(qso['band'])),("Mode", str(qso['mode'])),
                    ("RST →", str(qso['rst_s'])),("RST ←", str(qso['rst_r']))]
            for i,(label,val) in enumerate(data):
                x = 20 + (i%3)*230; y = 195 - (i//3)*38
                ax.add_patch(mpatches.FancyBboxPatch((x,y),180,32,
                    boxstyle="round,pad=2", facecolor=theme['header'], alpha=0.3,
                    edgecolor=theme['border'], linewidth=0.8))
                ax.text(x+8, y+22, label, fontsize=8, color='#aaa', va='top')
                ax.text(x+8, y+7, val, fontsize=10, fontweight='bold', color='white', va='top')
            if qso['dist']: ax.text(710, 195, f"📡 {qso['dist']} km", fontsize=9,
                                     color=theme['accent'], ha='right', va='top')
        else:
            ax.text(360, 260, "← Sélectionnez un QSO dans le Journal", ha='center',
                    fontsize=13, color='#aaa', style='italic')
            ax.text(360, 220, "Aperçu de la carte QSL", ha='center',
                    fontsize=11, color='#555')

        # Message bas
        ax.text(360, 90, self.qsl_msg_var.get(), ha='center', fontsize=10,
                color=theme['text'], style='italic')
        # Ligne décorative
        ax.plot([30,690],[75,75], color=theme['border'], linewidth=1, alpha=0.5)
        # Signature et date
        ax.text(20, 55, f"73 de {MY_CALL}", fontsize=10, color=theme['accent'])
        ax.text(710, 55, datetime.now().strftime("%Y"), fontsize=10,
                color='#aaa', ha='right')

        self._qsl_fig = fig
        canvas = FigureCanvasTkAgg(fig, master=self._qsl_canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True)

    def _generate_qsl_card(self):
        qso = self._get_selected_qso()
        if not qso:
            messagebox.showinfo("QSL Card","Sélectionnez d'abord un QSO dans l'onglet Journal.")
            return
        self._draw_qsl_card_preview(qso)

    def _save_qsl_card(self):
        if not self._qsl_fig:
            messagebox.showinfo("QSL","Générez d'abord une carte."); return
        fn = filedialog.asksaveasfilename(defaultextension=".png",
            filetypes=[("PNG","*.png"),("PDF","*.pdf")],
            title="Enregistrer la QSL Card")
        if fn:
            self._qsl_fig.savefig(fn, dpi=150, bbox_inches='tight',
                                   facecolor=self._qsl_fig.get_facecolor())
            messagebox.showinfo("QSL Card",f"Carte enregistrée :\n{fn}")
            self.status_var.set(f"🖨️ QSL Card sauvegardée : {os.path.basename(fn)}")

    def _print_qsl_card(self):
        if not self._qsl_fig:
            messagebox.showinfo("QSL","Générez d'abord une carte."); return
        import tempfile, subprocess
        tmp = tempfile.mktemp(suffix=".pdf")
        self._qsl_fig.savefig(tmp, dpi=150, bbox_inches='tight')
        try:
            if os.name == 'nt':
                os.startfile(tmp, "print")
            else:
                subprocess.Popen(["lpr", tmp])
            self.status_var.set("🖨️ QSL Card envoyée à l'imprimante")
        except Exception as e:
            messagebox.showinfo("Impression",f"Fichier PDF créé :\n{tmp}\nOuvrez-le et imprimez manuellement.")

    # ==========================================
    # --- WIKI / AIDE ---
    # ==========================================
    def _build_wiki_tab(self, parent):
        # Notebook interne pour les sections
        nb_wiki = ttk.Notebook(parent, bootstyle="info")
        nb_wiki.pack(fill="both", expand=True, padx=5, pady=5)

        sections = {
            "🚀 Démarrage rapide": self._wiki_quickstart(),
            "🏠 Dashboard": self._wiki_dashboard(),
            "📖 Journal": self._wiki_journal(),
            "🌍 Carte & DX Cluster": self._wiki_cluster(),
            "🏆 DXCC & Awards": self._wiki_awards(),
            "📊 Graphiques & Stats": self._wiki_graphs(),
            "🌐 Propagation": self._wiki_propagation(),
            "📻 PSK Reporter": self._wiki_psk(),
            "🖨️ QSL & LoTW": self._wiki_qsl(),
            "📻 Mémoires & CAT": self._wiki_cat(),
            "⚙️ Configuration": self._wiki_config(),
            "🔧 Dépannage": self._wiki_troubleshoot(),
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
            txt.tag_configure("h2", font=("Arial",12,"bold"), foreground="#3498db", spacing1=6, spacing3=2)
            txt.tag_configure("h3", font=("Arial",10,"bold"), foreground="#2ecc71", spacing1=4)
            txt.tag_configure("code", font=("Consolas",9), foreground="#e67e22", background="#11273f")
            txt.tag_configure("tip",  font=("Arial",9,"italic"), foreground="#f39c12")
            txt.tag_configure("warn", font=("Arial",9,"bold"), foreground="#e74c3c")
            txt.tag_configure("ok",   font=("Arial",9), foreground="#2ecc71")
            for line in content:
                tag, text = line
                txt.insert("end", text + "\n", tag)
            txt.config(state="disabled")

    def _wiki_quickstart(self):
        return [
            ("h1","  Station Master — Guide de démarrage rapide"),
            ("",  ""),
            ("h2","  Prérequis Python"),
            ("code","  pip install ttkbootstrap tkintermapview requests pyserial matplotlib numpy"),
            ("",  ""),
            ("h2","  Premier lancement"),
            ("ok","  ✅ 1. Lancez mon_logbook.py — un fichier config.ini est créé automatiquement"),
            ("ok","  ✅ 2. Cliquez ⚙️ Paramètres → onglet 🏠 Station"),
            ("ok","  ✅ 3. Entrez votre indicatif (ex: ON5AM) et votre locator (ex: JO20SP)"),
            ("ok","  ✅ 4. Configurez votre port CAT si vous utilisez un transceiver"),
            ("ok","  ✅ 5. Enregistrez et redémarrez"),
            ("",  ""),
            ("h2","  Saisir votre premier QSO"),
            ("",  "  • Tapez l'indicatif dans le champ en haut à gauche"),
            ("",  "  • L'indicateur en dessous vous dit immédiatement si c'est un doublon"),
            ("",  "  • Cliquez 🔍 pour chercher les infos sur QRZ.com (clé API requise)"),
            ("",  "  • Remplissez Mode, RST, Commentaire puis 💾 SAVE"),
            ("",  ""),
            ("h2","  Import d'un logbook existant"),
            ("",  "  Bouton 📂 Import en haut → sélectionnez votre fichier .adi ou .adif"),
            ("tip","  💡 Tous les formats ADIF standards sont supportés (WSJT-X, Log4OM, DXKeeper...)"),
        ]

    def _wiki_journal(self):
        return [
            ("h1","  📖 Onglet Journal"),
            ("",""),
            ("h2","  Navigation"),
            ("","  • Double-clic sur un QSO → édition complète"),
            ("","  • Clic droit → menu contextuel (supprimer, marquer, exporter)"),
            ("","  • Ctrl+A → sélectionner tout"),
            ("","  • Clic sur un QSO → affichage automatique sur la carte + fiche QRZ"),
            ("",""),
            ("h2","  Filtres"),
            ("","  Utilisez la zone Recherche à droite pour filtrer par :"),
            ("","  • Indicatif (partiel ou complet)"),
            ("","  • Bande : liste déroulante Bande"),
            ("","  • Mode : liste déroulante Mode"),
            ("","  • Bouton X : réinitialiser tous les filtres"),
            ("",""),
            ("h2","  Colonnes du tableau"),
            ("","  ID | Pays | Date | Heure UTC | Callsign | Nom | QTH | Bande | Mode"),
            ("","  RS envoyé | RS reçu | Distance km | Azimut | Statuts QSL | Commentaire"),
            ("",""),
            ("h2","  Raccourcis clavier"),
            ("code","  Double-clic  = Éditer le QSO"),
            ("code","  Ctrl+A       = Tout sélectionner"),
            ("code","  Clic droit   = Menu contextuel"),
            ("",""),
            ("h2","  Alerte doublon"),
            ("","  Dès que vous tapez un indicatif :"),
            ("ok","  🟢 Vert   = Premier QSO avec cette station"),
            ("tip","  🟡 Orange = Déjà travaillé sur d'autres bandes — nouvelle bande possible !"),
            ("warn","  🔴 Rouge  = Doublon exact sur la bande actuelle"),
        ]

    def _wiki_cluster(self):
        return [
            ("h1","  📡 DX Cluster & Carte Live"),
            ("",""),
            ("h2","  DX Cluster"),
            ("","  Connexion automatique au serveur configuré dans ⚙️ → DX Cluster"),
            ("","  Serveur par défaut : on0dxk.dyndns.org:8000"),
            ("",""),
            ("h2","  Filtres cluster"),
            ("","  • Bande   : affiche uniquement les spots sur la bande sélectionnée"),
            ("","  • Pays    : filtre par nom de pays (ex: Japan)"),
            ("","  • Appel   : filtre par préfixe ou indicatif partiel"),
            ("","  • 🔔 Alerte sonore : bip si un spot correspond aux alertes configurées"),
            ("",""),
            ("h2","  Code couleur des spots"),
            ("ok","  🟦 Bleu foncé  = Nouveau DXCC (jamais travaillé dans votre log)"),
            ("warn","  🟥 Rouge       = Correspond à vos alertes bande/pays configurées"),
            ("","  ⬜ Normal      = Spot standard"),
            ("",""),
            ("h2","  Double-clic sur un spot"),
            ("","  → Accorde le transceiver via CAT sur la fréquence du spot"),
            ("",""),
            ("h2","  Configurer les alertes"),
            ("","  Bouton ⚙️ Config alertes → entrez les bandes et pays à surveiller"),
            ("code","  Exemple bandes  : 20m,15m,10m"),
            ("code","  Exemple pays    : Japan,USA,Australia,China"),
            ("",""),
            ("h2","  Carte Live"),
            ("","  • Cliquez sur un QSO dans le Journal → le DX apparaît sur la carte"),
            ("","  • Une ligne rouge relie votre station au DX (short path)"),
            ("","  • Fond : OpenStreetMap (connexion internet requise)"),
            ("","  • Votre station est marquée 🏠 au démarrage"),
        ]

    def _wiki_awards(self):
        return [
            ("h1","  🏆 DXCC & Awards"),
            ("",""),
            ("h2","  Onglet DXCC"),
            ("","  • Bouton 🔄 Calculer → analyse tous vos QSOs et groupe par entité DXCC"),
            ("","  • Filtre bande : voir le DXCC par bande spécifique"),
            ("","  • Double-clic → ajouter des notes sur une entité"),
            ("ok","  ✅ Vert = entité confirmée (LoTW ou marquée manuellement)"),
            ("","  📡 Normal = travaillé mais pas encore confirmé"),
            ("",""),
            ("h2","  Marquer comme confirmé"),
            ("","  Sélectionnez une ou plusieurs entités → bouton ✅ Marquer comme CONFIRMÉ"),
            ("","  Les confirmations sont stockées dans la base de données SQLite"),
            ("",""),
            ("h2","  Onglet Awards → DXCC"),
            ("","  4 barres de progression : DXCC 100 / 200 / 300 / Honor Roll (340+)"),
            ("",""),
            ("h2","  WAZ — Worked All Zones"),
            ("","  40 zones CQ. Vert = travaillé, Rouge = manquant"),
            ("tip","  💡 Basé sur le mapping entité → zone CQ intégré au logiciel"),
            ("",""),
            ("h2","  WAS — Worked All States"),
            ("","  50 états USA. Basé sur le champ QTH des QSOs avec stations K/W/N"),
            ("","  La grille visuelle colorie les états travaillés en vert"),
            ("",""),
            ("h2","  IOTA"),
            ("","  Détection automatique des références dans les commentaires de QSOs"),
            ("code","  Exemple : commentaire contenant EU-005 ou OC-001"),
            ("tip","  💡 Pensez à noter la référence IOTA dans le champ Commentaire !"),
        ]

    def _wiki_graphs(self):
        return [
            ("h1","  📊 Graphiques & Statistiques"),
            ("",""),
            ("h2","  Onglet Statistiques"),
            ("","  Rapport texte complet avec :"),
            ("","  • QSOs par bande avec barre visuelle"),
            ("","  • QSOs par mode"),
            ("","  • QSOs par mois (12 derniers)"),
            ("","  • Top 15 pays DXCC estimés"),
            ("","  • Top 5 distances"),
            ("","  Bouton 📋 Copier → copie le rapport dans le presse-papier"),
            ("",""),
            ("h2","  Onglet Graphiques"),
            ("","  Choisissez le type dans la liste déroulante puis cliquez 📊 Générer :"),
            ("ok","  • QSOs par mois     — histogramme 24 derniers mois"),
            ("ok","  • QSOs par bande    — camembert coloré"),
            ("ok","  • QSOs par mode     — barres horizontales"),
            ("ok","  • Activité par heure — distribution UTC sur 24h"),
            ("ok","  • Progression DXCC  — courbe cumulative d'entités"),
            ("",""),
            ("h2","  Onglet Heatmap"),
            ("","  Carte mondiale de tous vos QSOs avec locator grid"),
            ("","  Trois modes d'affichage :"),
            ("","  • Entités DXCC   = couleur par pays"),
            ("","  • Densité QSOs   = gradient chaud selon le nombre de contacts"),
            ("","  • Continents     = couleur par continent avec légende"),
            ("tip","  💡 Requiert matplotlib + numpy (pip install matplotlib numpy)"),
        ]

    def _wiki_propagation(self):
        return [
            ("h1","  🌐 Propagation & Météo HF"),
            ("",""),
            ("h2","  Données solaires (hamqsl.com)"),
            ("","  Mise à jour automatique toutes les heures :"),
            ("ok","  SFI (Solar Flux Index)  — plus c'est élevé, meilleures sont les hautes bandes"),
            ("ok","  SN  (Sunspot Number)     — nombre de taches solaires"),
            ("ok","  K-index                  — activité géomagnétique (0-1 excellent, 5+ tempête)"),
            ("ok","  A-index                  — index géomagnétique journalier"),
            ("",""),
            ("h2","  Interprétation rapide"),
            ("ok","  🟢 SFI > 150 + K ≤ 2  = Conditions excellentes, 10m-15m ouverts"),
            ("tip","  🟡 SFI 100-150 + K ≤ 3 = Conditions normales"),
            ("warn","  🔴 K ≥ 5               = Tempête géomagnétique, évitez les hautes bandes"),
            ("",""),
            ("h2","  Greyline"),
            ("","  Calcul automatique pour votre locator :"),
            ("","  • Heure de lever et coucher solaire UTC"),
            ("","  • ± 30 minutes = fenêtre greyline"),
            ("","  • Bandes favorables greyline : 160m, 80m, 40m"),
            ("tip","  💡 La greyline est le moment idéal pour les DX longue distance !"),
            ("",""),
            ("h2","  Graphique MUF"),
            ("","  MUF estimée sur 24h selon SFI et K-index"),
            ("","  Les lignes pointillées indiquent les fréquences des bandes HF"),
            ("","  La ligne verticale blanche = heure actuelle UTC"),
            ("",""),
            ("h2","  Liens utiles"),
            ("","  • 🌐 DX Maps    → spots temps réel par bande"),
            ("","  • 📡 VOACAP     → prévisions de propagation point à point"),
        ]

    def _wiki_qsl(self):
        return [
            ("h1","  🖨️ QSL, LoTW & Confirmations"),
            ("",""),
            ("h2","  Export LoTW (ADIF)"),
            ("","  Menu clic droit dans le Journal → 📤 Exporter LoTW (ADIF)"),
            ("","  ou Clic droit → Exporter Sélection"),
            ("",""),
            ("","  Le fichier ADIF généré est compatible TQSL / LoTW :"),
            ("ok","  ✅ ADIF_VER 2.2.7"),
            ("ok","  ✅ STATION_CALLSIGN et MY_GRIDSQUARE inclus"),
            ("ok","  ✅ Sous-modes FT8/FT4/JS8/WSPR/JT65 automatiques"),
            ("",""),
            ("h2","  Workflow LoTW"),
            ("code","  1. Exporter → fichier .adi"),
            ("code","  2. Ouvrir dans TQSL → signer avec votre certificat"),
            ("code","  3. Uploader le .tq8 sur lotw.arrl.org"),
            ("tip","  💡 Configurez le chemin TQSL dans ⚙️ → LoTW/TQSL pour ouverture auto"),
            ("",""),
            ("h2","  QSL Reminder"),
            ("","  Onglet 📬 QSL Reminder → liste les QSOs anciens sans confirmation"),
            ("","  • Réglage du délai en jours (défaut 90j)"),
            ("","  • Filtre par système (LoTW / eQSL / QRZ / ClubLog)"),
            ("warn","  🔴 Rouge = plus d'un an sans confirmation"),
            ("tip","  🟡 Orange = au-delà du délai configuré"),
            ("",""),
            ("h2","  QSL Card"),
            ("","  Onglet 🖨️ QSL Card :"),
            ("","  1. Sélectionnez un QSO dans l'onglet Journal"),
            ("","  2. Cliquez 🖨️ Générer QSL Card"),
            ("","  3. Choisissez un thème (Classique / Nuit DX / Vintage / Contest)"),
            ("","  4. Modifiez le message et votre QTH si nécessaire"),
            ("","  5. 💾 Enregistrer PNG/PDF ou 🖨️ Imprimer directement"),
        ]

    def _wiki_cat(self):
        return [
            ("h1","  📻 Contrôle CAT & Mémoires fréquences"),
            ("",""),
            ("h2","  Protocole CAT"),
            ("","  Station Master utilise le protocole Kenwood CI-V (commandes FA/MD/SM/IF)"),
            ("","  Compatible avec la majorité des transceivers modernes :"),
            ("ok","  ✅ Kenwood : TS-590, TS-890, TS-2000, TS-480..."),
            ("ok","  ✅ Yaesu   : FT-991, FT-DX10, FT-DX101 (mode Kenwood émulé)"),
            ("ok","  ✅ Icom    : IC-7300, IC-7610 via adaptateur CI-V→RS232"),
            ("tip","  💡 Pour Icom, utilisez un câble USB-CI-V ou l'adaptateur RS-BA1"),
            ("",""),
            ("h2","  Configuration CAT"),
            ("","  ⚙️ Paramètres → 📻 CAT Transceiver :"),
            ("code","  Port  : COM4  (Windows) ou /dev/ttyUSB0 (Linux)"),
            ("code","  Baud  : 9600  (valeur la plus courante)"),
            ("","  Vitesses supportées : 4800, 9600, 19200, 38400, 57600"),
            ("",""),
            ("h2","  Données lues par CAT"),
            ("","  • VFO A : fréquence en temps réel → bande auto-détectée"),
            ("","  • Mode : LSB/USB/CW/FM/AM/DIG"),
            ("","  • S-Meter : barre de progression en temps réel"),
            ("","  • TX Status : indicateur 🔥 ON AIR lors de l'émission"),
            ("",""),
            ("h2","  Mémoires fréquences"),
            ("","  Onglet 📻 Mémoires :"),
            ("","  • 24 mémoires prédéfinies (FT8/SSB/CW toutes bandes)"),
            ("","  • Clic sur un bouton = accord immédiat du transceiver via CAT"),
            ("","  • Couleurs : 🟢 FT8/FT4  🔵 SSB  🟡 CW  🟣 DIG  🩵 FM"),
            ("","  • Ajout de mémoires personnalisées via le formulaire en haut"),
            ("","  • Stockées dans la base SQLite → persistantes entre sessions"),
        ]

    def _wiki_dashboard(self):
        return [
            ("h1","  🏠 Tableau de bord (Dashboard)"),
            ("",""),
            ("h2","  Vue d'ensemble"),
            ("","  Le Dashboard est le premier onglet — il centralise les informations les plus utiles :"),
            ("ok","  ✅ QSOs total + aujourd'hui"),
            ("ok","  ✅ Entités DXCC travaillées et confirmées"),
            ("ok","  ✅ Bande et fréquence active (via CAT)"),
            ("ok","  ✅ Résumé propagation solaire"),
            ("ok","  ✅ Greyline (lever/coucher solaire UTC)"),
            ("ok","  ✅ Dernier QSO enregistré"),
            ("ok","  ✅ Barres de progression Awards (DXCC 100/200/300, WAZ, WAS)"),
            ("ok","  ✅ Activité des 7 derniers jours"),
            ("ok","  ✅ Top 5 pays"),
            ("",""),
            ("h2","  Rapport PDF"),
            ("","  Bouton 📄 Générer Rapport PDF → crée un rapport complet A4 avec :"),
            ("","  • Statistiques générales, QSOs par bande et mode"),
            ("","  • Top 20 pays, activité mensuelle sur 12 mois"),
            ("","  • Mis en forme professionnel, prêt à partager"),
            ("tip","  💡 Requiert : pip install reportlab"),
            ("",""),
            ("h2","  Actualisation"),
            ("","  Le dashboard se rafraîchit automatiquement toutes les 30 secondes."),
            ("","  Bouton 🔄 Actualiser pour une mise à jour immédiate."),
        ]

    def _wiki_psk(self):
        return [
            ("h1","  📻 PSK Reporter"),
            ("",""),
            ("h2","  Qu'est-ce que PSK Reporter ?"),
            ("","  PSK Reporter est un réseau mondial de récepteurs SDR et stations amateurs"),
            ("","  qui logguent automatiquement les signaux entendus et les publient en temps réel."),
            ("",""),
            ("h2","  Onglet PSK Reporter"),
            ("","  Affiche quelles stations ont entendu votre signal dans la dernière heure."),
            ("ok","  • UTC : heure de réception"),
            ("ok","  • Callsign TX : votre station (ou station envoyant)"),
            ("ok","  • Entendu par : indicatif du récepteur"),
            ("ok","  • Locator RX : locateur Maidenhead du récepteur"),
            ("ok","  • Freq MHz / Bande / Mode / SNR"),
            ("ok","  • Pays du récepteur"),
            ("",""),
            ("h2","  Double-clic sur un spot"),
            ("","  → Affiche automatiquement le locateur du récepteur sur la Carte Live"),
            ("",""),
            ("h2","  Rafraîchissement"),
            ("","  Automatique toutes les 5 minutes via l'API PSK Reporter."),
            ("tip","  💡 Très utile pour vérifier la propagation et savoir qui vous entend !"),
            ("",""),
            ("h2","  Greyline animée (Carte Live)"),
            ("","  Le terminateur solaire est tracé sur la carte et mis à jour chaque minute."),
            ("","  • Case à cocher 🌓 Greyline animée pour l'activer/désactiver"),
            ("","  • Les points oranges indiquent la limite jour/nuit"),
            ("tip","  💡 Combinez la greyline avec les spots DX Cluster pour chasser les DX !"),
        ]

    def _wiki_contest(self):
        # Méthode conservée pour compatibilité mais non utilisée
        return [
            ("h1","  ⏱️ Mode Contest"),
            ("","  L'onglet Contest a été retiré."),
            ("","  Pour les contests, utilisez N1MM+ qui est spécialement conçu pour cela."),
            ("tip","  💡 Votre logbook Station Master reste actif pendant les contests via WSJT-X UDP."),
        ]


    def _wiki_config(self):
        return [
            ("h1","  ⚙️ Configuration"),
            ("",""),
            ("h2","  Fichier config.ini"),
            ("","  Créé automatiquement au premier lancement dans le dossier du script"),
            ("",""),
            ("h2","  Section [USER]"),
            ("code","  Callsign = ON5AM"),
            ("code","  Grid     = JO20SP   ← Locator Maidenhead 6 caractères"),
            ("",""),
            ("h2","  Section [CAT]"),
            ("code","  Port = COM4          ← Port série Windows"),
            ("code","  Baud = 9600          ← Vitesse de communication"),
            ("",""),
            ("h2","  Section [API]"),
            ("code","  QRZ_User = ON5AM     ← Login QRZ.com"),
            ("code","  QRZ_Pass = ****      ← Mot de passe QRZ"),
            ("code","  QRZ_Key  = xxxxxx    ← Clé API (abonnement XML requis)"),
            ("tip","  💡 Sans clé API QRZ, les lookups automatiques sont désactivés"),
            ("",""),
            ("h2","  Section [CLUSTER]"),
            ("code","  Host = on0dxk.dyndns.org"),
            ("code","  Port = 8000"),
            ("code","  Call = ON5AM"),
            ("",""),
            ("h2","  Section [DXCC]"),
            ("code","  Alert_Bands    = 20m,15m,10m"),
            ("code","  Alert_Countries= Japan,USA,Australia"),
            ("",""),
            ("h2","  Sauvegarde"),
            ("","  Bouton 💾 Backup → crée mon_logbook_DATE.db dans le dossier Backups/"),
            ("","  Backup automatique avant tout effacement de données"),
        ]

    def _wiki_troubleshoot(self):
        return [
            ("h1","  🔧 Dépannage"),
            ("",""),
            ("h2","  CAT ne fonctionne pas"),
            ("warn","  RADIO OFF affiché → le port série n'est pas accessible"),
            ("","  Solutions :"),
            ("","  • Vérifiez le numéro de port dans le Gestionnaire de périphériques Windows"),
            ("","  • Vérifiez que le baud rate correspond au menu de votre transceiver"),
            ("","  • Fermez tout autre logiciel utilisant ce port (WSJT-X, FLDigi...)"),
            ("","  • Essayez de brancher/débrancher le câble USB-CAT"),
            ("",""),
            ("h2","  Carte blanche"),
            ("","  → OpenStreetMap requiert une connexion internet"),
            ("","  → Vérifiez votre pare-feu / proxy d'entreprise"),
            ("",""),
            ("h2","  DX Cluster vide"),
            ("","  → Le serveur on0dxk.dyndns.org peut être temporairement hors ligne"),
            ("","  → Essayez un autre serveur : dxc.k3lr.com:7373 ou dx.sp5kab.pl:8000"),
            ("","  → Changez dans ⚙️ → DX Cluster"),
            ("",""),
            ("h2","  WSJT-X / FT8 non reçu"),
            ("","  → Vérifiez que WSJT-X envoie bien les UDP sur le port 2237"),
            ("","  → Menu WSJT-X : File → Settings → Reporting → UDP Server: 127.0.0.1:2237"),
            ("","  → L'indicateur RX DATA ✅ doit s'allumer en vert"),
            ("",""),
            ("h2","  Graphiques absents"),
            ("code","  pip install matplotlib numpy"),
            ("",""),
            ("h2","  Erreur import ADIF"),
            ("","  → Vérifiez que le fichier est bien en format ADIF standard"),
            ("","  → Les fichiers Cabrillo (.cbr) ne sont pas supportés"),
            ("",""),
            ("h2","  Performance lente avec beaucoup de QSOs"),
            ("","  → La base SQLite gère bien jusqu'à 100 000+ QSOs"),
            ("","  → Si lent : Backup → fermez → supprimez les vieux QSOs via clic droit"),
            ("",""),
            ("h2","  Contact & Version"),
            ("ok","  Station Master V21.0 — développé pour ON5AM"),
            ("ok","  Base de données : SQLite (mon_logbook.db)"),
            ("ok","  Python 3.9+ requis"),
        ]



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
            ("QRZ API Key:", "API", "QRZ_Key", get("API","QRZ_Key",""), "*"),
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

        ttk.Label(win, text="🔎 Recherche avancée", font=("Impact",18),
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
            fname = os.path.join(bdir, f"mon_logbook_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db")
            shutil.copy("mon_logbook.db", fname)
            messagebox.showinfo("Backup", f"✅ Sauvegarde réussie !\n\n📁 {fname}")
            self.status_var.set(f"💾 Backup : {os.path.basename(fname)}")
        except Exception as e:
            messagebox.showerror("Backup", f"Erreur : {e}")

    def update_radio_info(self, t, v):
        if t == "FREQ": 
            txt = f"VFO A: {int(v)/1000:,.1f} kHz"
            self.lbl_radio.config(text=txt, bootstyle="success-inverse")
            self.current_freq_hz = str(v)
        if t == "MODE": self.e_mode.delete(0,tk.END); self.e_mode.insert(0,v)
        if t == "SMETER": self.pb_smeter['value'] = v
        if t == "TX_STATUS":
            if v: self.lbl_radio.config(text="🔥 ON AIR 🔥", bootstyle="danger-inverse")
            else: self.lbl_radio.config(bootstyle="success-inverse")

    def on_cluster_spot(self, freq, call, comment, spotter, time_z):
        band = freq_to_band(freq); mode = get_mode_from_freq(freq)
        country = get_country_name(call) or "Unknown"
        
        # Calculer azimut
        azimut = ""
        # Stocker le spot brut
        self._all_spots.insert(0, (freq, call, comment, spotter, time_z, band, mode, country))
        if len(self._all_spots) > 200: self._all_spots = self._all_spots[:200]

        # Alerte sonore si activée et filtre correspondant
        if self.cluster_alert_var.get():
            tag = self._get_spot_tag(band, country, call)
            if tag in ('alert', 'new_dxcc'):
                try: self.root.bell()
                except: pass
                # Notification Windows
                label = "🆕 Nouveau DXCC !" if tag == 'new_dxcc' else "🔔 Alerte DX Cluster"
                threading.Thread(target=_send_toast, args=(label, f"{call} — {country}\n{freq} MHz  {band}  {mode}"), daemon=True).start()

        # Appliquer le filtre actif
        self._apply_cluster_filter()

    def on_cluster_click(self, e):
        sel = self.tree_cl.selection()
        if sel: 
            f_str = self.tree_cl.item(sel[0])['values'][1]
            try: self.cat.set_freq(float(f_str)*1000)
            except: pass

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
        ttk.Label(hdr, text=callsign, font=("Impact", 28), bootstyle="inverse-dark").pack(side="left", padx=10)

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
                      font=("Arial", 12), foreground="#e74c3c", justify="center").pack(expand=True)
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
            fname = os.path.join(bdir, f"mon_logbook_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db")
            shutil.copy("mon_logbook.db", fname)
            # Garder seulement les 10 derniers backups automatiques
            all_bk = sorted([
                f for f in os.listdir(bdir)
                if f.startswith("mon_logbook_") and f.endswith(".db")
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
            shutil.copy("mon_logbook.db", fname)
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
                sock.settimeout(5.0)
                sock.bind(('', port))
                try:
                    mreq = struct.pack("4sl", socket.inet_aton(mcast_ip), socket.INADDR_ANY)
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                except: pass
                self.root.after(0, lambda: self.lbl_data.config(
                    text=f"RX DATA ✅ (port {port})", foreground="#2ecc71"))

                while True:
                    try:
                        d, _ = sock.recvfrom(4096)
                    except socket.timeout:
                        continue

                    self.root.after(0, lambda: self.lbl_data.config(foreground="green"))
                    self.root.after(200, lambda: self.lbl_data.config(foreground="#2ecc71"))

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
                        # IMPORTANT : WSJT-X envoie type 5 ET type 12 pour chaque QSO.
                        # On ignore le type 12 si source=wsjtx pour éviter le doublon.
                        elif p.msg_type == 12 and self._udp_source != "wsjtx":
                            p.read_str()   # Id
                            adif_str = p.read_str()
                            if adif_str:
                                self._parse_adif_string(adif_str)

                    except Exception as e:
                        print(f"UDP parse error: {e}")

            except Exception as e:
                self.root.after(0, lambda: self.lbl_data.config(text="RX DATA ⚠️", foreground="#e74c3c"))
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
                                text="RX ADIF ✅", foreground="#2ecc71"))
                            self.root.after(3000, lambda: self.lbl_data.config(
                                text="RX DATA ✅", foreground="#2ecc71"))
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

        # Cherche un doublon dans les 3 dernières minutes (même call + même bande)
        rows = self.conn.cursor().execute(
            "SELECT time_on FROM qsos WHERE callsign=? AND band=? AND qso_date=?",
            (call, band, now_date)
        ).fetchall()
        for (t,) in rows:
            try:
                h, m = int(t[:2]), int(t[3:5])
                if abs((h * 60 + m) - now_mins) <= 3:
                    return   # doublon détecté dans la fenêtre de 3 min
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
        self.root.after(0, self.load_data)
        print(f"WSJT-X QSO logged: {call} {band} {mode}")

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
                "SELECT time_on FROM qsos WHERE callsign=? AND band=? AND qso_date=?",
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

        if inserted > 0:
            self.conn.commit()
            self.root.after(0, self.load_data)
            print(f"ADIF: {inserted} QSO(s) importé(s)")

    def process_uploads(self, d, row_id):
        pass  # Upload vers services externes (désactivé)

    def import_adif(self):
        fn = filedialog.askopenfilename()
        if not fn: return
        with open(fn, 'r', errors='ignore') as f: content = f.read().upper()
        recs = content.split('<EOR>'); cur = self.conn.cursor()
        for r in recs:
            if "<CALL:" not in r: continue
            def g(t): m = re.search(fr'<{t}:\d+>([^<]+)', r); return m.group(1).strip() if m else ""
            d=g("QSO_DATE"); t=g("TIME_ON"); df = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d)==8 else d
            cur.execute("INSERT INTO qsos (qso_date, time_on, callsign, band, mode, rst_sent, rst_rcvd, name, qth, distance, grid, freq, qrz_stat, eqsl_stat, lotw_stat, club_stat, comment) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'Import','Import','No','Import',?)",
                (df, f"{t[:2]}:{t[2:4]}", g("CALL"), g("BAND"), g("MODE"), g("RST_SENT"), g("RST_RCVD"), g("NAME"), g("QTH"), "", g("GRIDSQUARE"), "", g("COMMENT")))
        self.conn.commit(); self.load_data()


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
    canvas.create_text(w//2, 160, text="Ham Radio Logbook & Station Management",
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
            _s.configure("Treeview.Heading", background="#1a3a5c", foreground="#f39c12")

            # Splash screen
            splash = show_splash(app)
            app.after(1700, splash.destroy)
            app.after(1800, app.deiconify)

            HamLogbookApp(app)
            app.mainloop()
        except Exception as e:
            print("CRASH:", e); traceback.print_exc(); input()