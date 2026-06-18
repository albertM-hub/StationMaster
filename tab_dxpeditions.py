"""
tab_dxpeditions.py — Onglet DXpéditions live pour Station Master / Logbook ON5AM
hamanalyst.org — ON5AM

Améliorations v2 :
  1. Source agenda ADXO (ng3k.com) — référence mondiale DXpéditions
  2. Sections ACTIVE (not spotted) + UPCOMING pliables
  3. Drapeaux pays + badges LoTW/eQSL sur les spots
  4. Colonnes compactes, age "just now"

Sources de données :
  • Spots  : DXwatch https://www.dxwatch.com/dxsd1/s.php
  • Agenda : ADXO    https://ng3k.com/misc/adxo.html  (parsing HTML)
             DXwatch https://www.dxwatch.com/dxsd1/l.php (JSON, fallback)

Dépendances :
  pip install requests
"""

import queue
import re
import threading
import calendar as cal_mod
import tkinter as tk
from tkinter import ttk
from datetime import datetime, date
from html.parser import HTMLParser
import requests

# ── Palette ───────────────────────────────────────────────────────────────────

BG       = "#11273f"
BG_CARD  = "#0d1e30"
BG_HDR   = "#0a1628"
BG_MODE  = "#071220"
BG_SEC   = "#0a1e2e"
FG       = "#c9d1d9"
FG_DIM   = "#8b949e"
ACCENT   = "#4fc3f7"
ORANGE   = "#f39c12"
RED      = "#f44336"
GREEN    = "#3fb950"
YELLOW   = "#ffd600"

MODE_COLOR = {
    "FT8":  "#00bcd4", "FT4":  "#00acc1",
    "CW":   "#ffd600", "SSB":  "#4caf50",
    "AM":   "#ab47bc", "RTTY": "#ff7043",
    "PSK":  "#ef5350", "DIGI": "#26c6da",
}

BAR_COLORS = [
    "#00bcd4","#4caf50","#ffd600","#ab47bc",
    "#ff7043","#29b6f6","#ef5350","#66bb6a",
    "#ce93d8","#ffa726","#a5d6a7","#ff5722",
    "#80cbc4","#f48fb1","#b39ddb","#ffcc02",
]

REFRESH_SPOTS_SEC  = 60
REFRESH_AGENDA_SEC = 600

# ── Drapeaux pays (préfixe DXCC → emoji drapeau) ────────────────────────────
# Mapping préfixes courants → code ISO2 → emoji
_PREFIX_ISO = {
    "K":"US","W":"US","N":"US","AA":"US","AB":"US","AC":"US","AD":"US",
    "AE":"US","AF":"US","AG":"US","AI":"US","AJ":"US","AK":"US",
    "F":"FR","G":"GB","DL":"DE","I":"IT","EA":"ES","PA":"NL",
    "ON":"BE","OZ":"DK","SM":"SE","OH":"FI","LA":"NO","SP":"PL",
    "OK":"CZ","OM":"SK","HA":"HU","YO":"RO","LZ":"BG","SV":"GR",
    "UA":"RU","UR":"UA","UN":"KZ","JA":"JP","BG":"CN","BY":"CN",
    "VK":"AU","ZL":"NZ","ZS":"ZA","PY":"BR","LU":"AR","CE":"CL",
    "XE":"MX","TI":"CR","HP":"PA","YV":"VE","OA":"PE","CP":"BO",
    "VU":"IN","HS":"TH","9V":"SG","VR":"HK","BY":"CN","BH":"CN",
    "S5":"SI","9A":"HR","T9":"BA","YU":"RS","Z3":"MK","E7":"BA",
    "4X":"IL","A9":"BH","A7":"QA","A6":"AE","HZ":"SA","OD":"LB",
    "EP":"IR","YK":"SY","JY":"JO","SU":"EG","ST":"SD","5B":"CY",
    "TA":"TR","4L":"GE","EK":"AM","UK":"UZ","EY":"TJ","EX":"KG",
    "JT":"MN","HL":"KR","DS":"KR","VQ9":"IO","3B8":"MU","3B9":"RE",
    "D4":"CV","C6":"BS","VP9":"BM","PJ2":"CW","PJ4":"BQ","PJ7":"SX",
    "ZF":"KY","FY":"GF","TO":"GP","FM":"MQ","FS":"MF","HI":"DO",
    "CO":"CU","YJ":"VU","H4":"SB","T8":"PW","KH6":"US","KL7":"US",
    "VE":"CA","VA":"CA","VY":"CA","TY":"BJ","5W":"WS","XX9":"MO",
    "S2":"BD","CY0":"CA","TL":"CF","T88":"PW","YJ1":"VU",
}

