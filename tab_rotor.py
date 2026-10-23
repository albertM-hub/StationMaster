"""
tab_rotor.py — Onglet Rotor pour Station Master
ON5AM Station Master

Interface reprise de « rotor Yaesu/rotor_control.py » (carte, grand cercle,
clic sur la carte, recherche QRZ), partie série confiée à rotor.py.

Règles impératives :
  - AUCUNE rotation automatique : l'onglet ne lit ni le Journal, ni le cluster,
    ni les spots. Seuls les clics sur GO / CCW / CW font bouger l'antenne.
    Clic sur la carte et recherche QRZ remplissent le champ, sans rien envoyer.
  - Pas de touche Entrée = GO.
  - CCW / CW : appui maintenu, S au relâchement, à la sortie du bouton et à la
    perte de focus de la fenêtre.
  - STOP toujours cliquable ; Échap = STOP dans toute l'appli.
  - Port ouvert uniquement au clic sur « Connecter », jamais de reconnexion
    automatique. S envoyé à la déconnexion et à la fermeture de l'appli.
"""

import queue
import threading
import time
import tkinter as tk

import rotor_carte as rc

try:
    from PIL import Image, ImageTk
except ImportError:
    pass

# ── Palette (idem rotor_control.py) ──────────────────────────────────────────
C_BG = "#0d1117"
C_PANEL = "#161b22"
C_FG = "#e6edf3"
C_DIM = "#8b949e"
C_GREEN = "#3fb950"
C_RED = "#f85149"
C_BTN = "#21262d"
C_LINE = "#ff3333"
C_QTH = "#ffaa00"
C_BLUE = "#4d96ff"
C_YEL = "#d29922"

POLL_S = 0.25  # lecture azimut (commande C, sans mouvement), comme l'original
RESIZE_MS = 150  # redessin de la carte quand la taille ne bouge plus


def _grid_to_ll(grid: str):
    """Locator Maidenhead (4 ou 6 caractères) → (lat, lon) du centre de la case."""
    g = (grid or "").strip().upper()
    try:
        lon = (ord(g[0]) - 65) * 20 - 180 + int(g[2]) * 2
        lat = (ord(g[1]) - 65) * 10 - 90 + int(g[3])
        if len(g) >= 6:
            lon += (ord(g[4]) - 65) * (2 / 24) + 1 / 24
            lat += (ord(g[5]) - 65) * (1 / 24) + 1 / 48
        else:
            lon += 1
            lat += 0.5
        return lat, lon
    except (IndexError, ValueError):
        return None


