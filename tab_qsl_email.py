"""
tab_qsl_email.py — Onglet QSL Email pour Station Master
ON5AM Station Master V21.0

Affiche tous les QSOs avec statut d'envoi email QSL.
Double-clic sur une ligne → fenêtre d'envoi via QSLEmailer (tab_qsl.py).
"""
import tkinter as tk
from tkinter import ttk

# ── Palette (idem tab_ft8_monitor / station_master) ──────────────────────────
BG     = "#0d1117"
BG2    = "#161b22"
BG3    = "#21262d"
FG     = "#e6edf3"
GREEN  = "#3fb950"
GRAY   = "#484f58"


class QSLEmailTab:
    """
    Onglet QSL Email.

    Paramètres
    ----------
    parent      : frame tk parent
    app         : référence à StationMasterApp
    get_country : get_country_name(callsign) → str  (injecté depuis station_master)
    """

    def __init__(self, parent, app, get_country=None):
        self.app          = app
        self._get_country = get_country or (lambda _: "")
        self._filter_var  = tk.StringVar(value="Tous")

        self._ensure_column()
        self._build_ui(parent)
        app.root.after(800, self.refresh)

    # ── Migration DB ──────────────────────────────────────────────────────────
    def _ensure_column(self):
        """Ajoute qsl_email_sent à la table qsos si absente."""
        try:
            self.app.conn.execute(
                "ALTER TABLE qsos ADD COLUMN qsl_email_sent INTEGER DEFAULT 0"
            )
            self.app.conn.commit()
        except Exception:
            pass  # colonne déjà présente

    # ── Construction UI ───────────────────────────────────────────────────────
    def _build_ui(self, parent):
        parent.configure(bg=BG)

        # ── Barre de contrôle ────────────────────────────────────────────────
        ctrl = tk.Frame(parent, bg=BG2, pady=5)
        ctrl.pack(fill="x", padx=4, pady=(4, 0))

        tk.Label(ctrl, text="Filtre :", bg=BG2, fg=FG,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=(10, 4))

        for val in ("Tous", "Non envoyés", "Envoyés"):
            tk.Radiobutton(
                ctrl, text=val, variable=self._filter_var, value=val,
                bg=BG2, fg=FG, selectcolor=BG3,
                activebackground=BG2, activeforeground=FG,
                font=("Consolas", 10), command=self.refresh,
            ).pack(side="left", padx=6)

        tk.Label(ctrl, text="— double-clic pour envoyer",
                 bg=BG2, fg=GRAY, font=("Consolas", 8, "italic")
                 ).pack(side="left", padx=12)

        self._lbl_count = tk.Label(ctrl, text="", bg=BG2, fg=GRAY,
                                   font=("Consolas", 9))
        self._lbl_count.pack(side="right", padx=10)

        tk.Button(
            ctrl, text="🔄 Rafraîchir", bg=BG3, fg=FG, relief="flat",
            font=("Consolas", 9), cursor="hand2", padx=6,
            activebackground=BG2, command=self.refresh,
        ).pack(side="right", padx=4)

        # ── Tableau ──────────────────────────────────────────────────────────
        tree_fr = tk.Frame(parent, bg=BG)
        tree_fr.pack(fill="both", expand=True, padx=4, pady=(4, 4))

        try:
            _st = ttk.Style()
            _st.configure("QSLEmail.Treeview",
                          background=BG, foreground=FG,
                          fieldbackground=BG, rowheight=22,
                          font=("Consolas", 9))
            _st.configure("QSLEmail.Treeview.Heading",
                          background=BG3, foreground="#8b949e",
                          font=("Consolas", 9, "bold"))
            _st.map("QSLEmail.Treeview",
                    background=[("selected", "#1c4966")],
                    foreground=[("selected", "#ffffff")])
            _style = "QSLEmail.Treeview"
        except Exception:
            _style = "Treeview"

        cols = ("id", "date", "call", "band", "mode", "pays", "email_sent")
        self._tree = ttk.Treeview(tree_fr, columns=cols, show="headings",
                                  selectmode="browse", style=_style)

        hdrs = [
            ("id",         "ID",           0,    "center"),
            ("date",       "Date",         95,   "center"),
            ("call",       "Callsign",     110,  "w"),
            ("band",       "Bande",        65,   "center"),
            ("mode",       "Mode",         65,   "center"),
            ("pays",       "Pays",         165,  "w"),
            ("email_sent", "Email envoyé", 105,  "center"),
        ]
        for col, txt, w, anc in hdrs:
            self._tree.heading(col, text=txt)
            self._tree.column(col, width=w, anchor=anc,
                              stretch=(col == "pays"))
        self._tree.column("id", width=0, stretch=tk.NO)

        vsb = ttk.Scrollbar(tree_fr, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)

        self._tree.tag_configure("sent",     background="#0d2e18", foreground=GREEN)
        self._tree.tag_configure("unsent_a", background=BG,        foreground=FG)
        self._tree.tag_configure("unsent_b", background=BG2,       foreground=FG)

        self._tree.bind("<Double-1>", self._on_double_click)

    # ── Données ───────────────────────────────────────────────────────────────
    def refresh(self):
        """Recharge depuis la DB et applique le filtre actif."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        filt = self._filter_var.get()
        sql = (
            "SELECT id, qso_date, callsign, band, mode, qsl_email_sent "
            "FROM qsos WHERE qso_date != '' "
        )
        if filt == "Envoyés":
            sql += "AND qsl_email_sent = 1 "
        elif filt == "Non envoyés":
            sql += "AND (qsl_email_sent IS NULL OR qsl_email_sent = 0) "
        sql += "ORDER BY qso_date DESC, time_on DESC"

        try:
            rows = self.app.conn.cursor().execute(sql).fetchall()
        except Exception as e:
            print(f"[QSLEmail] DB error: {e}")
            return

        unsent_idx = 0
        for (qso_id, date_s, call, band, mode, sent) in rows:
            country = ""
            if call:
                try:
                    c = self._get_country(call) or ""
                    if not c.startswith("??"):
                        country = c
                except Exception:
                    pass

            sent_lbl = "✅ Oui" if sent else "—"
            if sent:
                tag = "sent"
            else:
                tag = "unsent_a" if unsent_idx % 2 == 0 else "unsent_b"
                unsent_idx += 1

            self._tree.insert("", "end",
                              values=(qso_id,
                                      date_s[:10] if date_s else "",
                                      call  or "",
                                      band  or "",
                                      mode  or "",
                                      country,
                                      sent_lbl),
                              tags=(tag,))

        total      = len(rows)
        sent_count = sum(1 for r in rows if r[5])
        self._lbl_count.config(
            text=f"{total} QSO(s)  •  {sent_count} envoyés  •  {total - sent_count} en attente"
        )

    # ── Interaction ───────────────────────────────────────────────────────────
    def _on_double_click(self, _event):
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0], "values")
        if not vals:
            return
        try:
            self._launch_send_dialog(int(vals[0]))
        except (ValueError, IndexError):
            pass

    def _launch_send_dialog(self, qso_id: int):
        """Charge le QSO depuis la DB et ouvre la fenêtre QSLEmailer."""
        emailer = getattr(self.app, "_qsl_emailer", None)
        if emailer is None:
            from tkinter import messagebox
            messagebox.showerror("QSL Email", "QSLEmailer non disponible.")
            return

        try:
            row = self.app.conn.cursor().execute(
                "SELECT id, qso_date, time_on, callsign, name, qth, "
                "band, mode, rst_sent, rst_rcvd, distance, freq "
                "FROM qsos WHERE id=?", (qso_id,)
            ).fetchone()
        except Exception as e:
            print(f"[QSLEmail] DB error: {e}")
            return

        if not row:
            return

        (rid, date_s, time_s, call, name, qth,
         band, mode, rst_s, rst_r, dist, freq) = row

        qso = {
            "id":    rid,
            "date":  date_s or "",
            "time":  time_s or "",
            "call":  call   or "",
            "name":  name   or "",
            "qth":   qth    or "",
            "band":  band   or "",
            "mode":  mode   or "",
            "rst_s": rst_s  or "",
            "rst_r": rst_r  or "",
            "dist":  dist   or "",
            "ant":   "",
            "freq":  freq   or "",
        }

        conf = emailer._get_conf()
        smtp_user, smtp_pass, smtp_host, smtp_port = emailer._get_smtp_creds(conf)

        if not smtp_user or not smtp_pass:
            from tkinter import messagebox
            messagebox.showerror("Config email",
                "Identifiants SMTP manquants.\n\n"
                "Ajoutez dans config.ini :\n\n"
                "[GMAIL]\nemail = on5amplus@gmail.com\n"
                "app_password = xxxx xxxx xxxx xxxx")
            return

        dest_email = ""
        lang       = "en"
        try:
            from tab_qsl import _qrz_email, _get_lang
            dest_email = _qrz_email(call, conf)
            lang       = _get_lang(call)
        except Exception as e:
            print(f"[QRZ] Lookup échoué : {e}")

        emailer._open_confirm_win(
            qso, lang, dest_email, conf,
            smtp_user, smtp_pass, smtp_host, smtp_port,
        )
        # Refresh différé : laisse le thread SMTP background terminer
        self.app.root.after(3500, self.refresh)
