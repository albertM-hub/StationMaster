"""
tab_ft8_monitor.py — Moniteur FT8/WSJT-X en temps réel
ON5AM Station Master V21.0

Reçoit les paquets UDP WSJT-X :
  Type 1 (Status)  → fréquence, mode, TX/RX, DX call
  Type 2 (Decode)  → décodes FT8/FT4 en direct avec SNR, message
  Type 3 (Clear)   → efface le tableau de décodes
  Type 5 (QSO Log) → rafraîchit les QSOs récents

Intégration dans station_master.py :
  1. from tab_ft8_monitor import FT8MonitorTab
  2. self._ft8_monitor = FT8MonitorTab(frame, app=self, my_call=MY_CALL)
  3. Dans udp_listener() : if self._ft8_monitor: self._ft8_monitor.on_raw_packet(d)
"""
import collections
import struct
import time
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone

# ── Palette couleurs (idem station_master.py) ────────────────────────────────
BG     = "#0d1117"
BG2    = "#161b22"
BG3    = "#21262d"
FG     = "#e6edf3"
GREEN  = "#3fb950"
YELLOW = "#d29922"
RED    = "#f85149"
BLUE   = "#4d96ff"
PURPLE = "#c77dff"
GRAY   = "#484f58"
PINK   = "#ff6bff"


# ── Parseur de paquets WSJT-X ────────────────────────────────────────────────

class _FT8Packet:
    """Décode les paquets WSJT-X UDP (Types 1, 2, 3, 5)."""
    MAGIC = 0xADBCCBDA

    def __init__(self, data: bytes):
        self.d = data
        self.pos = 0
        magic = self._u32()
        if magic != self.MAGIC:
            raise ValueError(f"Magic invalide: {magic:#010x}")
        self._u32()               # schema (ignoré)
        self.msg_type = self._u32()

    # ── Primitives de lecture ─────────────────────────────────────────────────
    def _u8(self):
        v = self.d[self.pos]
        self.pos += 1
        return v

    def _u32(self):
        v = struct.unpack('>I', self.d[self.pos:self.pos + 4])[0]
        self.pos += 4
        return v

    def _i32(self):
        v = struct.unpack('>i', self.d[self.pos:self.pos + 4])[0]
        self.pos += 4
        return v

    def _u64(self):
        v = struct.unpack('>Q', self.d[self.pos:self.pos + 8])[0]
        self.pos += 8
        return v

    def _f64(self):
        v = struct.unpack('>d', self.d[self.pos:self.pos + 8])[0]
        self.pos += 8
        return v

    def _bool(self):
        v = self.d[self.pos]
        self.pos += 1
        return bool(v)

    def _str(self):
        length = self._u32()
        if length == 0 or length == 0xFFFFFFFF:
            return ""
        if length > 512:
            self.pos += min(length, len(self.d) - self.pos)
            return ""
        s = self.d[self.pos:self.pos + length].decode('utf-8', errors='ignore')
        self.pos += length
        return s

    def _qdatetime(self):
        """Saute un QDateTime Qt : u64 (julian ms) + u8 (timespec) [+u32 si offset]."""
        self.pos += 8
        ts = self._u8()
        if ts == 2:
            self.pos += 4

    # ── Parseurs par type ─────────────────────────────────────────────────────
    def parse_status(self) -> dict:
        """Type 1 — Status : fréquence, mode, TX/RX, DX call, callsigns."""
        try:
            return {
                "id":           self._str(),
                "dial_freq":    self._u64(),   # Hz
                "mode":         self._str(),
                "dx_call":      self._str(),
                "report":       self._str(),
                "tx_mode":      self._str(),
                "tx_enabled":   self._bool(),
                "transmitting": self._bool(),
                "decoding":     self._bool(),
                "rx_df":        self._u32(),   # audio Hz
                "tx_df":        self._u32(),   # audio Hz
                "de_call":      self._str(),   # mon indicatif dans WSJT-X
                "de_grid":      self._str(),
                "dx_grid":      self._str(),
            }
        except Exception:
            return {}

    def parse_decode(self) -> dict:
        """Type 2 — Decode : décode FT8/FT4 individuel."""
        try:
            return {
                "id":         self._str(),
                "new":        self._bool(),
                "time_ms":    self._u32(),   # ms depuis début de période
                "snr":        self._i32(),   # dB
                "delta_time": self._f64(),   # secondes
                "delta_freq": self._u32(),   # Hz audio
                "mode":       self._str(),
                "message":    self._str(),
                "low_conf":   self._bool(),
                "off_air":    self._bool(),
            }
        except Exception:
            return {}