class RotorTab:
    """
    Onglet Rotor pour Station Master.

    Paramètres
    ----------
    parent   : frame tk parent
    app      : StationMasterApp (utilisé pour _tk_queue et app.qrz seulement)
    port     : port série du contrôleur
    baudrate : vitesse série (défaut 9600)
    max_az   : limite haute acceptée par GO (AZ_MAX_DEG du firmware)
    qth      : (lat, lon) de la station, ou None
    grid     : locator, utilisé si qth est None
    callsign : indicatif affiché sur la carte
    """

    def __init__(
        self,
        parent,
        app,
        port: str,
        baudrate: int = 9600,
        max_az: int = 360,
        qth=None,
        grid: str = "",
        callsign: str = "ON5AM",
    ):
        self.app = app
        self._port = port
        self._baud = baudrate
        self._max_az = max_az
        # QTH : coordonnées de [ROTOR], sinon centre du locator
        self._qth_lat, self._qth_lon = qth or _grid_to_ll(grid) or (0.0, 0.0)
        self._callsign = callsign
        self._thread: threading.Thread = None
        self._quit = threading.Event()  # fin du thread (déconnexion)
        self._stop_req = threading.Event()  # STOP prioritaire sur la file
        self._cmd_q: queue.Queue = queue.Queue()
        self._connected = False
        self._manual = False  # CCW/CW maintenu en cours

        # Carte
        self.scale = 1.0  # carte affichée / carte de base
        self._base_img = None
        self._photo = None
        self._resize_job = None
        self._heading = None  # azimut lu (pointillé vert)
        self._target = None  # (az, lat, lon, nom) ; lat None = azimut seul

        self._parent = parent
        self._build_ui(parent)
        self._load_map()

        # Échap = STOP partout ; perte de focus = STOP si CCW/CW maintenu
        root = parent.winfo_toplevel()
        root.bind_all("<Escape>", lambda e: self._on_stop(), add="+")
        root.bind("<FocusOut>", lambda e: self._release_manual(), add="+")

    # ── Construction UI ───────────────────────────────────────────────────────
    def _build_ui(self, parent):
        parent.configure(bg=C_BG)

        # La carte occupe toute la place libre ; canvas centré, aux proportions de la carte
        self.map_frame = tk.Frame(parent, bg=C_BG, width=rc.MAP_W, height=rc.MAP_H)
        self.map_frame.grid(
            row=0, column=0, columnspan=4, padx=6, pady=6, sticky="nsew"
        )
        self.map_frame.bind("<Configure>", self._on_map_resize)
        self.canvas = tk.Canvas(
            self.map_frame,
            width=rc.MAP_W,
            height=rc.MAP_H,
            bg="#0a1e30",
            highlightthickness=0,
        )
        self.canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.canvas.bind("<Button-1>", self._map_click)

        def panel(col):
            f = tk.Frame(parent, bg=C_PANEL)
            f.grid(row=1, column=col, padx=3, pady=(0, 6), sticky="nsew")
            return f

        # Azimut courant
        p0 = panel(0)
        tk.Label(p0, text="AZIMUT", bg=C_PANEL, fg=C_DIM, font=("Consolas", 8)).pack(
            pady=(8, 0)
        )
        self.lbl_az = tk.Label(
            p0,
            text="---°",
            bg=C_PANEL,
            fg=C_GREEN,
            font=("Consolas", 40, "bold"),
            width=5,
        )
        self.lbl_az.pack(pady=(0, 8))

        # GO + CCW / STOP / CW
        p1 = panel(1)
        tk.Label(
            p1, text="ALLER À (°)", bg=C_PANEL, fg=C_DIM, font=("Consolas", 8)
        ).pack(pady=(8, 4))
        ef = tk.Frame(p1, bg=C_PANEL)
        ef.pack()
        self.entry_az = tk.Entry(
            ef,
            width=5,
            bg=C_BTN,
            fg=C_FG,
            font=("Consolas", 20, "bold"),
            justify="center",
            insertbackground=C_FG,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#30363d",
        )
        # Champ vide au départ : un GO sans saisie ne doit pas envoyer l'antenne au Nord
        self.entry_az.pack(side="left", padx=(0, 4))
        # Volontairement pas de <Return> → GO : seul le clic lance un mouvement
        self.btn_go = tk.Button(
            ef,
            text="GO",
            bg=C_GREEN,
            fg="#000",
            relief="flat",
            width=4,
            font=("Consolas", 12, "bold"),
            command=self._on_go,
        )
        self.btn_go.pack(side="left")

        bf = tk.Frame(p1, bg=C_PANEL)
        bf.pack(pady=6)
        self.btn_ccw = tk.Button(
            bf,
            text="◄ CCW",
            bg=C_BTN,
            fg=C_FG,
            font=("Consolas", 10, "bold"),
            relief="flat",
            width=5,
            activebackground="#404040",
        )
        self.btn_ccw.pack(side="left", padx=2)
        # STOP : jamais désactivé
        tk.Button(
            bf,
            text="■",
            bg=C_RED,
            fg=C_FG,
            font=("Consolas", 10, "bold"),
            relief="flat",
            width=5,
            activebackground="#b62324",
            command=self._on_stop,
        ).pack(side="left", padx=2)
        self.btn_cw = tk.Button(
            bf,
            text="CW ►",
            bg=C_BTN,
            fg=C_FG,
            font=("Consolas", 10, "bold"),
            relief="flat",
            width=5,
            activebackground="#404040",
        )
        self.btn_cw.pack(side="left", padx=2)
        for btn, direction in ((self.btn_ccw, "ccw"), (self.btn_cw, "cw")):
            btn.bind("<ButtonPress-1>", lambda e, d=direction: self._press_manual(d))
            btn.bind("<ButtonRelease-1>", lambda e: self._release_manual())
            btn.bind("<Leave>", lambda e: self._release_manual())
        tk.Label(
            p1,
            text="CCW / CW : maintenir · Échap = STOP",
            bg=C_PANEL,
            fg=C_DIM,
            font=("Consolas", 7),
        ).pack(pady=(0, 6))

        # Indicatif QRZ
        p2 = panel(2)
        tk.Label(
            p2, text="INDICATIF (QRZ)", bg=C_PANEL, fg=C_DIM, font=("Consolas", 8)
        ).pack(pady=(8, 4))
        cf = tk.Frame(p2, bg=C_PANEL)
        cf.pack()
        self.entry_call = tk.Entry(
            cf,
            width=9,
            bg=C_BTN,
            fg=C_QTH,
            font=("Consolas", 14, "bold"),
            justify="center",
            insertbackground=C_QTH,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#30363d",
        )
        self.entry_call.pack(side="left", padx=(0, 4))
        # Entrée = recherche seulement (aucune commande rotor)
        self.entry_call.bind("<Return>", lambda e: self._lookup())
        tk.Button(
            cf,
            text="⊙",
            bg=C_QTH,
            fg="#000",
            relief="flat",
            width=3,
            font=("Consolas", 14, "bold"),
            command=self._lookup,
        ).pack(side="left")
        self.lbl_call = tk.Label(
            p2,
            text="",
            bg=C_PANEL,
            fg=C_DIM,
            font=("Consolas", 8),
            wraplength=160,
            justify="center",
        )
        self.lbl_call.pack(pady=(4, 6))
        self._wrap_to_panel(self.lbl_call, p2)

        # Statut + connexion
        p3 = panel(3)
        tk.Label(p3, text="STATUT", bg=C_PANEL, fg=C_DIM, font=("Consolas", 8)).pack(
            pady=(8, 4)
        )
        self.lbl_status = tk.Label(
            p3, text="● HORS LIGNE", bg=C_PANEL, fg=C_RED, font=("Consolas", 10, "bold")
        )
        self.lbl_status.pack()
        self.btn_conn = tk.Button(
            p3,
            text="🔌 Connecter",
            bg=C_BTN,
            fg=C_FG,
            relief="flat",
            font=("Consolas", 9),
            padx=8,
            cursor="hand2",
            activebackground=C_BG,
            command=self._toggle_connect,
        )
        self.btn_conn.pack(pady=4)
        lbl_port = tk.Label(
            p3,
            text=f"{self._port}\n{self._baud} bd",
            bg=C_PANEL,
            fg=C_DIM,
            font=("Consolas", 8),
            wraplength=160,
            justify="center",
        )
        lbl_port.pack(pady=(2, 2))
        self._wrap_to_panel(lbl_port, p3)
        self.lbl_msg = tk.Label(
            p3,
            text="",
            bg=C_PANEL,
            fg=C_YEL,
            font=("Consolas", 8),
            wraplength=160,
            justify="center",
        )
        self.lbl_msg.pack(pady=(0, 6))
        self._wrap_to_panel(self.lbl_msg, p3)
        if not rc.HAS_PIL:
            tk.Label(
                p3,
                text="pip install Pillow numpy",
                bg=C_PANEL,
                fg=C_RED,
                font=("Consolas", 7),
            ).pack()

        for c in range(4):
            parent.columnconfigure(c, weight=1, uniform="panneaux")
        parent.rowconfigure(0, weight=1)

        self._set_move_buttons(False)

    def _wrap_to_panel(self, label, panel):
        # Retour à la ligne à la largeur réelle du panneau (suit le redimensionnement)
        panel.bind(
            "<Configure>",
            lambda e: label.config(wraplength=max(60, e.width - 12)),
            add="+",
        )

    def _set_move_buttons(self, enabled: bool):
        st = "normal" if enabled else "disabled"
        for b in (self.btn_go, self.btn_ccw, self.btn_cw):
            b.config(state=st)

    def _msg(self, text: str, fg: str = C_YEL):
        self.lbl_msg.config(text=text, fg=fg)

    # ── Carte ─────────────────────────────────────────────────────────────────
    def _xy(self, lon, lat):
        # Coordonnées à l'échelle de la carte affichée
        x, y = rc.ll_to_xy(lon, lat)
        return x * self.scale, y * self.scale

    def _load_map(self):
        if not rc.HAS_PIL:
            self._render_map()
            return
        self.canvas.create_text(
            rc.MAP_W // 2,
            rc.MAP_H // 2,
            text="Chargement carte…",
            fill=C_DIM,
            font=("Consolas", 12),
            tags="loading",
        )
        # Callback depuis un thread → passage par la queue tkinter
        rc.load_map_async(lambda img: self._post(lambda: self._show_map(img)))

    def _show_map(self, pil_img):
        self.canvas.delete("loading")
        self._base_img = pil_img
        self._render_map()

    def _on_map_resize(self, event):
        # Redessin différé : rien pendant le glissement, une fois la taille stabilisée
        if self._resize_job:
            self.canvas.after_cancel(self._resize_job)
        self._resize_job = self.canvas.after(
            RESIZE_MS, self._apply_scale, event.width, event.height
        )

    def _apply_scale(self, w, h):
        self._resize_job = None
        s = max(0.1, min(w / rc.MAP_W, h / rc.MAP_H))
        if abs(s - self.scale) < 0.002:
            return
        self.scale = s
        self.canvas.config(width=round(rc.MAP_W * s), height=round(rc.MAP_H * s))
        self.canvas.delete("loading")
        self._render_map()

    def _render_map(self):
        # Fond de carte à l'échelle courante, puis tracés par-dessus
        self.canvas.delete("mapbg")
        if self._base_img is not None:
            size = (round(rc.MAP_W * self.scale), round(rc.MAP_H * self.scale))
            img = self._base_img
            if img.size != size:
                img = img.resize(size, Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self._photo, tags="mapbg")
        elif not rc.HAS_PIL:
            self._draw_fallback()
        self.canvas.tag_lower("mapbg")
        self._draw_overlays()

    def _draw_fallback(self):
        c = self.canvas
        w, h = rc.MAP_W * self.scale, rc.MAP_H * self.scale
        c.create_rectangle(0, 0, w, h, fill="#0a1e30", outline="", tags="mapbg")
        for lo in range(-180, 181, 30):
            x, _ = self._xy(lo, 0)
            c.create_line(x, 0, x, h, fill="#122030", tags="mapbg")
        for la in range(-90, 91, 30):
            _, y = self._xy(0, la)
            c.create_line(0, y, w, y, fill="#122030", tags="mapbg")
        for poly in rc.CONTINENTS:
            pts = []
            for lo, la in poly:
                pts.extend(self._xy(lo, max(-85, min(85, la))))
            if len(pts) >= 6:
                c.create_polygon(pts, fill="#2a4a2a", outline="#3a6a3a", tags="mapbg")

    def _gc_line(self, az, dist_deg, **opts):
        # Grand cercle depuis le QTH sur dist_deg degrés d'arc, coupé à l'antiméridien
        pts_ll = rc.great_circle_pts(
            self._qth_lat, self._qth_lon, az, n=max(2, int(dist_deg)), dist_deg=dist_deg
        )
        segs, seg, prev_x = [], [], None
        for lat, lon in pts_ll:
            while lon > 180:
                lon -= 360
            while lon < -180:
                lon += 360
            x, y = self._xy(lon, lat)
            if prev_x is not None and abs(x - prev_x) > rc.MAP_W * self.scale / 2:
                if seg:
                    segs.append(seg)
                seg = []
            seg.append((x, y))
            prev_x = x
        if seg:
            segs.append(seg)
        for s in segs:
            if len(s) >= 2:
                self.canvas.create_line(
                    [c for pt in s for c in pt], smooth=True, tags="overlay", **opts
                )

    def _draw_overlays(self):
        # Cap du rotor (pointillé vert), cible (rouge, arrêtée au point visé), QTH par-dessus
        c = self.canvas
        c.delete("overlay")
        if self._heading is not None:
            self._gc_line(
                self._heading % 360, 180.0, fill=C_GREEN, width=1, dash=(4, 3)
            )
        if self._target is not None:
            az, lat, lon, name = self._target
            if lat is None:
                self._gc_line(az, 180.0, fill=C_LINE, width=2)
            else:
                self._gc_line(
                    az,
                    rc.central_angle(self._qth_lat, self._qth_lon, lat, lon),
                    fill=C_LINE,
                    width=2,
                )
                tx, ty = self._xy(lon, lat)
                c.create_oval(
                    tx - 6,
                    ty - 6,
                    tx + 6,
                    ty + 6,
                    outline=C_LINE,
                    width=2,
                    tags="overlay",
                )
                c.create_oval(
                    tx - 2,
                    ty - 2,
                    tx + 2,
                    ty + 2,
                    fill="white",
                    outline="",
                    tags="overlay",
                )
                if name:
                    c.create_text(
                        tx + 9,
                        ty + 9,
                        text=name,
                        anchor="nw",
                        fill=C_LINE,
                        font=("Consolas", 8, "bold"),
                        tags="overlay",
                    )
        qx, qy = self._xy(self._qth_lon, self._qth_lat)
        c.create_oval(
            qx - 5,
            qy - 5,
            qx + 5,
            qy + 5,
            fill=C_QTH,
            outline="white",
            width=1,
            tags="overlay",
        )
        c.create_text(
            qx + 8,
            qy - 8,
            text=self._callsign,
            fill=C_QTH,
            font=("Consolas", 8, "bold"),
            tags="overlay",
        )

    def _set_heading(self, az):
        if az != self._heading:
            self._heading = az
            self._draw_overlays()

    def _set_target(self, az, lat=None, lon=None, name=None):
        self._target = (az, lat, lon, name)
        self._draw_overlays()

    # ── Actions UI (thread tkinter) ───────────────────────────────────────────
    def _map_click(self, event):
        """Remplit le champ azimut avec le cap du point cliqué. Rien n'est envoyé."""
        lon, lat = rc.xy_to_ll(event.x / self.scale, event.y / self.scale)
        az = rc.bearing(self._qth_lat, self._qth_lon, lat, lon)
        self.entry_az.delete(0, tk.END)
        self.entry_az.insert(0, f"{az:.0f}")
        self._set_target(az, lat, lon)

    def _lookup(self):
        """Recherche QRZ : remplit le champ azimut. Rien n'est envoyé au rotor."""
        call = self.entry_call.get().strip().upper()
        if not call:
            return
        self.lbl_call.config(text="Recherche…", fg=C_DIM)
        qrz = getattr(self.app, "qrz", None)

        def worker():
            info = qrz.get_info(call) if qrz is not None else None
            if not info:
                self._post(
                    lambda: self.lbl_call.config(
                        text=f"{call} : introuvable ou QRZ non configuré", fg=C_RED
                    )
                )
                return
            try:
                lat, lon = float(info["lat"]), float(info["lon"])
            except (KeyError, TypeError, ValueError):
                ll = _grid_to_ll(info.get("grid", ""))
                if ll is None:
                    self._post(
                        lambda: self.lbl_call.config(
                            text=f"{call} : position inconnue sur QRZ", fg=C_RED
                        )
                    )
                    return
                lat, lon = ll
            az = rc.bearing(self._qth_lat, self._qth_lon, lat, lon)
            country = info.get("country", "")
            self._post(lambda: self._apply_lookup(call, az, country, lat, lon))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_lookup(self, call, az, country, lat, lon):
        self.entry_az.delete(0, tk.END)
        self.entry_az.insert(0, f"{az:.0f}")
        self.lbl_call.config(
            text=f"{country}\n→ {az:.1f}°  (GO pour tourner)", fg=C_GREEN
        )
        self._set_target(az, lat, lon, call)
        # Pas de M ici : la rotation ne part qu'avec GO, jamais sur une simple recherche

    def _toggle_connect(self):
        if self._thread is not None and self._thread.is_alive():
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        self._quit = threading.Event()
        self._stop_req.clear()
        self._drain_queue()
        self.btn_conn.config(state="disabled")
        self.lbl_status.config(text="⏳ Connexion…", fg=C_YEL)
        self._msg("")
        self._thread = threading.Thread(
            target=self._serial_loop,
            args=(self._port, self._baud, self._quit),
            daemon=True,
        )
        self._thread.start()

    def _disconnect(self):
        self._manual = False
        self._quit.set()  # le thread envoie S puis ferme le port

    def _on_go(self):
        if not self._connected:
            return
        txt = self.entry_az.get().strip()
        if not txt:
            self._msg("Tape un azimut avant GO", C_RED)
            return
        try:
            az = int(txt)
        except ValueError:
            self._msg("Azimut : nombre entier attendu", C_RED)
            return
        if not 0 <= az <= self._max_az:
            # Pas de modulo silencieux : 400 ne doit pas devenir 40
            self._msg(f"Azimut hors plage (0–{self._max_az}°)", C_RED)
            return
        # Une cible localisée (QRZ, clic) reste affichée si GO vise son cap
        if not (
            self._target
            and self._target[1] is not None
            and round(self._target[0]) % 360 == az % 360
        ):
            self._set_target(az)
        self._msg(f"GO {az:03d}° envoyé", C_GREEN)
        self._cmd_q.put(lambda rot, a=az: rot.goto(a))

    def _press_manual(self, direction: str):
        if not self._connected or self._manual:
            return
        self._manual = True
        self._msg(f"{direction.upper()} — relâcher pour arrêter", C_BLUE)
        self._cmd_q.put(lambda rot: rot.ccw() if direction == "ccw" else rot.cw())

    def _release_manual(self):
        if self._manual:
            self._manual = False
            self._request_stop()
            self._msg("Relâché — STOP envoyé", C_DIM)

    def _on_stop(self):
        """STOP : toujours accepté. Hors connexion, on le signale simplement."""
        self._manual = False
        if not self._connected:
            self._msg("STOP : rotor non connecté, rien envoyé", C_DIM)
            return
        self._request_stop()
        self._msg("STOP envoyé", C_RED)

    def _request_stop(self):
        # Prioritaire : le thread vide la file avant d'envoyer S, une rotation
        # en attente ne peut donc pas partir après ce STOP
        self._stop_req.set()

    def _drain_queue(self):
        while True:
            try:
                self._cmd_q.get_nowait()
            except queue.Empty:
                return

    # ── Thread série ──────────────────────────────────────────────────────────
    def _serial_loop(self, port: str, baud: int, quit_ev: threading.Event):
        """Ouvre le port, lit l'azimut, exécute les commandes des boutons.
        Pas de reconnexion automatique : sur erreur, le thread s'arrête."""
        from rotor import Rotor, RotorError

        rot = Rotor(port, baudrate=baud, max_az=self._max_az)
        try:
            rot.open()
        except RotorError as e:
            self._post(lambda m=str(e): self._on_disconnected(m))
            return
        self._post(self._on_connected)
        err = None
        try:
            next_poll = 0.0
            while not quit_ev.is_set():
                # 1) STOP en priorité : vider la file puis S
                if self._stop_req.is_set():
                    self._stop_req.clear()
                    self._drain_queue()
                    ok = rot.stop()  # S + attente du OK, renvoi si besoin
                    self._post(lambda o=ok: self._on_stop_result(o))
                    continue
                # 2) Commandes des boutons, une à la fois
                try:
                    cmd = self._cmd_q.get_nowait()
                except queue.Empty:
                    cmd = None
                if cmd is not None:
                    try:
                        cmd(rot)
                    except RotorError as e:
                        self._post(lambda m=str(e): self._msg(m, C_RED))
                    continue
                # 3) Lecture azimut (C) — sans mouvement
                now = time.monotonic()
                if now >= next_poll:
                    az = rot.read_az()
                    next_poll = now + POLL_S
                    self._post(lambda a=az: self._update_az(a))
                quit_ev.wait(0.02)
        except Exception as e:
            err = str(e)[:60]
        finally:
            # S + attente du OK avant de fermer (sinon le S peut être perdu)
            if not rot.close() and not err:
                err = "S de fermeture NON confirmé — vérifier le rotor"
            self._post(lambda m=err: self._on_disconnected(m))

    def _post(self, fn):
        """Poste un callback dans la queue tkinter thread-safe."""
        try:
            self.app._tk_queue.put(fn)
        except Exception:
            pass

    # ── Mise à jour UI (thread tkinter uniquement) ────────────────────────────
    def _on_connected(self):
        self._connected = True
        self.lbl_status.config(text="● EN LIGNE", fg=C_GREEN)
        self.btn_conn.config(text="⏏ Déconnecter", state="normal")
        self._set_move_buttons(True)

    def _on_stop_result(self, ok: bool):
        if ok:
            self._msg("STOP confirmé par le contrôleur", C_GREEN)
        else:
            self._msg("⚠ STOP NON CONFIRMÉ — vérifier le rotor", C_RED)

    def _on_disconnected(self, err):
        self._connected = False
        self._manual = False
        self.lbl_status.config(text="● HORS LIGNE", fg=C_RED)
        self.btn_conn.config(text="🔌 Connecter", state="normal")
        self._set_move_buttons(False)
        if err:
            self._msg(f"❌ {err}", C_RED)
        self.lbl_az.config(text="---°")
        self._heading = None
        self._draw_overlays()

    def _update_az(self, az):
        if not self._connected:
            return
        if az is None:
            self.lbl_az.config(text="---°", fg=C_YEL)
            self._msg("Pas de réponse à C — vitesse / protocole ?", C_YEL)
            return
        self.lbl_az.config(text=f"{az:03d}°", fg=C_GREEN)
        if self.lbl_msg.cget("text").startswith("Pas de réponse"):
            self._msg("")
        self._set_heading(az)

    # ── Arrêt ─────────────────────────────────────────────────────────────────
    def stop(self):
        """Arrêt propre — appelé à la fermeture de Station Master.
        Attend que le thread ait envoyé S et fermé le port."""
        self._manual = False
        self._stop_req.set()
        self._quit.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(
                timeout=5.0
            )  # 2 s reset Arduino + 2 × 1 s d'attente du OK
