"""
tab_spe_expert.py — Onglet SPE Expert pour Station Master
ON5AM Station Master V21.0

Contrôle et monitoring de l'ampli SPE Expert 1.3K-FA / 2K-FA
via port série — thread-safe, non-bloquant.
"""
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk

# ── Palette (idem tab_ft8_monitor) ───────────────────────────────────────────
BG     = "#0d1117"
BG2    = "#161b22"
BG3    = "#21262d"
FG     = "#e6edf3"
GREEN  = "#3fb950"
RED    = "#f85149"
YELLOW = "#d29922"
ORANGE = "#f0883e"
BLUE   = "#4d96ff"
GRAY   = "#484f58"

BANDS = ["160m", "80m", "60m", "40m", "30m", "20m",
         "17m",  "15m", "12m", "10m", "6m",  "4m"]
_BAND_IDX = {b: i for i, b in enumerate(BANDS)}


class SPEExpertTab:
    """
    Onglet SPE Expert pour Station Master.

    Paramètres
    ----------
    parent   : frame tk parent
    app      : référence à StationMasterApp
    port     : port série (ex. '/dev/ttyUSB1')
    baudrate : vitesse série (défaut 115200)
    """

    def __init__(self, parent, app, port: str = "/dev/ttyUSB1", baudrate: int = 115200):
        self.app      = app
        self._port    = port
        self._baud    = baudrate
        self._stop    = threading.Event()
        self._thread: threading.Thread = None
        self._cmd_q: queue.Queue = queue.Queue()
        self._status  = None          # dernier AmpStatus reçu (thread-safe: Python GIL)
        self._last_ok = 0.0           # time.monotonic() du dernier statut reçu

        self._build_ui(parent)
        self._start_thread()

    # ── Construction UI ───────────────────────────────────────────────────────
    def _build_ui(self, parent):
        parent.configure(bg=BG)

        # ── Header connexion ─────────────────────────────────────────────
        hdr = tk.Frame(parent, bg=BG2, pady=6)
        hdr.pack(fill="x", padx=4, pady=(4, 0))

        tk.Label(hdr, text="Port :", bg=BG2, fg=GRAY,
                 font=("Consolas", 9)).pack(side="left", padx=(10, 2))
        self._port_var = tk.StringVar(value=self._port)
        ttk.Entry(hdr, textvariable=self._port_var,
                  width=16).pack(side="left", padx=2)

        tk.Label(hdr, text="Baud :", bg=BG2, fg=GRAY,
                 font=("Consolas", 9)).pack(side="left", padx=(10, 2))
        self._baud_var = tk.StringVar(value=str(self._baud))
        ttk.Combobox(hdr, textvariable=self._baud_var,
                     values=["9600", "19200", "38400", "57600", "115200"],
                     width=8, state="readonly").pack(side="left", padx=2)

        tk.Button(hdr, text="🔌 Connecter", bg=BG3, fg=FG, relief="flat",
                  font=("Consolas", 9), padx=8, cursor="hand2",
                  activebackground=BG, command=self._reconnect
                  ).pack(side="left", padx=8)

        self._lbl_conn = tk.Label(hdr, text="⚪ Non connecté", bg=BG2, fg=GRAY,
                                  font=("Consolas", 9, "bold"))
        self._lbl_conn.pack(side="left", padx=8)

        self._lbl_age = tk.Label(hdr, text="", bg=BG2, fg=GRAY,
                                 font=("Consolas", 8))
        self._lbl_age.pack(side="right", padx=10)

        # ── Zone status ──────────────────────────────────────────────────
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        # Rangée 1 — informations état
        r1 = tk.Frame(body, bg=BG2, padx=8, pady=8)
        r1.pack(fill="x", pady=(0, 4))

        self._lbl_mode   = self._stat_cell(r1, "MODE")
        self._lbl_txrx   = self._stat_cell(r1, "TX / RX")
        self._lbl_band   = self._stat_cell(r1, "BANDE")
        self._lbl_anttx  = self._stat_cell(r1, "ANT TX")
        self._lbl_antrx  = self._stat_cell(r1, "ANT RX")
        self._lbl_pwrlvl = self._stat_cell(r1, "POWER LVL")

        # Rangée 2 — mesures
        r2 = tk.Frame(body, bg=BG2, padx=8, pady=8)
        r2.pack(fill="x", pady=(0, 4))

        self._lbl_power   = self._stat_cell(r2, "PUISSANCE W", fg=GREEN)
        self._lbl_swr_atu = self._stat_cell(r2, "SWR ATU",     fg=GREEN)
        self._lbl_swr_ant = self._stat_cell(r2, "SWR ANT",     fg=GREEN)
        self._lbl_vpa     = self._stat_cell(r2, "VPA (V)",     fg=BLUE)
        self._lbl_ipa     = self._stat_cell(r2, "IPA (A)",     fg=BLUE)
        self._lbl_temp    = self._stat_cell(r2, "TEMP °C",     fg=YELLOW)

        # Rangée 3 — alertes
        r3 = tk.Frame(body, bg=BG2, padx=8, pady=6)
        r3.pack(fill="x", pady=(0, 8))

        self._lbl_warn  = tk.Label(r3, text="Warning : —", bg=BG2, fg=YELLOW,
                                   font=("Consolas", 10))
        self._lbl_warn.pack(side="left", padx=16)
        self._lbl_alarm = tk.Label(r3, text="Alarm : —", bg=BG2, fg=RED,
                                   font=("Consolas", 10, "bold"))
        self._lbl_alarm.pack(side="left", padx=16)

        # ── Contrôles ────────────────────────────────────────────────────
        ctrl = tk.Frame(body, bg=BG3, padx=10, pady=8)
        ctrl.pack(fill="x")

        # Boutons opération
        for txt, key, fg in [
            ("⚡ OPERATE", "OPERATE", GREEN),
            ("💤 STANDBY", "OFF",     YELLOW),
            ("🔧 TUNE",    "TUNE",    ORANGE),
        ]:
            tk.Button(ctrl, text=txt, bg=BG2, fg=fg, relief="flat",
                      font=("Consolas", 10, "bold"), padx=12, pady=6,
                      cursor="hand2", activebackground=BG,
                      command=lambda k=key: self._send_key(k)
                      ).pack(side="left", padx=4)

        ttk.Separator(ctrl, orient="vertical").pack(side="left",
                                                     fill="y", padx=12, pady=4)

        # Sélection bande
        tk.Label(ctrl, text="Bande :", bg=BG3, fg=GRAY,
                 font=("Consolas", 9)).pack(side="left", padx=(4, 2))
        self._band_sel = tk.StringVar(value="20m")
        ttk.Combobox(ctrl, textvariable=self._band_sel, values=BANDS,
                     width=7, state="readonly").pack(side="left", padx=2)
        tk.Button(ctrl, text="→ Go", bg=BG2, fg=FG, relief="flat",
                  font=("Consolas", 9), padx=6, cursor="hand2",
                  activebackground=BG,
                  command=self._apply_band).pack(side="left", padx=4)

        ttk.Separator(ctrl, orient="vertical").pack(side="left",
                                                     fill="y", padx=12, pady=4)

        # Antenne
        tk.Label(ctrl, text="Antenne :", bg=BG3, fg=GRAY,
                 font=("Consolas", 9)).pack(side="left", padx=(4, 2))
        tk.Button(ctrl, text="Suivante →", bg=BG2, fg=BLUE, relief="flat",
                  font=("Consolas", 9), padx=6, cursor="hand2",
                  activebackground=BG,
                  command=lambda: self._send_key("ANTENNA")
                  ).pack(side="left", padx=4)

    @staticmethod
    def _stat_cell(parent, label: str, fg: str = FG) -> tk.Label:
        """Crée une cellule label+valeur dans une rangée, retourne le label valeur."""
        f = tk.Frame(parent, bg=BG2)
        f.pack(side="left", padx=14)
        tk.Label(f, text=label, bg=BG2, fg=GRAY,
                 font=("Consolas", 8)).pack()
        lbl = tk.Label(f, text="---", bg=BG2, fg=fg,
                       font=("Consolas", 13, "bold"), width=8)
        lbl.pack()
        return lbl

    # ── Thread background ─────────────────────────────────────────────────────
    def _start_thread(self):
        self._port = self._port_var.get().strip() or self._port
        self._baud = int(self._baud_var.get() or self._baud)
        # Nouvel event par thread — l'ancien thread garde sa propre référence
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll_loop,
                                        args=(self._stop,), daemon=True)
        self._thread.start()

    def _poll_loop(self, stop: threading.Event):
        """Thread série : connexion, polling 2s, dispatch commandes UI."""
        from spe_expert import SPEExpert
        port = self._port
        baud = self._baud
        while not stop.is_set():
            try:
                with SPEExpert(port, baudrate=baud, timeout=1.5) as amp:
                    self._post(lambda p=port: self._lbl_conn.config(
                        text=f"✅ Connecté  {p}", fg=GREEN))
                    while not stop.is_set():
                        # Vider la file de commandes UI
                        while not self._cmd_q.empty():
                            try:
                                self._cmd_q.get_nowait()(amp)
                            except Exception as e:
                                print(f"[SPE] cmd error: {e}")
                        # Polling statut
                        status = amp.get_status()
                        if status is not None:
                            self._status  = status
                            self._last_ok = time.monotonic()
                            self._post(lambda s=status: self._update_ui(s))
                        stop.wait(2.0)
            except Exception as e:
                msg = str(e)
                if "Errno 2" in msg or "No such file" in msg:
                    label = "❌ Port introuvable — câble débranché ?"
                elif "Errno 13" in msg or "Permission" in msg:
                    label = "❌ Accès refusé  (sudo usermod -aG dialout $USER)"
                elif "Errno 16" in msg or "busy" in msg.lower():
                    label = "❌ Port occupé par un autre programme"
                else:
                    label = f"❌ {msg[:55]}"
                self._post(lambda m=label: self._lbl_conn.config(text=m, fg=RED))
                stop.wait(5.0)   # pause avant retry

    def _post(self, fn):
        """Poste un callback dans la queue tkinter thread-safe."""
        try:
            self.app._tk_queue.put(fn)
        except Exception:
            pass

    # ── Commandes UI → thread série ───────────────────────────────────────────
    def _send_key(self, key: str):
        def _do(amp):
            if not amp.send_key(key):
                print(f"[SPE] ACK manquant pour '{key}'")
        self._cmd_q.put(_do)

    def _apply_band(self):
        """Calcule le delta et envoie N × BAND_UP ou BAND_DOWN."""
        target = self._band_sel.get()
        if self._status is None:
            return
        ci = _BAND_IDX.get(self._status.band, -1)
        ti = _BAND_IDX.get(target, -1)
        if ci < 0 or ti < 0 or ci == ti:
            return
        delta = ti - ci
        key   = "BAND_UP" if delta > 0 else "BAND_DOWN"
        steps = abs(delta)

        def _do(amp):
            for _ in range(steps):
                amp.send_key(key)
                time.sleep(0.15)   # laisser l'ampli traiter chaque impulsion
        self._cmd_q.put(_do)

    def _reconnect(self):
        """Relance le thread série sans bloquer l'UI."""
        self._stop.set()   # signal à l'ancien thread (son event privé)
        self._start_thread()   # crée un nouvel event + nouveau thread immédiatement

    def stop(self):
        """Arrêt propre — appelé à la fermeture de Station Master."""
        self._stop.set()   # arrête le thread actif (son event privé)

    # ── Mise à jour UI (thread tkinter uniquement) ────────────────────────────
    def _update_ui(self, s):
        self._lbl_mode.config(
            text=s.mode,
            fg=GREEN if s.mode == "Operate" else YELLOW)
        self._lbl_txrx.config(
            text=s.rx_tx,
            fg=RED if s.rx_tx == "TX" else GREEN)
        self._lbl_band.config(text=s.band)
        self._lbl_anttx.config(text=s.tx_ant)
        self._lbl_antrx.config(text=s.rx_ant)
        self._lbl_pwrlvl.config(text=s.power_level)

        # Puissance — couleur selon niveau
        p_fg = RED if s.out_power_w > 1200 else (YELLOW if s.out_power_w > 800 else GREEN)
        self._lbl_power.config(text=f"{s.out_power_w:>4d}", fg=p_fg)

        # SWR — rouge si > 2.0, orange si > 1.5
        for lbl, val in [(self._lbl_swr_atu, s.swr_atu),
                         (self._lbl_swr_ant, s.swr_ant)]:
            c = RED if val > 2.0 else (ORANGE if val > 1.5 else GREEN)
            lbl.config(text=f"{val:.2f}", fg=c)

        self._lbl_vpa.config(text=f"{s.vpa:.1f}")
        self._lbl_ipa.config(text=f"{s.ipa:.1f}")

        # Température — rouge > 65°C, orange > 50°C
        t_fg = RED if s.temp_c > 65 else (ORANGE if s.temp_c > 50 else YELLOW)
        self._lbl_temp.config(text=f"{s.temp_c}", fg=t_fg)

        self._lbl_warn.config(
            text=f"Warning : {s.warning or 'aucun'}",
            fg=YELLOW if s.warning else GRAY)
        self._lbl_alarm.config(
            text=f"Alarm : {s.alarm or 'aucune'}",
            fg=RED if s.alarm else GRAY)

        age = int(time.monotonic() - self._last_ok)
        self._lbl_age.config(text=f"statut il y a {age}s")
