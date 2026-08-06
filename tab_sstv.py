"""
tab_sstv.py — Onglet SSTV (réception) pour Station Master (ON5AM).

Phase 1 (RX) uniquement — voir docs/plans/2026-08-06-sstv-tab-design.md.
Émission (TX) et galerie viennent dans une étape ultérieure.

Architecture :
- `tci_client.TCIClient` (contrôle/statut uniquement — fréquence, S-meter).
- `dax_audio.DAXAudioRX` (audio RX réel, via device PipeWire aethersdr-dax-1).
- `sstv_decoder` (pure logique, sans dépendance Tkinter).
Un thread daemon consomme l'audio en continu ; tout rendu Tkinter passe par
`app._tk_queue`, comme les autres threads réseau de Station Master (jamais
d'appel Tkinter direct hors du thread principal).

Tant qu'aucun VIS n'est verrouillé, seule une fenêtre glissante des ~2
dernières secondes d'audio est gardée pour la recherche VIS (coût constant,
pas de rescan d'un buffer qui grossirait indéfiniment en attente de signal).
Une fois verrouillé, l'audio s'accumule dans un buffer dédié à l'image en
cours, réinitialisé à la fin de la réception.
"""

import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
from PIL import Image, ImageTk

import dax_audio
import sstv_decoder as sstvdec
import tci_client

BG = "#0d1526"
PANEL_BG = "#152238"
FG = "#e8eef7"
ACCENT = "#4a9eff"
BORDER = "#2a3b5c"

WATERFALL_HEIGHT = 220
WATERFALL_WIDTH = 640
WATERFALL_FREQ_MAX = 3000  # Hz, comme la capture Nexus

SEARCH_WINDOW_S = 2.0
VIS_SEARCH_INTERVAL_S = 0.3
DECODE_INTERVAL_S = 1.0

SSTV_MODES_UI = ["Auto", "Scottie 1", "Scottie 2", "Martin 1", "Martin 2", "Robot 36"]
_NAME_TO_VIS = {sstvdec.MODES[c].name: c for c in sstvdec.MODES}
_NAME_TO_VIS["Robot 36"] = sstvdec.ROBOT36_VIS


