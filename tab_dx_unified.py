import tkinter as tk
from tkinter import ttk

# ── Serveurs DX Cluster préconfigurés ────────────────────────────────────────
SERVERS = [
    ("ON0DXK — Belgique",     "on0dxk.dyndns.org",  8000),
    ("F1LED — France (RBN+POTA)", "cluster.f1led.fr", 7300),
    ("Custom...",             "",                    7300),
]

BG     = "#11273f"
BG_HDR = "#0a1628"
ACCENT = "#4fc3f7"
FG_DIM = "#8b949e"

# ── Classe principale ─────────────────────────────────────────────────────────

class TabDXUnified(tk.Frame):
    """
    Onglet DX Live unifié.

    Layout :
    ┌─ Barre serveur ──────────────────────────────────────────────┐
    ├─────────────────────────────┬────────────────────────────────┤
    │   DX CLUSTER (gauche ~60%)  │   DXPÉDITIONS (droite ~40%)   │
    │   (code existant dans app)  │   (tab_dxpeditions.py)        │
    └─────────────────────────────┴────────────────────────────────┘
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.pack(fill="both", expand=True)
        self.app = app
        self._build()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        self._build_server_bar()
        self._build_panels()

    def _build_server_bar(self):
        """Barre de sélection / connexion serveur cluster."""
        bar = tk.Frame(self, bg=BG_HDR, height=34)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Icône
        tk.Label(bar, text="🌐", bg=BG_HDR,
                 font=("Segoe UI Emoji", 11)).pack(side="left", padx=(8, 2), pady=5)

        tk.Label(bar, text="Serveur :", bg=BG_HDR, fg=FG_DIM,
                 font=("Consolas", 9)).pack(side="left", padx=(0, 4))

        # Combobox serveurs préconfigurés
        self._srv_var = tk.StringVar(value=SERVERS[0][0])
        self._srv_cb  = ttk.Combobox(
            bar, textvariable=self._srv_var,
            values=[s[0] for s in SERVERS],
            width=26, state="readonly", font=("Consolas", 9))
        self._srv_cb.pack(side="left", padx=4, pady=5)
        self._srv_cb.bind("<<ComboboxSelected>>", self._on_server_select)

        # Séparateur
        tk.Label(bar, text="|", bg=BG_HDR, fg="#333",
                 font=("Consolas", 10)).pack(side="left", padx=6)

        # Champ custom host
        tk.Label(bar, text="Host :", bg=BG_HDR, fg=FG_DIM,
                 font=("Consolas", 9)).pack(side="left", padx=(0, 3))
        self._host_var = tk.StringVar(value=SERVERS[0][1])
        tk.Entry(bar, textvariable=self._host_var,
                 bg="#1a2a3a", fg="#c9d1d9", insertbackground="white",
                 font=("Consolas", 9), width=22,
                 relief="flat").pack(side="left", padx=2, pady=6)

        # Port
        tk.Label(bar, text="Port :", bg=BG_HDR, fg=FG_DIM,
                 font=("Consolas", 9)).pack(side="left", padx=(6, 3))
        self._port_var = tk.StringVar(value=str(SERVERS[0][2]))
        tk.Entry(bar, textvariable=self._port_var,
                 bg="#1a2a3a", fg="#c9d1d9", insertbackground="white",
                 font=("Consolas", 9), width=6,
                 relief="flat").pack(side="left", padx=2, pady=6)

        # Bouton connecter
        tk.Button(bar, text="🔌 Connecter",
                  bg="#1a3a5c", fg=ACCENT,
                  activebackground="#1e4a6e", activeforeground=ACCENT,
                  relief="flat", bd=0, cursor="hand2",
                  font=("Consolas", 9, "bold"),
                  command=self._connect).pack(side="left", padx=10, pady=5)

        # Statut connexion (droite)
        self._conn_lbl = tk.Label(bar, text="⬤ Déconnecté",
                                  bg=BG_HDR, fg="#f44336",
                                  font=("Consolas", 9))
        self._conn_lbl.pack(side="right", padx=12)

        # Pré-remplir avec la config actuelle de l'app si disponible
        self._load_current_config()

    def _load_current_config(self):
        """Lit la config actuelle de l'app pour pré-remplir les champs."""
        try:
            from configparser import ConfigParser
            import os
            cfg_file = next(
                (f for f in ["config.ini", "mon_logbook.ini", "station_master.ini"]
                 if os.path.exists(f)), None)
            if cfg_file:
                cfg = ConfigParser()
                cfg.read(cfg_file)
                host = cfg.get("DX_CLUSTER", "Host", fallback="")
                port = cfg.get("DX_CLUSTER", "Port", fallback="")
                if host:
                    self._host_var.set(host)
                if port:
                    self._port_var.set(port)
        except Exception:
            pass

        # Essaie aussi depuis les attributs de l'app
        for attr_h, attr_p in [("cluster_host","cluster_port"),
                                ("dx_host","dx_port"),
                                ("_cluster_host","_cluster_port")]:
            if hasattr(self.app, attr_h):
                self._host_var.set(getattr(self.app, attr_h))
                if hasattr(self.app, attr_p):
                    self._port_var.set(str(getattr(self.app, attr_p)))
                break

    def _on_server_select(self, event=None):
        """Met à jour host/port quand on choisit un serveur préconfiguré."""
        name = self._srv_var.get()
        for sname, host, port in SERVERS:
            if sname == name and host:
                self._host_var.set(host)
                self._port_var.set(str(port))
                break

    def _connect(self):
        """Demande à l'app de (re)connecter au serveur sélectionné."""
        host = self._host_var.get().strip()
        try:
            port = int(self._port_var.get().strip())
        except ValueError:
            port = 7300

        if not host:
            return

        # Met à jour les attributs de l'app
        for attr in ["cluster_host", "dx_host", "_cluster_host"]:
            if hasattr(self.app, attr):
                setattr(self.app, attr, host)
        for attr in ["cluster_port", "dx_port", "_cluster_port"]:
            if hasattr(self.app, attr):
                setattr(self.app, attr, port)

        # Appelle la méthode de reconnexion si elle existe
        reconnected = False
        for method in ["_reconnect_cluster", "reconnect_cluster",
                       "_cluster_reconnect", "cluster_connect",
                       "_connect_cluster"]:
            if hasattr(self.app, method):
                try:
                    getattr(self.app, method)(host, port)
                    reconnected = True
                    break
                except TypeError:
                    try:
                        getattr(self.app, method)()
                        reconnected = True
                        break
                    except Exception:
                        pass
                except Exception as e:
                    print(f"[TabDXUnified] {method}: {e}")

        if reconnected:
            self._conn_lbl.config(text=f"⬤ {host}:{port}", fg="#3fb950")
        else:
            self._conn_lbl.config(
                text=f"⬤ {host}:{port} (reconnexion manuelle)",
                fg="#f39c12")

    def _build_panels(self):
        """Crée le split PanedWindow cluster | DXpéditions."""
        self.paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL,
            bg="#0d1a2a", sashwidth=5,
            sashrelief="flat", bd=0)
        self.paned.pack(fill="both", expand=True)

        # ── Panel gauche — DX Cluster (code existant dans app) ──
        self.left = tk.Frame(self.paned, bg=BG)
        self.paned.add(self.left, minsize=480, width=900)

        # ── Panel droit — DXpéditions ──
        self.right = tk.Frame(self.paned, bg=BG)
        self.paned.add(self.right, minsize=320)

        # Construit le cluster dans le panel gauche
        try:
            self.app._build_cluster_tab(self.left)
        except Exception as e:
            tk.Label(self.left,
                     text=f"⚠ Erreur cluster : {e}",
                     bg=BG, fg="#f44336",
                     font=("Consolas", 10)).pack(padx=20, pady=20)

        # Construit les DXpéditions dans le panel droit
        try:
            from tab_dxpeditions import TabDXpeditions
            TabDXpeditions(self.right, app=self.app)
        except Exception as e:
            tk.Label(self.right,
                     text=f"⚠ Erreur DXpéditions : {e}",
                     bg=BG, fg="#f44336",
                     font=("Consolas", 10)).pack(padx=20, pady=20)