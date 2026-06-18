"""
contest_tab.py  –  Onglet "Contests" pour Station Master (ON5AM)
Source : WA7BNM Contest Calendar RSS  (https://www.contestcalendar.com)
Usage  : from contest_tab import ContestTab
         tab = ContestTab(notebook)
         notebook.add(tab.frame, text="Contests")
"""

import tkinter as tk
from tkinter import ttk
import threading
import webbrowser
import xml.etree.ElementTree as ET
import urllib.request
from datetime import datetime
import re

# ── Palette harmonisée Station Master ──────────────────────────────────────
BG_DARK      = "#1a1a2e"
BG_CARD      = "#16213e"
BG_HEADER    = "#0f3460"
FG_TEXT      = "#e0e0e0"
FG_DIM       = "#888888"
ORANGE       = "#e07b39"       # accent principal
ORANGE_DARK  = "#c0622a"
RED          = "#f85149"
RED_DARK     = "#c0392b"
GREEN        = "#3fb950"
CYAN         = "#3daee9"
YELLOW       = "#d4a017"
TOGGLE_ON_BG = "#e07b39"
TOGGLE_ON_FG = "#ffffff"
TOGGLE_OFF_BG= "#2a2a4a"
TOGGLE_OFF_FG= "#aaaaaa"
FONT_MAIN    = ("Consolas", 10)
FONT_TITLE   = ("Consolas", 11, "bold")
FONT_SMALL   = ("Consolas", 9)
FONT_HEADER  = ("Consolas", 10, "bold")

# ── URL du flux RSS ─────────────────────────────────────────────────────────
RSS_URL = "https://www.contestcalendar.com/calendar.rss"

# ── Mots-clés de détection des modes ───────────────────────────────────────
MODE_KEYWORDS = {
    "CW":   ["cw", "cwops", "cwtips", "icwc", "skcc", "straight key", "cwt"],
    "FT8":  ["ft8"],
    "FT4":  ["ft4"],
    "RTTY": ["rtty", "baudot"],
    "SSB":  ["ssb", "phone", "sideband"],
    "Mixed":["mixed", "all mode"],
}

# Couleur associée à chaque mode pour les badges
MODE_COLORS = {
    "CW":    ("#d4a017", "#1a1a2e"),   # jaune
    "FT8":   ("#3daee9", "#1a1a2e"),   # cyan
    "FT4":   ("#2e9bd4", "#ffffff"),   # cyan foncé
    "RTTY":  ("#e07b39", "#ffffff"),   # orange
    "SSB":   ("#3fb950", "#1a1a2e"),   # vert
    "Mixed": ("#9b59b6", "#ffffff"),   # violet
    "Other": ("#555555", "#cccccc"),   # gris
}


def detect_modes(text: str) -> list[str]:
    """Détecte les modes présents dans un texte (titre + description)."""
    text_lower = text.lower()
    found = []
    for mode, keywords in MODE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(mode)
    return found if found else ["Other"]


def parse_rss(xml_text: str) -> list[dict]:
    """Parse le flux RSS WA7BNM et retourne une liste de contests."""
    contests = []
    try:
        root = ET.fromstring(xml_text)
        # Namespace optionnel
        ns = ""
        channel = root.find("channel")
        if channel is None:
            return contests
        for item in channel.findall("item"):
            def get(tag):
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else ""
            title       = get("title")
            link        = get("link")
            description = get("description")
            pub_date    = get("pubDate")
            # Nettoie les balises HTML basiques dans la description
            desc_clean  = re.sub(r"<[^>]+>", " ", description).strip()
            desc_clean  = re.sub(r"\s+", " ", desc_clean)
            # Détection du mode depuis titre + description
            modes = detect_modes(title + " " + desc_clean)
            # Extraction date/heure depuis la description (format "0300Z-0400Z, May 7")
            date_match  = re.search(
                r"(\d{4}Z[-–]\d{4}Z[^<\n]*)",
                description
            )
            contest_date = date_match.group(1).strip() if date_match else pub_date
            contests.append({
                "title":       title,
                "link":        link,
                "description": desc_clean,
                "date":        contest_date,
                "modes":       modes,
                "pub_date":    pub_date,
            })
    except ET.ParseError:
        pass
    return contests