def _decodium_running():
    """Best-effort : détecte si Decodium tourne déjà (usage exclusif du flux
    DAX recommandé). Une détection ratée n'empêche pas l'utilisateur de
    continuer — avertissement, pas verrou technique dur."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", "-i", "decodium"], capture_output=True, timeout=2
        )
        return out.returncode == 0
    except Exception:
        return False


class TabSSTV:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app

        self.armed = False
        self.rx = None
        self._consumer_thread = None
        self._stop_consumer = threading.Event()

        self._search_buffer = np.zeros(0, dtype=np.float64)
        self._image_buffer = None  # None = pas encore verrouillé sur un VIS
        self._vis_code = None
        self._lines_done = 0
        self._last_vis_search = 0.0
        self._last_decode = 0.0

        self.tci = tci_client.TCIClient(*self._tci_host_port())
        self.tci.start()

        self._build_ui()
        self.parent.after(500, self._poll_tci_status)

    # ------------------------------------------------------------------
    def _tci_host_port(self):
        try:
            import station_master as sm

            host = sm.CONF.get("TCI", "Host", fallback="127.0.0.1")
            port = sm.CONF.getint("TCI", "Port", fallback=50001)
            return host, port
        except Exception:
            return "127.0.0.1", 50001

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.parent.configure(bg=BG)

        top = tk.Frame(self.parent, bg=PANEL_BG)
        top.pack(fill="x", padx=8, pady=(8, 4))

        self.freq_var = tk.StringVar(value="— kHz")
        tk.Label(
            top,
            textvariable=self.freq_var,
            bg=PANEL_BG,
            fg=ACCENT,
            font=("Consolas", 16, "bold"),
        ).pack(side="left", padx=10, pady=6)

        self.tci_status_var = tk.StringVar(value="⚫ TCI déconnecté")
        tk.Label(
            top,
            textvariable=self.tci_status_var,
            bg=PANEL_BG,
            fg=FG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=10)

        tk.Label(top, text="Slant :", bg=PANEL_BG, fg=FG).pack(
            side="left", padx=(20, 4)
        )
        self.slant_var = tk.DoubleVar(value=1.0)
        tk.Scale(
            top,
            from_=0.95,
            to=1.05,
            resolution=0.001,
            orient="horizontal",
            variable=self.slant_var,
            bg=PANEL_BG,
            fg=FG,
            length=160,
            troughcolor=BORDER,
            highlightthickness=0,
        ).pack(side="left", padx=4)

        self.tx_status_var = tk.StringVar(value="TX Off")
        tk.Label(
            top,
            textvariable=self.tx_status_var,
            bg=PANEL_BG,
            fg="#8b1a1a",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right", padx=10)

        self.arm_btn = tk.Button(
            top,
            text="▶ Arm",
            bg="#238636",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=self._toggle_arm,
        )
        self.arm_btn.pack(side="right", padx=10, pady=6)

        # Waterfall
        wf_frame = tk.Frame(self.parent, bg=BG)
        wf_frame.pack(fill="x", padx=8, pady=4)
        self._wf_array = np.zeros(
            (WATERFALL_HEIGHT, WATERFALL_WIDTH, 3), dtype=np.uint8
        )
        self._wf_photo = ImageTk.PhotoImage(Image.fromarray(self._wf_array))
        self.wf_canvas = tk.Canvas(
            wf_frame,
            width=WATERFALL_WIDTH,
            height=WATERFALL_HEIGHT,
            bg="black",
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.wf_canvas.pack()
        self._wf_canvas_img = self.wf_canvas.create_image(
            0, 0, anchor="nw", image=self._wf_photo
        )

        # Zone bas : sélecteur de mode + image en cours de décodage
        bottom = tk.Frame(self.parent, bg=PANEL_BG)
        bottom.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        left = tk.Frame(bottom, bg=PANEL_BG)
        left.pack(side="left", fill="y", padx=8, pady=8)

        tk.Label(left, text="Mode SSTV :", bg=PANEL_BG, fg=FG).pack(anchor="w")
        self.mode_var = tk.StringVar(value="Auto")
        ttk.Combobox(
            left,
            textvariable=self.mode_var,
            values=SSTV_MODES_UI,
            state="readonly",
            width=16,
        ).pack(anchor="w", pady=(0, 8))

        self.status_var = tk.StringVar(value="Arrêté — appuyez sur Arm pour démarrer")
        tk.Label(
            left,
            textvariable=self.status_var,
            bg=PANEL_BG,
            fg=FG,
            font=("Segoe UI", 9),
            wraplength=180,
            justify="left",
        ).pack(anchor="w")

        self.mode_info_var = tk.StringVar(value="")
        tk.Label(
            left,
            textvariable=self.mode_info_var,
            bg=PANEL_BG,
            fg="#9fb3d1",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(2, 0))

        right = tk.Frame(bottom, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self._img_photo = None
        self.image_label = tk.Label(right, bg="black")
        self.image_label.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Statut TCI (contrôle/statut uniquement — pas l'audio)
    # ------------------------------------------------------------------
    def _poll_tci_status(self):
        try:
            while True:
                kind, detail = self.tci.status_queue.get_nowait()
                if kind == "connected":
                    self.tci_status_var.set("🟢 TCI connecté")
                elif kind == "error":
                    self.tci_status_var.set(f"🔴 TCI : {detail}")
                elif kind == "disconnected":
                    self.tci_status_var.set("⚫ TCI déconnecté")
        except Exception:
            pass
        try:
            while True:
                line = self.tci.text_queue.get_nowait()
                if line.startswith("vfo:0,0,"):
                    try:
                        hz = int(line.split(",")[2].rstrip(";"))
                        self.freq_var.set(f"{hz/1000:.3f} kHz")
                    except Exception:
                        pass
        except Exception:
            pass
        self.parent.after(500, self._poll_tci_status)

    # ------------------------------------------------------------------
    # Arm / Stop
    # ------------------------------------------------------------------
    def _toggle_arm(self):
        if self.armed:
            self._disarm()
        else:
            self._arm()

    def _arm(self):
        if _decodium_running():
            if not messagebox.askyesno(
                "Decodium actif",
                "Decodium semble tourner. Usage exclusif recommandé : les deux "
                "applications ne devraient pas utiliser le flux audio DAX en même "
                "temps. Continuer quand même ?",
            ):
                return

        self.rx = dax_audio.DAXAudioRX()
        try:
            self.rx.start()
        except Exception as e:
            messagebox.showerror(
                "SSTV", f"Impossible de démarrer la capture audio DAX :\n{e}"
            )
            self.rx = None
            return

        self._search_buffer = np.zeros(0, dtype=np.float64)
        self._image_buffer = None
        self._vis_code = None
        self._lines_done = 0
        self._stop_consumer.clear()
        self.armed = True
        self.arm_btn.config(text="■ Stop", bg="#8b1a1a")
        self.status_var.set("Recherche VIS...")
        self.mode_info_var.set("")
        self._consumer_thread = threading.Thread(
            target=self._consumer_loop, daemon=True
        )
        self._consumer_thread.start()

    def _disarm(self):
        self.armed = False
        self._stop_consumer.set()
        if self.rx:
            self.rx.stop()
            self.rx = None
        self.arm_btn.config(text="▶ Arm", bg="#238636")
        self.status_var.set("Arrêté — appuyez sur Arm pour démarrer")

    # ------------------------------------------------------------------
    # Boucle de consommation audio (thread daemon)
    # ------------------------------------------------------------------
    def _consumer_loop(self):
        while not self._stop_consumer.is_set():
            try:
                block = self.rx.audio_queue.get(timeout=0.2)
            except Exception:
                continue
            block = block.astype(np.float64)
            self._update_waterfall(block)

            if self._image_buffer is None:
                self._search_buffer = np.concatenate([self._search_buffer, block])
                max_search = int(dax_audio.SAMPLE_RATE * SEARCH_WINDOW_S)
                if len(self._search_buffer) > max_search:
                    self._search_buffer = self._search_buffer[-max_search:]

                now = time.time()
                if now - self._last_vis_search > VIS_SEARCH_INTERVAL_S:
                    self._last_vis_search = now
                    self._try_lock_vis()
            else:
                self._image_buffer = np.concatenate([self._image_buffer, block])
                now = time.time()
                if now - self._last_decode > DECODE_INTERVAL_S:
                    self._last_decode = now
                    self._try_decode()

    def _try_lock_vis(self):
        manual = self.mode_var.get()
        found = sstvdec.find_vis(self._search_buffer)
        if found is None:
            return
        vis_code, header_end = found
        if manual != "Auto":
            forced = _NAME_TO_VIS.get(manual)
            if forced is not None:
                vis_code = forced
        self._vis_code = vis_code
        self._image_buffer = self._search_buffer[header_end:].copy()
        self._search_buffer = np.zeros(0, dtype=np.float64)
        self._lines_done = 0

        info = sstvdec.mode_info(vis_code)
        name = info[0] if info else f"VIS {vis_code} (inconnu)"
        self.app._tk_queue.put(lambda: self.status_var.set(f"Décodage : {name}"))
        if info:
            mname, dur_s, (w, h) = info
            self.app._tk_queue.put(
                lambda: self.mode_info_var.set(f"{mname} · ≈{dur_s:.0f}s · {w}×{h}")
            )

    def _try_decode(self):
        vis_code = self._vis_code
        slant = self.slant_var.get()

        def on_line(y, image):
            self._lines_done = max(self._lines_done, y + 1)
            self.app._tk_queue.put(lambda img=image.copy(): self._show_image(img))

        if vis_code in sstvdec.MODES:
            mode = sstvdec.MODES[vis_code]
            sstvdec.decode_generic_mode(
                self._image_buffer, mode, slant=slant, on_line=on_line
            )
            total = mode.height
        elif vis_code == sstvdec.ROBOT36_VIS:
            sstvdec.decode_robot36(self._image_buffer, slant=slant, on_line=on_line)
            total = sstvdec.ROBOT36_HEIGHT
        else:
            total = None

        if total is not None and self._lines_done >= total:
            self.app._tk_queue.put(lambda: self.status_var.set("Réception terminée"))
            self._image_buffer = None
            self._vis_code = None
            self._lines_done = 0

    def _update_waterfall(self, block):
        n = len(block)
        if n < 8:
            return
        spec = np.abs(np.fft.rfft(block * np.hanning(n)))
        freqs = np.fft.rfftfreq(n, d=1.0 / dax_audio.SAMPLE_RATE)
        mask = freqs <= WATERFALL_FREQ_MAX
        spec = spec[mask]
        if spec.size == 0:
            return
        spec = np.interp(
            np.linspace(0, spec.size - 1, WATERFALL_WIDTH), np.arange(spec.size), spec
        )
        spec_db = 20 * np.log10(spec + 1e-6)
        lo, hi = -60, 20
        norm = np.clip((spec_db - lo) / (hi - lo), 0, 1)
        row = (norm * 255).astype(np.int32)
        colors = np.zeros((WATERFALL_WIDTH, 3), dtype=np.uint8)
        colors[:, 2] = np.clip(255 - row * 2, 0, 255).astype(np.uint8)
        colors[:, 0] = np.clip(row * 2 - 128, 0, 255).astype(np.uint8)
        colors[:, 1] = row.astype(np.uint8)

        def _apply():
            self._wf_array[1:, :, :] = self._wf_array[:-1, :, :]
            self._wf_array[0, :, :] = colors
            self._wf_photo = ImageTk.PhotoImage(Image.fromarray(self._wf_array))
            self.wf_canvas.itemconfig(self._wf_canvas_img, image=self._wf_photo)

        self.app._tk_queue.put(_apply)

    def _show_image(self, image_array):
        img = Image.fromarray(image_array)
        w = self.image_label.winfo_width() or img.width
        h = self.image_label.winfo_height() or img.height
        img_disp = img.copy()
        img_disp.thumbnail((max(w, 100), max(h, 100)))
        self._img_photo = ImageTk.PhotoImage(img_disp)
        self.image_label.config(image=self._img_photo)