# ── Onglet FT8 Monitor ───────────────────────────────────────────────────────

class FT8MonitorTab:
    """
    Onglet FT8 Live pour Station Master.

    Paramètres
    ----------
    parent       : frame tk parent
    app          : référence à StationMasterApp
    my_call      : indicatif de la station (ex : "ON5AM")
    get_country  : fonction get_country_name(callsign) → str
    """

    MAX_DECODES = 300  # lignes max dans le tableau

    def __init__(self, parent, app, my_call: str = "ON5AM", get_country=None):
        self.app          = app
        self.my_call      = my_call.upper()
        self._get_country = get_country or (lambda _: "")
        self._status      = {}
        self._decode_count = 0
        self._worked_calls: set = set()
        self._worked_dxcc:  set = set()
        self._last_pkt_time: float = 0.0          # time.monotonic() du dernier paquet
        self._pkt_times: collections.deque = collections.deque(maxlen=120)

        self._build_ui(parent)
        self._load_worked()

    # ── Construction UI ───────────────────────────────────────────────────────
    def _build_ui(self, parent):
        parent.configure(bg=BG)

        # ── Barre de statut WSJT-X ───────────────────────────────────────
        top = tk.Frame(parent, bg=BG2, pady=5)
        top.pack(fill="x", padx=4, pady=(4, 0))

        tk.Label(top, text="WSJT-X", bg=BG2, fg=GRAY,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=(8, 4))

        self._lbl_freq = tk.Label(top, text="--- MHz", bg=BG2, fg=GREEN,
                                  font=("Consolas", 14, "bold"))
        self._lbl_freq.pack(side="left", padx=4)

        self._lbl_mode = tk.Label(top, text="---", bg=BG2, fg=YELLOW,
                                  font=("Consolas", 13))
        self._lbl_mode.pack(side="left", padx=(0, 12))

        # TX/RX indicateur
        tx_fr = tk.Frame(top, bg=BG2, padx=6, pady=2, relief="groove", bd=1)
        tx_fr.pack(side="left")
        self._lbl_txrx = tk.Label(tx_fr, text="◀ RX", bg=BG2, fg=GREEN,
                                  font=("Consolas", 12, "bold"), width=6)
        self._lbl_txrx.pack()

        # DX call en cours
        self._lbl_dxcall = tk.Label(top, text="", bg=BG2, fg=BLUE,
                                    font=("Consolas", 13, "bold"))
        self._lbl_dxcall.pack(side="left", padx=12)

        # Statut Decodium (watchdog)
        self._lbl_decodium = tk.Label(top, text="Decodium ❌", bg=BG2, fg=RED,
                                      font=("Consolas", 9))
        self._lbl_decodium.pack(side="right", padx=4)

        # Compteur à droite
        self._lbl_count = tk.Label(top, text="0 décodes", bg=BG2, fg=GRAY,
                                   font=("Consolas", 9))
        self._lbl_count.pack(side="right", padx=8)

        tk.Button(top, text="🗑 Effacer", bg=BG3, fg=FG, relief="flat",
                  font=("Consolas", 9), cursor="hand2", padx=6,
                  activebackground="#21262d",
                  command=self._clear_decodes).pack(side="right", padx=4)

        # ── Légende couleurs ─────────────────────────────────────────────
        leg = tk.Frame(parent, bg=BG, pady=3)
        leg.pack(fill="x", padx=8)
        legends = [
            ("● CQ",           "#4ade80"),
            ("● Répond à moi", "#fde047"),
            ("● Nouveau DXCC", "#f87171"),
            ("● Déjà logué",   "#6b7280"),
        ]
        for txt, col in legends:
            tk.Label(leg, text=txt, bg=BG, fg=col,
                     font=("Consolas", 9, "bold")).pack(side="left", padx=10)
        tk.Label(leg, text="— double-clic pour pré-remplir le formulaire",
                 bg=BG, fg=GRAY, font=("Consolas", 8, "italic")).pack(side="left")

        # ── Tableau principal des décodes ─────────────────────────────────
        tree_fr = tk.Frame(parent, bg=BG)
        tree_fr.pack(fill="both", expand=True, padx=4, pady=(2, 0))

        # Style dédié pour que ttkbootstrap n'écrase pas les tag_configure
        try:
            from tkinter import ttk as _ttk_mod
            _st = _ttk_mod.Style()
            _st.configure("FT8.Treeview",
                          background=BG, foreground=FG,
                          fieldbackground=BG, rowheight=22,
                          font=("Consolas", 9))
            _st.configure("FT8.Treeview.Heading",
                          background=BG3, foreground="#8b949e",
                          font=("Consolas", 9, "bold"))
            _st.map("FT8.Treeview",
                    background=[("selected", "#1c4966")],
                    foreground=[("selected", "#ffffff")])
            _tree_style = "FT8.Treeview"
        except Exception:
            _tree_style = "Treeview"

        cols = ("utc", "snr", "dt", "hz", "pays", "message")
        self._tree = ttk.Treeview(tree_fr, columns=cols,
                                  show="headings", selectmode="browse",
                                  style=_tree_style)
        hdrs = [
            ("utc",     "UTC",      75,  "center"),
            ("snr",     "SNR",      50,  "center"),
            ("dt",      "Δt",       45,  "center"),
            ("hz",      "Hz",       55,  "center"),
            ("pays",    "Pays",    155,  "w"),
            ("message", "Message", 380,  "w"),
        ]
        for col, txt, w, anc in hdrs:
            self._tree.heading(col, text=txt)
            self._tree.column(col, width=w, anchor=anc, stretch=(col == "message"))

        vsb = ttk.Scrollbar(tree_fr, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)

        # Couleurs bien contrastées — fond + texte lumineux par catégorie
        self._tree.tag_configure("cq",       background="#0d2e18", foreground="#4ade80")
        self._tree.tag_configure("reply",    background="#2e2800", foreground="#fde047")
        self._tree.tag_configure("new_dxcc", background="#2e0e0e", foreground="#f87171")
        self._tree.tag_configure("worked",   background=BG2,       foreground="#6b7280")
        self._tree.tag_configure("normal",   background=BG,        foreground=FG)
        self._tree.tag_configure("alt",      background=BG2,       foreground=FG)

        self._tree.bind("<Double-1>", self._on_double_click)

        # ── QSOs récents WSJT-X ─────────────────────────────────────────
        sep = tk.Frame(parent, bg=BG3, height=1)
        sep.pack(fill="x", padx=4, pady=(4, 0))

        lf_bot = tk.LabelFrame(parent, text=" QSOs récents WSJT-X ",
                               bg=BG, fg=GRAY, font=("Consolas", 9),
                               padx=4, pady=4)
        lf_bot.pack(fill="x", padx=4, pady=(0, 4))

        cols2 = ("heure", "call", "bande", "mode", "rst_r", "pays")
        self._tree_rec = ttk.Treeview(lf_bot, columns=cols2,
                                      show="headings", height=5)
        hdrs2 = [
            ("heure", "Heure",     80),
            ("call",  "Indicatif", 115),
            ("bande", "Bande",     65),
            ("mode",  "Mode",      65),
            ("rst_r", "RST Rcvd",  70),
            ("pays",  "Pays",      200),
        ]
        for col, txt, w in hdrs2:
            self._tree_rec.heading(col, text=txt)
            self._tree_rec.column(col, width=w)
        self._tree_rec.pack(fill="x")

        self._tree_rec.tag_configure("ft8",  background="#0d1a2e", foreground=BLUE)
        self._tree_rec.tag_configure("ft4",  background="#1a0d2e", foreground=PURPLE)
        self._tree_rec.tag_configure("digi", background=BG2,       foreground=FG)

        self._start_decodium_watchdog()

    # ── Données initiales ─────────────────────────────────────────────────────
    def _load_worked(self):
        """Charge callsigns et DXCC déjà travaillés depuis la DB."""
        try:
            c = self.app.conn.cursor()
            self._worked_calls = {
                r[0].upper()
                for r in c.execute("SELECT DISTINCT callsign FROM qsos").fetchall()
            }
            self._worked_dxcc = set()
            for (call,) in c.execute("SELECT DISTINCT callsign FROM qsos").fetchall():
                country = self._get_country(call)
                if country and not country.startswith("??"):
                    self._worked_dxcc.add(country)
        except Exception as e:
            print(f"[FT8Monitor] _load_worked: {e}")

    def load_recent_qsos(self):
        """Recharge les QSOs récents mode digi depuis la DB."""
        try:
            c = self.app.conn.cursor()
            rows = c.execute(
                "SELECT time_on, callsign, band, mode, rst_rcvd FROM qsos "
                "WHERE mode IN ('FT8','FT4','DIGU','PKTUSB','MFSK','JS8') "
                "ORDER BY qso_date DESC, time_on DESC LIMIT 15"
            ).fetchall()
            for item in self._tree_rec.get_children():
                self._tree_rec.delete(item)
            for (t, call, band, mode, rst) in rows:
                country = self._get_country(call)
                m = mode.upper()
                tag = "ft4" if "FT4" in m else "ft8" if "FT8" in m or "DIGU" in m or "PKT" in m else "digi"
                self._tree_rec.insert("", "end",
                                      values=(t, call, band, mode, rst, country),
                                      tags=(tag,))
        except Exception as e:
            print(f"[FT8Monitor] load_recent_qsos: {e}")

    # ── Réception paquets UDP ─────────────────────────────────────────────────
    def on_raw_packet(self, data: bytes):
        """Reçoit un paquet UDP brut — appelé depuis le thread UDP.
        Thread-safe : toutes les mises à jour UI passent par _tk_queue."""
        now = time.monotonic()
        self._last_pkt_time = now
        self._pkt_times.append(now)
        try:
            p = _FT8Packet(data)
            if p.msg_type == 1:
                s = p.parse_status()
                if s:
                    self.app._tk_queue.put(lambda st=s: self._update_status(st))
            elif p.msg_type == 2:
                d = p.parse_decode()
                if d:
                    self.app._tk_queue.put(lambda dec=d: self._add_decode(dec))
            elif p.msg_type == 3:
                self.app._tk_queue.put(self._clear_decodes)
            elif p.msg_type == 5:
                self.app._tk_queue.put(self.load_recent_qsos)
                self.app._tk_queue.put(self._refresh_worked)
        except Exception as exc:
            print(f"[FT8] parse error: {exc!r}  raw={data[:12].hex()}")

    def _refresh_worked(self):
        """Recharge les callsigns/DXCC travaillés après un nouveau QSO."""
        self._load_worked()

    # ── Watchdog Decodium ─────────────────────────────────────────────────────
    def _start_decodium_watchdog(self):
        self.app.root.after(2000, self._tick_decodium_watchdog)

    def _tick_decodium_watchdog(self):
        now     = time.monotonic()
        elapsed = now - self._last_pkt_time if self._last_pkt_time > 0 else 9999

        # Taux de paquets sur la fenêtre glissante de 60 s
        cutoff = now - 60.0
        rate   = sum(1 for t in self._pkt_times if t >= cutoff)

        if self._last_pkt_time == 0:
            text, color = "Decodium ❌", RED
        elif elapsed < 15:
            text  = f"Decodium ✅ ({int(elapsed)}s)  {rate}/min"
            color = GREEN
        elif elapsed < 60:
            text  = f"Decodium ⚠ ({int(elapsed)}s)"
            color = YELLOW
        else:
            text, color = "Decodium ❌ inactif", RED

        self._lbl_decodium.config(text=text, fg=color)
        self.app.root.after(2000, self._tick_decodium_watchdog)

    # ── Mises à jour UI ───────────────────────────────────────────────────────
    def _update_status(self, s: dict):
        freq_mhz = s.get("dial_freq", 0) / 1_000_000
        mode     = s.get("mode", "---")
        tx       = s.get("transmitting", False)
        dx_call  = s.get("dx_call", "")

        self._lbl_freq.config(text=f"{freq_mhz:.4f} MHz")
        self._lbl_mode.config(text=mode or "---")

        if tx:
            self._lbl_txrx.config(text="▶ TX  ", fg=RED)
        else:
            decoding = s.get("decoding", False)
            self._lbl_txrx.config(
                text="◀ RX ●" if decoding else "◀ RX  ",
                fg=GREEN if not decoding else PINK)

        self._lbl_dxcall.config(text=dx_call)
        self._status = s

    def _add_decode(self, d: dict):
        msg      = d.get("message", "").strip()
        snr      = d.get("snr", 0)
        dt       = d.get("delta_time", 0.0)
        df       = d.get("delta_freq", 0)
        low_conf = d.get("low_conf", False)

        if not msg:
            return

        utc_str = datetime.now(timezone.utc).strftime("%H%M%S")
        tokens  = msg.split()

        # Identifier le callsign DX et la nature du message
        dx_call        = ""
        is_cq          = False
        is_reply_to_me = False

        if tokens:
            if tokens[0] == "CQ":
                is_cq = True
                if len(tokens) >= 3:
                    # CQ DX ON5AM JO20 → tokens[-2]=ON5AM, tokens[-1]=JO20 (4 car.)
                    dx_call = tokens[-2] if len(tokens[-1]) == 4 else tokens[-1]
                elif len(tokens) == 2:
                    dx_call = tokens[1]
            elif len(tokens) >= 2 and tokens[0].upper() == self.my_call:
                is_reply_to_me = True
                dx_call        = tokens[1]
            elif len(tokens) >= 1:
                dx_call = tokens[0]  # expéditeur pour lookup pays/worked

        # Lookup pays
        country = ""
        if dx_call:
            c = self._get_country(dx_call)
            if c and not c.startswith("??"):
                country = c

        # Choix du tag couleur
        if is_reply_to_me:
            tag = "reply"
        elif is_cq and country and country not in self._worked_dxcc:
            tag = "new_dxcc"
        elif is_cq:
            tag = "cq"
        elif dx_call.upper() in self._worked_calls:
            tag = "worked"
        else:
            tag = "normal" if self._decode_count % 2 else "alt"

        if low_conf:
            msg = f"({msg})"

        self._tree.insert("", 0,
                          values=(utc_str, f"{snr:+d}", f"{dt:+.1f}", str(df), country, msg),
                          tags=(tag,))

        # Limiter la taille du tableau
        children = self._tree.get_children()
        if len(children) > self.MAX_DECODES:
            self._tree.delete(children[-1])

        self._decode_count += 1
        self._lbl_count.config(text=f"{self._decode_count} décodes")

    def _clear_decodes(self, _event=None):
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._decode_count = 0
        self._lbl_count.config(text="0 décodes")

    # ── Interaction ───────────────────────────────────────────────────────────
    def _on_double_click(self, _event):
        """Double-clic sur un décode → pré-remplit le formulaire Nouveau Contact."""
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0], "values")
        if not vals:
            return
        msg    = vals[5]  # colonne message (index 5)
        tokens = msg.strip("()").split()

        dx_call = ""
        if tokens:
            if tokens[0] == "CQ":
                if len(tokens) >= 3:
                    dx_call = tokens[-2] if len(tokens[-1]) == 4 else tokens[-1]
                elif len(tokens) == 2:
                    dx_call = tokens[1]
            elif len(tokens) >= 2:
                dx_call = tokens[1]

        if not dx_call:
            return

        # Remplir e_call dans le formulaire principal
        if hasattr(self.app, 'e_call'):
            self.app.e_call.delete(0, tk.END)
            self.app.e_call.insert(0, dx_call.upper())

        # Mode depuis Status WSJT-X
        mode = self._status.get("mode", "")
        if mode and hasattr(self.app, 'e_mode'):
            self.app.e_mode.delete(0, tk.END)
            self.app.e_mode.insert(0, mode)

        # RST par défaut FT8
        if hasattr(self.app, 'e_rst_s'):
            self.app.e_rst_s.delete(0, tk.END)
            self.app.e_rst_s.insert(0, "-10")
        if hasattr(self.app, 'e_rst_r'):
            self.app.e_rst_r.delete(0, tk.END)
            self.app.e_rst_r.insert(0, vals[1])  # colonne SNR

        # Aller sur l'onglet Dashboard (formulaire Nouveau Contact)
        if hasattr(self.app, 'nb'):
            try:
                self.app.nb.select(0)
            except Exception:
                pass