class ContestTab:
    """Widget principal de l'onglet Contests."""

    def __init__(self, parent):
        self.parent = parent
        self._all_contests: list[dict] = []
        self._active_modes: set[str]   = set()   # vide = tout afficher
        self._loading = False

        self._build_ui(self.parent)
        self._refresh()

    # ── Construction de l'interface ────────────────────────────────────────

    def _build_ui(self, parent):
        self.frame = parent
        self.frame.configure(bg=BG_DARK)

        # Barre du haut ─────────────────────────────────────────────────────
        top_bar = tk.Frame(self.frame, bg=BG_HEADER, pady=6)
        top_bar.pack(fill="x", side="top")

        # Titre
        tk.Label(
            top_bar, text="🏆  Contests Calendar",
            bg=BG_HEADER, fg=ORANGE,
            font=("Consolas", 13, "bold")
        ).pack(side="left", padx=12)

        # Bouton Refresh
        self._btn_refresh = tk.Button(
            top_bar, text="⟳  Refresh",
            bg=ORANGE_DARK, fg="#ffffff",
            font=FONT_SMALL, relief="flat",
            activebackground=ORANGE, activeforeground="#ffffff",
            cursor="hand2", command=self._refresh
        )
        self._btn_refresh.pack(side="right", padx=10, pady=2)

        # Lien source
        src_lbl = tk.Label(
            top_bar, text="WA7BNM Contest Calendar",
            bg=BG_HEADER, fg=CYAN,
            font=FONT_SMALL, cursor="hand2"
        )
        src_lbl.pack(side="right", padx=4)
        src_lbl.bind("<Button-1>",
                     lambda e: webbrowser.open("https://www.contestcalendar.com"))

        # Barre des filtres modes ───────────────────────────────────────────
        filter_bar = tk.Frame(self.frame, bg=BG_DARK, pady=6)
        filter_bar.pack(fill="x", side="top", padx=10)

        tk.Label(
            filter_bar, text="Modes :", bg=BG_DARK, fg=FG_DIM,
            font=FONT_SMALL
        ).pack(side="left", padx=(0, 8))

        self._mode_buttons: dict[str, tk.Button] = {}
        for mode in ["CW", "FT8", "FT4", "RTTY", "SSB", "Mixed"]:
            btn = tk.Button(
                filter_bar, text=mode,
                bg=TOGGLE_OFF_BG, fg=TOGGLE_OFF_FG,
                font=FONT_SMALL, relief="flat",
                padx=8, pady=3, cursor="hand2",
                command=lambda m=mode: self._toggle_mode(m)
            )
            btn.pack(side="left", padx=3)
            self._mode_buttons[mode] = btn

        # Bouton ALL
        self._btn_all = tk.Button(
            filter_bar, text="ALL",
            bg=TOGGLE_ON_BG, fg=TOGGLE_ON_FG,
            font=("Consolas", 9, "bold"), relief="flat",
            padx=8, pady=3, cursor="hand2",
            command=self._clear_filters
        )
        self._btn_all.pack(side="left", padx=3)

        # Compteur
        self._count_var = tk.StringVar(value="")
        tk.Label(
            filter_bar, textvariable=self._count_var,
            bg=BG_DARK, fg=FG_DIM, font=FONT_SMALL
        ).pack(side="right", padx=6)

        # Zone de liste scrollable ─────────────────────────────────────────
        list_frame = tk.Frame(self.frame, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        scrollbar = tk.Scrollbar(list_frame, orient="vertical",
                                 bg=BG_DARK, troughcolor=BG_CARD)
        scrollbar.pack(side="right", fill="y")

        self._canvas = tk.Canvas(
            list_frame, bg=BG_DARK,
            yscrollcommand=scrollbar.set,
            highlightthickness=0
        )
        self._canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._canvas.yview)

        self._list_inner = tk.Frame(self._canvas, bg=BG_DARK)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw"
        )

        self._list_inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        # Molette souris
        self._canvas.bind("<MouseWheel>",
                          lambda e: self._canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._canvas.bind("<Button-4>",
                          lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>",
                          lambda e: self._canvas.yview_scroll(1, "units"))

        # Label de statut (chargement / erreur)
        self._status_var = tk.StringVar(value="Chargement…")
        self._status_lbl = tk.Label(
            self._list_inner, textvariable=self._status_var,
            bg=BG_DARK, fg=FG_DIM, font=FONT_SMALL
        )
        self._status_lbl.pack(pady=20)

    # ── Événements canvas ──────────────────────────────────────────────────

    def _on_inner_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    # ── Filtres modes ──────────────────────────────────────────────────────

    def _toggle_mode(self, mode: str):
        if mode in self._active_modes:
            self._active_modes.discard(mode)
        else:
            self._active_modes.add(mode)
        self._update_toggle_buttons()
        self._render_contests()

    def _clear_filters(self):
        self._active_modes.clear()
        self._update_toggle_buttons()
        self._render_contests()

    def _update_toggle_buttons(self):
        no_filter = len(self._active_modes) == 0
        # Bouton ALL
        self._btn_all.config(
            bg=TOGGLE_ON_BG if no_filter else TOGGLE_OFF_BG,
            fg=TOGGLE_ON_FG if no_filter else TOGGLE_OFF_FG,
        )
        for mode, btn in self._mode_buttons.items():
            active = mode in self._active_modes
            btn.config(
                bg=TOGGLE_ON_BG if active else TOGGLE_OFF_BG,
                fg=TOGGLE_ON_FG if active else TOGGLE_OFF_FG,
            )

    # ── Chargement RSS ─────────────────────────────────────────────────────

    def _refresh(self):
        if self._loading:
            return
        self._loading = True
        self._btn_refresh.config(state="disabled", text="…")
        self._status_var.set("Connexion à WA7BNM Contest Calendar…")
        # Vide la liste
        for w in self._list_inner.winfo_children():
            if w != self._status_lbl:
                w.destroy()
        threading.Thread(target=self._fetch_rss, daemon=True).start()

    def _fetch_rss(self):
        try:
            req = urllib.request.Request(
                RSS_URL,
                headers={"User-Agent": "Station Master / ON5AM contest-tab 1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_bytes = resp.read()
            contests = parse_rss(xml_bytes.decode("utf-8", errors="replace"))
            self.frame.after(0, self._on_rss_loaded, contests, None)
        except Exception as exc:
            self.frame.after(0, self._on_rss_loaded, [], str(exc))

    def _on_rss_loaded(self, contests: list[dict], error: str | None):
        self._loading = False
        self._btn_refresh.config(state="normal", text="⟳  Refresh")
        if error:
            self._status_var.set(f"❌  Erreur : {error}")
            return
        if not contests:
            self._status_var.set("Aucun contest trouvé dans le flux RSS.")
            return
        self._all_contests = contests
        self._status_var.set("")
        self._render_contests()

    # ── Rendu de la liste ──────────────────────────────────────────────────

    def _render_contests(self):
        # Supprime les cartes existantes (sauf status label)
        for w in self._list_inner.winfo_children():
            if w is not self._status_lbl:
                w.destroy()

        # Filtre selon les modes actifs
        if self._active_modes:
            visible = [
                c for c in self._all_contests
                if any(m in self._active_modes for m in c["modes"])
            ]
        else:
            visible = self._all_contests

        self._count_var.set(f"{len(visible)} contest(s)")

        if not visible:
            self._status_var.set("Aucun contest pour les modes sélectionnés.")
            return
        self._status_var.set("")

        for contest in visible:
            self._build_card(contest)

        self._on_inner_configure()

    def _build_card(self, contest: dict):
        """Crée une carte contest dans la liste."""
        card = tk.Frame(
            self._list_inner,
            bg=BG_CARD, bd=0,
            highlightbackground=BG_HEADER,
            highlightthickness=1
        )
        card.pack(fill="x", padx=6, pady=3, ipady=4)

        # ── Ligne 1 : titre + badges modes ──────────────────────────────
        row1 = tk.Frame(card, bg=BG_CARD)
        row1.pack(fill="x", padx=8, pady=(6, 2))

        title_lbl = tk.Label(
            row1, text=contest["title"],
            bg=BG_CARD, fg=ORANGE,
            font=FONT_TITLE, anchor="w", cursor="hand2"
        )
        title_lbl.pack(side="left")
        title_lbl.bind(
            "<Button-1>",
            lambda e, url=contest["link"]: webbrowser.open(url) if url else None
        )

        # Badges modes (à droite)
        for mode in contest["modes"]:
            mbg, mfg = MODE_COLORS.get(mode, MODE_COLORS["Other"])
            tk.Label(
                row1, text=f" {mode} ",
                bg=mbg, fg=mfg,
                font=("Consolas", 8, "bold"),
                relief="flat", padx=3, pady=1
            ).pack(side="right", padx=2)

        # ── Ligne 2 : date ───────────────────────────────────────────────
        if contest["date"]:
            row2 = tk.Frame(card, bg=BG_CARD)
            row2.pack(fill="x", padx=8, pady=1)
            tk.Label(
                row2, text="📅  " + contest["date"],
                bg=BG_CARD, fg=FG_DIM,
                font=FONT_SMALL, anchor="w"
            ).pack(side="left")

        # ── Ligne 3 : description (masquée par défaut, toggle) ──────────
        desc_frame = tk.Frame(card, bg=BG_CARD)
        desc_var   = tk.BooleanVar(value=False)

        def toggle_desc(frame=desc_frame, var=desc_var,
                        text=contest["description"]):
            var.set(not var.get())
            if var.get():
                frame.pack(fill="x", padx=8, pady=(2, 2))
            else:
                frame.pack_forget()

        if contest["description"]:
            tk.Label(
                desc_frame,
                text=contest["description"],
                bg=BG_CARD, fg=FG_TEXT,
                font=FONT_SMALL, anchor="w",
                wraplength=700, justify="left"
            ).pack(fill="x")

        # ── Ligne actions ────────────────────────────────────────────────
        row_act = tk.Frame(card, bg=BG_CARD)
        row_act.pack(fill="x", padx=8, pady=(2, 5))

        if contest["description"]:
            tk.Button(
                row_act, text="▼ Détails",
                bg=BG_DARK, fg=CYAN,
                font=FONT_SMALL, relief="flat",
                cursor="hand2", command=toggle_desc
            ).pack(side="left", padx=(0, 6))

        if contest["link"]:
            tk.Button(
                row_act, text="🔗 View full details",
                bg=BG_DARK, fg=CYAN,
                font=FONT_SMALL, relief="flat",
                cursor="hand2",
                command=lambda url=contest["link"]: webbrowser.open(url)
            ).pack(side="left")


# ── Test standalone ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Contest Tab – Test ON5AM")
    root.geometry("900x650")
    root.configure(bg=BG_DARK)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    t = tk.Frame(nb, bg=BG_DARK)
    nb.add(t, text="🏆 Contests")
    tab = ContestTab(t)

    root.mainloop()