def call_to_flag(callsign: str) -> str:
    """Retourne l'emoji drapeau pour un callsign, ou '' si inconnu."""
    call = callsign.upper().strip()
    # Essaie les préfixes du plus long au plus court
    for length in (4, 3, 2, 1):
        pfx = call[:length]
        iso = _PREFIX_ISO.get(pfx)
        if iso:
            # Emoji drapeau = regional indicator letters
            return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso)
    return "🌐"

# ── Utilitaires ───────────────────────────────────────────────────────────────

def freq_to_band(f: float) -> str:
    if f < 2:    return "160m"
    if f < 4:    return "80m"
    if f < 5.5:  return "60m"
    if f < 8:    return "40m"
    if f < 11:   return "30m"
    if f < 15:   return "20m"
    if f < 18.5: return "17m"
    if f < 22:   return "15m"
    if f < 25:   return "12m"
    if f < 30:   return "10m"
    if f < 54:   return "6m"
    return "VHF+"

def guess_mode(f: float) -> str:
    for ref in [1.840,3.573,7.074,10.136,14.074,18.100,21.074,24.915,28.074]:
        if abs(f-ref) < 0.003: return "FT8"
    for ref in [3.575,7.047,10.140,14.080,18.104,21.140,24.919,28.180]:
        if abs(f-ref) < 0.003: return "FT4"
    for s,e in [(1.8,1.84),(3.5,3.6),(7.0,7.04),(14.0,14.07),(21.0,21.07),(28.0,28.07)]:
        if s <= f <= e: return "CW"
    return "SSB"

def parse_date_safe(s: str) -> date:
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%Y%m%d","%m/%d/%Y","%d-%b-%Y","%d %b %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except Exception:
            continue
    return date.today()

def age_label(minutes: int) -> str:
    if minutes == 0:   return "just now"
    if minutes < 60:   return f"{minutes}'"
    return f"{minutes//60}h{minutes%60:02d}"

# ── Parser HTML ADXO ──────────────────────────────────────────────────────────

class _ADXOParser(HTMLParser):
    """Parse ng3k.com/misc/adxo.html pour extraire le tableau DXpéditions."""

    def __init__(self):
        super().__init__()
        self.expeditions = []
        self._in_table   = False
        self._in_row     = False
        self._in_cell    = False
        self._cells      = []
        self._current    = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table": self._in_table = True
        if self._in_table and tag == "tr":
            self._in_row = True
            self._cells  = []
        if self._in_row and tag in ("td","th"):
            self._in_cell  = True
            self._current  = ""

    def handle_endtag(self, tag):
        if tag == "table": self._in_table = False
        if tag in ("td","th") and self._in_cell:
            self._cells.append(self._current.strip())
            self._in_cell = False
        if tag == "tr" and self._in_row:
            self._in_row = False
            self._process_row(self._cells)

    def handle_data(self, data):
        if self._in_cell:
            self._current += data

    def _process_row(self, cells):
        # ADXO format: Callsign | Entity | Start | End | Operator(s) | ...
        if len(cells) < 4:
            return
        call = cells[0].strip().upper()
        if not call or call in ("CALLSIGN","CALL","DX"):
            return
        # Filtre : le callsign doit ressembler à un indicatif radio
        if not re.match(r'^[A-Z0-9]{2,}', call):
            return
        try:
            start = parse_date_safe(cells[2])
            end   = parse_date_safe(cells[3])
            # Ignore les entrées avec dates invalides (= date.today par défaut)
            if start == date.today() and end == date.today():
                return
            self.expeditions.append({
                "callsign": call,
                "entity":   cells[1].strip(),
                "start":    start,
                "end":      end,
                "lotw":     "lotw" in " ".join(cells).lower(),
                "eqsl":     "eqsl" in " ".join(cells).lower(),
            })
        except Exception:
            pass

# ── Classe principale ─────────────────────────────────────────────────────────

class TabDXpeditions(tk.Frame):
    """
    Onglet DXpéditions live v2 — tkinter pur, compatible avec mon_logbook.py

    Intégration dans mon_logbook.py :
        t_dxped = tk.Frame(self.nb, bg="#11273f")
        self.nb.add(t_dxped, text="📡 DXpéditions")
        from tab_dxpeditions import TabDXpeditions
        TabDXpeditions(t_dxped, app=self)
    """

    def __init__(self, parent, app, clublog_api_key: str = ""):
        super().__init__(parent, bg=BG)
        self.pack(fill="both", expand=True)
        self.app         = app
        self.clublog_key = clublog_api_key
        self._queue      = queue.Queue()
        self._expeditions = []
        self._spots       = []

        self._build_ui()
        self._poll_queue()
        self.after(600,  self._refresh_agenda)
        self.after(1400, self._refresh_spots)

    # ── Pompe de messages ─────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg[0]
                if   kind == "agenda": self._apply_agenda(msg[1])
                elif kind == "spots":  self._apply_spots(msg[1])
                elif kind == "status": self._set_status(msg[1], msg[2])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _set_status(self, text: str, color: str = FG_DIM):
        self.lbl_status.config(text=text, fg=color)

    # ── Interface ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Barre titre
        hdr = tk.Frame(self, bg=BG_HDR)
        hdr.pack(fill="x")

        tk.Label(hdr, text="📡  DXPÉDITIONS LIVE",
                 bg=BG_HDR, fg=ACCENT,
                 font=("Consolas",12,"bold")).pack(side="left", padx=12, pady=6)

        self.lbl_status = tk.Label(hdr, text="⏳ Chargement...",
                                   bg=BG_HDR, fg=FG_DIM,
                                   font=("Consolas",9))
        self.lbl_status.pack(side="left", padx=8)

        tk.Button(hdr, text="🔄", bg="#1e2a3a", fg=ACCENT,
                  activebackground="#253545", relief="flat", bd=0,
                  cursor="hand2", font=("Consolas",11),
                  command=self._manual_refresh).pack(side="right", padx=10, pady=4)

        leg = tk.Frame(hdr, bg=BG_HDR)
        leg.pack(side="right", padx=10)
        for mode, color in list(MODE_COLOR.items())[:6]:
            tk.Label(leg, text=f" {mode} ", bg=BG_HDR, fg=color,
                     font=("Consolas",8,"bold")).pack(side="left", padx=1)

        # Canvas agenda
        self.canvas_agenda = tk.Canvas(self, bg=BG_HDR,
                                       highlightthickness=0, height=20)
        self.canvas_agenda.pack(fill="x", padx=6, pady=(4,0))
        self.canvas_agenda.bind("<Configure>", lambda e: self._draw_agenda())

        # Barre ON AIR
        sep = tk.Frame(self, bg="#0a1e30", height=26)
        sep.pack(fill="x")
        sep.pack_propagate(False)

        tk.Label(sep, text="● ON AIR", bg="#0a1e30", fg=GREEN,
                 font=("Consolas",10,"bold")).pack(side="left", padx=10, pady=3)
        self.lbl_on_air = tk.Label(sep, text="0", bg="#0a1e30", fg=ACCENT,
                                   font=("Consolas",13,"bold"))
        self.lbl_on_air.pack(side="left", padx=4)
        self.lbl_spots_age = tk.Label(sep, text="", bg="#0a1e30", fg="#445",
                                      font=("Consolas",9))
        self.lbl_spots_age.pack(side="right", padx=12)

        # Zone défilante
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        self.canvas_spots = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical",
                             command=self.canvas_spots.yview)
        self.canvas_spots.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas_spots.pack(side="left", fill="both", expand=True)

        self.spots_frame = tk.Frame(self.canvas_spots, bg=BG)
        self._win = self.canvas_spots.create_window(
            (0,0), window=self.spots_frame, anchor="nw")

        self.spots_frame.bind("<Configure>",
            lambda e: self.canvas_spots.configure(
                scrollregion=self.canvas_spots.bbox("all")))
        self.canvas_spots.bind("<Configure>",
            lambda e: self.canvas_spots.itemconfig(self._win, width=e.width))
        self.canvas_spots.bind("<MouseWheel>",
            lambda e: self.canvas_spots.yview_scroll(
                -1 if e.delta > 0 else 1, "units"))

    # ── Agenda — fetch ADXO + DXwatch ─────────────────────────────────────────

    def _refresh_agenda(self):
        threading.Thread(target=self._fetch_agenda, daemon=True).start()
        self.after(REFRESH_AGENDA_SEC * 1000, self._refresh_agenda)

    def _fetch_agenda(self):
        expeditions = []
        hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        # Source 1 — ADXO (ng3k.com) — la référence mondiale
        try:
            r = requests.get("https://ng3k.com/misc/adxo.html",
                             headers=hdrs, timeout=15)
            if r.ok:
                parser = _ADXOParser()
                parser.feed(r.text)
                expeditions = parser.expeditions
        except Exception as e:
            self._queue.put(("status", f"⚠ ADXO : {e}", RED))

        # Source 2 — DXwatch JSON (fallback)
        if not expeditions:
            try:
                r = requests.get("https://www.dxwatch.com/dxsd1/l.php",
                                 headers=hdrs, timeout=12)
                if r.ok:
                    raw = r.json().get("l", {})
                    for entry in (raw.values() if isinstance(raw, dict) else []):
                        try:
                            if isinstance(entry, list) and len(entry) >= 4:
                                expeditions.append({
                                    "callsign": str(entry[0]).strip().upper(),
                                    "entity":   str(entry[1]).strip(),
                                    "start":    parse_date_safe(str(entry[2])),
                                    "end":      parse_date_safe(str(entry[3])),
                                    "lotw":     False,
                                    "eqsl":     False,
                                })
                        except Exception:
                            continue
            except Exception as e:
                self._queue.put(("status", f"⚠ DXwatch liste : {e}", RED))

        # Fallback démo
        if not expeditions:
            expeditions = self._demo_expeditions()

        today = date.today()
        for e in expeditions:
            e.setdefault("lotw", False)
            e.setdefault("eqsl", False)
            e["active"] = e["start"] <= today <= e["end"]
            e["soon"]   = not e["active"] and 0 <= (e["start"] - today).days <= 14

        expeditions.sort(key=lambda x: (not x["active"], not x["soon"], x["start"]))
        self._queue.put(("agenda", expeditions))

    def _demo_expeditions(self) -> list:
        today = date.today()
        y, m  = today.year, today.month
        last  = cal_mod.monthrange(y, m)[1]
        m2 = m+1 if m < 12 else 1
        y2 = y if m < 12 else y+1
        return [
            {"callsign":"XX9W",  "entity":"Macao",       "start":date(y,m,17),"end":date(y,m,last),"lotw":True, "eqsl":False},
            {"callsign":"S21WD", "entity":"Bangladesh",  "start":date(y,m,28),"end":date(y2,m2,1), "lotw":True, "eqsl":True},
            {"callsign":"CY0S",  "entity":"Sable I.",    "start":date(y,m,19),"end":date(y,m,last),"lotw":True, "eqsl":False},
            {"callsign":"TY5FR", "entity":"Bénin",       "start":date(y,m, 4),"end":date(y,m,5),   "lotw":False,"eqsl":True},
            {"callsign":"TL8BNW","entity":"Centrafrique","start":date(y,m, 1),"end":date(y,m,last),"lotw":True, "eqsl":False},
            {"callsign":"PJ7AA", "entity":"Sint Maarten","start":date(y,m, 1),"end":date(y,m,28),  "lotw":True, "eqsl":True},
            {"callsign":"T88KH", "entity":"Palau",       "start":date(y,m, 5),"end":date(y,m,20),  "lotw":False,"eqsl":False},
            {"callsign":"5W0AF", "entity":"Samoa",       "start":date(y,m,22),"end":date(y,m,last),"lotw":True, "eqsl":False},
            {"callsign":"C6AFD", "entity":"Bahamas",     "start":date(y,m, 1),"end":date(y,m,last),"lotw":True, "eqsl":True},
            {"callsign":"D4Z",   "entity":"Cap Vert",    "start":date(y,m, 1),"end":date(y,m,last),"lotw":True, "eqsl":False},
            {"callsign":"3B8FA", "entity":"Maurice",     "start":date(y,m, 1),"end":date(y,m,last),"lotw":False,"eqsl":True},
            {"callsign":"PJ2",   "entity":"Curaçao",     "start":date(y,m, 1),"end":date(y,m,last),"lotw":True, "eqsl":True},
            {"callsign":"YJ1JXZ","entity":"Vanuatu",     "start":date(y,m, 1),"end":date(y,m,last),"lotw":False,"eqsl":False},
        ]

    # ── Agenda — dessin ───────────────────────────────────────────────────────

    def _apply_agenda(self, expeditions: list):
        self._expeditions = expeditions
        self._draw_agenda()
        active = sum(1 for e in expeditions if e.get("active"))
        soon   = sum(1 for e in expeditions if e.get("soon"))
        self._set_status(
            f"✅ {active} actives · ⏳ {soon} bientôt · {len(expeditions)} total",
            FG_DIM)

    def _draw_agenda(self):
        c = self.canvas_agenda
        c.delete("all")
        W = c.winfo_width()
        if W < 40 or not self._expeditions:
            return

        today  = date.today()
        y, m   = today.year, today.month
        n_days = cal_mod.monthrange(y, m)[1]

        AGENDA_W = int(W * 2 / 3)
        LEFT  = 72
        TOP   = 38
        ROW_H = 20
        BAR_H = 14
        PAD_Y = 3
        day_w = (AGENDA_W - LEFT) / n_days

        active = sum(1 for e in self._expeditions if e.get("active"))
        soon   = sum(1 for e in self._expeditions if e.get("soon"))
        c.create_text(4, 10, anchor="w",
                      text=f"DXPÉDITIONS  ·  {today.strftime('%B %Y').upper()}",
                      fill=ACCENT, font=("Consolas",9,"bold"))
        c.create_text(AGENDA_W-4, 10, anchor="e",
                      text=f"{active} ACTIVE  ·  {soon} SOON",
                      fill=ACCENT, font=("Consolas",9,"bold"))

        for d in range(1, n_days+1):
            x = LEFT + (d-1)*day_w + day_w/2
            is_today = (d == today.day)
            if is_today or day_w >= 14 or d == 1 or d % 5 == 0:
                if is_today:
                    c.create_rectangle(x-8, 13, x+8, 22, fill="#1a3a5c", outline="")
                c.create_text(x, 23, text=str(d),
                              fill=ACCENT if is_today else "#7a9bb5",
                              font=("Consolas",9,"bold" if is_today else "normal"))

        for d in range(1, n_days+1):
            x = LEFT + (d-1)*day_w
            c.create_line(x, TOP-6, x, TOP,
                          fill="#334" if d%5 != 0 else "#557", width=1)

        n_rows = sum(1 for e in self._expeditions
                     if e["start"] <= date(y,m,n_days) and e["end"] >= date(y,m,1))
        x_today = LEFT + (today.day-1)*day_w + day_w/2
        c.create_line(x_today, TOP-6, x_today, TOP + n_rows*ROW_H + 4,
                      fill=ACCENT, dash=(4,3), width=2)

        row = 0
        for i, exp in enumerate(self._expeditions):
            s_clip = max(exp["start"], date(y,m,1))
            e_clip = min(exp["end"],   date(y,m,n_days))
            if s_clip > e_clip:
                continue
            yy  = TOP + row*ROW_H
            col = BAR_COLORS[i % len(BAR_COLORS)]
            x1  = LEFT + (s_clip.day-1)*day_w
            x2  = LEFT + e_clip.day*day_w - 1

            c.create_text(LEFT-4, yy + BAR_H/2 + PAD_Y, anchor="e",
                          text=exp["callsign"],
                          fill=col if exp.get("active") else "#557",
                          font=("Consolas",9,"bold" if exp.get("active") else "normal"))
            c.create_rectangle(x1, yy+PAD_Y, x2, yy+BAR_H+PAD_Y,
                                fill=col, outline="")
            if x2-x1 > 40:
                c.create_text((x1+x2)/2, yy+BAR_H/2+PAD_Y,
                              text=exp.get("entity","")[:16],
                              fill="#000", font=("Consolas",8,"bold"))
            row += 1

        c.configure(height=max(60, TOP + row*ROW_H + 10))

    # ── Spots — fetch ─────────────────────────────────────────────────────────

    def _refresh_spots(self):
        threading.Thread(target=self._fetch_spots, daemon=True).start()
        self.after(REFRESH_SPOTS_SEC * 1000, self._refresh_spots)

    def _fetch_spots(self):
        hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            r = requests.get("https://www.dxwatch.com/dxsd1/s.php?s=0&r=200",
                             headers=hdrs, timeout=12)
            r.raise_for_status()
            spots = self._parse_dxwatch(r.json())
            if spots:
                self._queue.put(("spots", spots))
                return
        except Exception as e:
            self._queue.put(("status", f"⚠ DXwatch : {e}", RED))

        # Fallback DX Summit
        try:
            r = requests.get(
                "https://www.dxsummit.fi/DxSpots.aspx?count=200&format=json",
                headers=hdrs, timeout=12)
            r.raise_for_status()
            self._queue.put(("spots", self._parse_dxsummit(r.json())))
        except Exception as e:
            self._queue.put(("status", f"⚠ Spots indisponibles : {e}", RED))

    def _parse_dxwatch(self, data: dict) -> list:
        spots = []
        raw   = data.get("s", {})
        items = raw.values() if isinstance(raw, dict) else []
        dxped_calls = {e["callsign"].upper() for e in self._expeditions}

        for entry in items:
            try:
                if isinstance(entry, list):
                    spotter  = str(entry[0]).strip().upper()
                    freq     = float(entry[1]) / 1000
                    call     = str(entry[2]).strip().upper()
                    comment  = str(entry[3]).strip() if len(entry) > 3 else ""
                    mode     = guess_mode(freq)
                    for md in ["FT8","FT4","CW","SSB","AM","RTTY","PSK"]:
                        if md in comment.upper():
                            mode = md; break
                    age = 0; time_str = ""
                else:
                    freq     = float(entry.get("f",0)) / 1000
                    call     = (entry.get("dx","") or "").strip().upper()
                    mode     = (entry.get("md","") or "").strip().upper()
                    spotter  = (entry.get("de","") or "").strip().upper()
                    comment  = (entry.get("t", "") or "").strip()
                    ts_raw   = entry.get("t8",0)
                    if not mode: mode = guess_mode(freq)
                    ts       = datetime.fromtimestamp(int(ts_raw)) if ts_raw else datetime.now()
                    age      = max(0, int((datetime.now()-ts).total_seconds()/60))
                    time_str = ts.strftime("%H:%M")

                if not call or freq < 0.1: continue
                if dxped_calls and call not in dxped_calls: continue

                # Info LoTW/eQSL depuis l'agenda
                exp_info = next((e for e in self._expeditions
                                 if e["callsign"] == call), None)
                spots.append({
                    "call":    call,
                    "freq":    freq,
                    "band":    freq_to_band(freq),
                    "mode":    mode,
                    "spotter": spotter,
                    "comment": comment,
                    "time":    time_str,
                    "age_min": age,
                    "lotw":    exp_info.get("lotw", False) if exp_info else False,
                    "eqsl":    exp_info.get("eqsl", False) if exp_info else False,
                })
            except Exception:
                continue

        spots.sort(key=lambda x: x["age_min"])
        return spots

    def _parse_dxsummit(self, data) -> list:
        spots = []
        entries = data if isinstance(data, list) else data.get("spots",[])
        dxped_calls = {e["callsign"].upper() for e in self._expeditions}

        for entry in entries:
            try:
                freq    = float(entry.get("Frequency",0))
                call    = (entry.get("DXCall","") or "").strip().upper()
                spotter = (entry.get("SpotterCall","") or "").strip().upper()
                comment = (entry.get("Info","") or "").strip()
                mode    = (entry.get("Mode","") or "").strip().upper()
                ts_str  = entry.get("TimeUTC","")
                if not call or freq < 0.1: continue
                if not mode: mode = guess_mode(freq)
                if dxped_calls and call not in dxped_calls: continue
                try:
                    ts  = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
                    age = max(0, int((datetime.utcnow()-ts).total_seconds()/60))
                except Exception:
                    age = 0
                exp_info = next((e for e in self._expeditions
                                 if e["callsign"] == call), None)
                spots.append({
                    "call":call,"freq":freq,"band":freq_to_band(freq),
                    "mode":mode,"spotter":spotter,"comment":comment,
                    "time":ts_str[:5] if len(ts_str)>=5 else "",
                    "age_min":age,
                    "lotw": exp_info.get("lotw",False) if exp_info else False,
                    "eqsl": exp_info.get("eqsl",False) if exp_info else False,
                })
            except Exception:
                continue

        spots.sort(key=lambda x: x["age_min"])
        return spots

    # ── Spots — affichage ─────────────────────────────────────────────────────

    def _apply_spots(self, spots: list):
        self._spots = spots
        for w in self.spots_frame.winfo_children():
            w.destroy()

        # Stations avec spots récents
        by_call: dict = {}
        for s in spots:
            by_call.setdefault(s["call"], []).append(s)

        self.lbl_on_air.config(text=str(len(by_call)))
        if spots:
            min_age = min(s["age_min"] for s in spots)
            self.lbl_spots_age.config(
                text=f"dernier spot {age_label(min_age)}")

        for call, call_spots in by_call.items():
            self._add_station_card(call, call_spots)

        # ── Section ACTIVE (not spotted recently) ──
        spotted_calls = set(by_call.keys())
        silent = [e for e in self._expeditions
                  if e.get("active") and e["callsign"] not in spotted_calls]
        self._add_section_bar(
            f"▶  ACTIVE (NOT SPOTTED RECENTLY)   {len(silent)}",
            silent, collapsed=True)

        # ── Section UPCOMING ──
        upcoming = [e for e in self._expeditions if e.get("soon")]
        self._add_section_bar(
            f"▶  UPCOMING   {len(upcoming)}",
            upcoming, collapsed=True, color=YELLOW)

        self._set_status(
            f"✅ {len(by_call)} stations · {len(spots)} spots — "
            f"{datetime.now().strftime('%H:%M:%S')}", FG_DIM)

    def _add_section_bar(self, title: str, expeditions: list,
                         collapsed: bool = True, color: str = FG_DIM):
        """Barre pliable pour ACTIVE NOT SPOTTED et UPCOMING."""
        if not expeditions:
            return

        bar = tk.Frame(self.spots_frame, bg=BG_SEC)
        bar.pack(fill="x", padx=6, pady=(6,1))

        # Contenu pliable
        content = tk.Frame(self.spots_frame, bg=BG_SEC)
        visible = tk.BooleanVar(value=not collapsed)

        def toggle():
            if visible.get():
                content.pack_forget()
                visible.set(False)
            else:
                content.pack(fill="x", padx=6, pady=(0,4))
                visible.set(True)

        tk.Label(bar, text=title, bg=BG_SEC, fg=color,
                 font=("Consolas",9,"bold"),
                 cursor="hand2").pack(side="left", padx=10, pady=4)
        tk.Button(bar, text="▼" if not collapsed else "▶",
                  bg=BG_SEC, fg=color, relief="flat", bd=0,
                  font=("Consolas",9), cursor="hand2",
                  command=toggle).pack(side="right", padx=8)

        bar.bind("<Button-1>", lambda e: toggle())

        # Rangée de badges
        row_f = tk.Frame(content, bg=BG_SEC)
        row_f.pack(fill="x", padx=8, pady=4)

        for exp in expeditions:
            flag = call_to_flag(exp["callsign"])
            badge = tk.Frame(row_f, bg="#0d1e30", bd=1, relief="flat")
            badge.pack(side="left", padx=3, pady=2)
            tk.Label(badge,
                     text=f"{flag} {exp['callsign']}",
                     bg="#0d1e30", fg=FG,
                     font=("Consolas",9,"bold")).pack(padx=6, pady=2)
            tk.Label(badge,
                     text=exp.get("entity",""),
                     bg="#0d1e30", fg=FG_DIM,
                     font=("Consolas",8)).pack(padx=6)
            # Dates
            ds = (f"{exp['start'].strftime('%m-%d')}→"
                  f"{exp['end'].strftime('%m-%d')}")
            tk.Label(badge, text=ds, bg="#0d1e30", fg="#445",
                     font=("Consolas",7)).pack(padx=6, pady=(0,2))

        if not collapsed:
            content.pack(fill="x", padx=6, pady=(0,4))

    def _add_station_card(self, call: str, spots: list):
        exp_info = next(
            (e for e in self._expeditions if e["callsign"].upper() == call), None)

        card = tk.Frame(self.spots_frame, bg=BG_CARD, bd=1, relief="flat")
        card.pack(fill="x", padx=6, pady=3, ipady=2)

        # ── En-tête ──
        hdr = tk.Frame(card, bg=BG_HDR)
        hdr.pack(fill="x")

        # Drapeau + callsign
        flag = call_to_flag(call)
        tk.Label(hdr, text=flag, bg=BG_HDR,
                 font=("Segoe UI Emoji",12)).pack(side="left", padx=(8,2), pady=4)
        tk.Label(hdr, text=call, bg=BG_HDR, fg=FG,
                 font=("Consolas",13,"bold")).pack(side="left", padx=(2,6), pady=4)

        entity = exp_info.get("entity","") if exp_info else ""
        if entity:
            tk.Label(hdr, text=entity, bg=BG_HDR, fg=FG_DIM,
                     font=("Consolas",10)).pack(side="left", padx=4)

        # Badges LoTW / eQSL
        if exp_info and exp_info.get("lotw"):
            tk.Label(hdr, text=" LoTW ", bg="#1a4a1a", fg="#3fb950",
                     font=("Consolas",8,"bold")).pack(side="left", padx=2)
        if exp_info and exp_info.get("eqsl"):
            tk.Label(hdr, text=" eQSL ", bg="#1a3a4a", fg="#4fc3f7",
                     font=("Consolas",8,"bold")).pack(side="left", padx=2)

        # Dates + badge ON AIR + age
        if exp_info:
            ds = (f"📅 {exp_info['start'].strftime('%m-%d')} "
                  f"→ {exp_info['end'].strftime('%m-%d')}")
            tk.Label(hdr, text=ds, bg=BG_HDR, fg="#445",
                     font=("Consolas",8)).pack(side="right", padx=10)

        age = min(s["age_min"] for s in spots)
        tk.Label(hdr, text=" ON AIR ", bg="#bf360c", fg="#fff",
                 font=("Consolas",8,"bold")).pack(side="right", padx=4)
        tk.Label(hdr, text=age_label(age) + (" ago" if age > 0 else ""),
                 bg=BG_HDR, fg=FG_DIM,
                 font=("Consolas",9)).pack(side="right", padx=6)

        # ── Grille des modes (colonnes compactes) ──
        grid = tk.Frame(card, bg=BG_CARD)
        grid.pack(fill="x", padx=8, pady=6)

        modes: dict = {}
        for s in sorted(spots, key=lambda x: x["age_min"]):
            modes.setdefault(s["mode"], []).append(s)

        for col_idx, (mode, mode_spots) in enumerate(modes.items()):
            mc = MODE_COLOR.get(mode, "#aaaaaa")

            mf = tk.Frame(grid, bg=BG_MODE, bd=1, relief="solid",
                          highlightbackground=mc, highlightthickness=1)
            # sticky="nw" + weight=0 → colonnes compactes, pas d'étirement
            mf.grid(row=0, column=col_idx, padx=4, pady=2, sticky="nw")
            grid.columnconfigure(col_idx, weight=0)

            # Titre mode
            tk.Label(mf, text=f"  {mode}  ", bg=BG_MODE, fg=mc,
                     font=("Consolas",10,"bold")).pack(fill="x")
            tk.Frame(mf, bg=mc, height=2).pack(fill="x")

            # Spots (max 5)
            for sp in mode_spots[:5]:
                rf = tk.Frame(mf, bg=BG_MODE)
                rf.pack(padx=4, pady=1)

                tk.Label(rf, text=f"{sp['freq']:.3f}",
                         bg=BG_MODE, fg=FG,
                         font=("Consolas",10,"bold"),
                         width=9).pack(side="left")

                tk.Label(rf, text=age_label(sp["age_min"]),
                         bg=BG_MODE, fg=ORANGE,
                         font=("Consolas",9),
                         width=8).pack(side="left")

                tk.Label(rf, text=sp["band"],
                         bg=BG_MODE, fg=mc,
                         font=("Consolas",8),
                         width=5).pack(side="left")

            extra = len(mode_spots) - 5
            if extra > 0:
                tk.Label(mf, text=f"+{extra}",
                         bg=BG_MODE, fg="#444",
                         font=("Consolas",8)).pack(pady=(0,2))

    # ── Refresh manuel ────────────────────────────────────────────────────────

    def _manual_refresh(self):
        self._set_status("⏳ Actualisation...", ACCENT)
        threading.Thread(target=self._fetch_agenda, daemon=True).start()
        threading.Thread(target=self._fetch_spots,  daemon=True).start()