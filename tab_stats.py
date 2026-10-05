"""
tab_stats.py — Onglet Statistiques (dashboard type Nexus) pour Station Master (ON5AM)

Remplace le contenu de l'ancien onglet "Logbook Analysis" : agrégations SQL
(bande, mode, année, WAS) + résolution DXCC/continent/zone CQ via cty.dat
(réutilise get_country_name/get_cq_zone/get_continent de station_master.py,
aucune logique DXCC dupliquée). Rendu matplotlib en grille de barres
horizontales, dans le même style visuel que le reste de l'application.

Importé par station_master.py : StatsDashboardTab(parent, app=self)
"""

import threading
import tkinter as tk
from collections import Counter, defaultdict

import ttkbootstrap as ttk

# ── Palette — cohérente avec le reste de Station Master ─────────────────────
BG = "#11273f"
BG2 = "#0d1e30"
FG = "#ffffff"
ACCENT = "#00d4ff"
GRID_ALPHA = 0.2

# Ordre "naturel" d'affichage (plus lisible qu'un tri par volume pour ces deux blocs)
_BAND_ORDER = [
    "160m",
    "80m",
    "60m",
    "40m",
    "30m",
    "20m",
    "17m",
    "15m",
    "12m",
    "10m",
    "6m",
    "2m",
    "70cm",
    "23cm",
]

# Cache indicatif -> (entité DXCC, continent, zone CQ), partagé entre rafraîchissements.
# Évite de refaire la recherche de préfixe dans cty.dat pour un indicatif déjà résolu
# (un log réel réutilise beaucoup les mêmes indicatifs : ~13000 uniques pour ~24000 QSO).
_geo_cache = {}


def _resolve_call(sm, call):
    """Résout (entité DXCC, continent, zone CQ) pour un indicatif, avec cache."""
    cached = _geo_cache.get(call)
    if cached is not None:
        return cached
    entity = sm.get_country_name(call) or ""
    continent = sm.get_continent(call) or ""
    zone = sm.get_cq_zone(call) or ""
    result = (entity, continent, zone)
    _geo_cache[call] = result
    return result


def _sort_bands(counter):
    """Trie les bandes dans l'ordre fréquence (160m -> 2m), inconnues en fin par volume."""
    known = [(b, counter[b]) for b in _BAND_ORDER if b in counter]
    unknown = sorted(
        ((b, v) for b, v in counter.items() if b not in _BAND_ORDER),
        key=lambda x: -x[1],
    )
    return known + unknown


def _sort_zones(counter):
    """Trie les zones CQ numériquement (1 -> 40)."""

    def key(item):
        try:
            return (0, int(item[0]))
        except ValueError:
            return (1, item[0])

    return sorted(counter.items(), key=key)


class StatsDashboardTab:
    """Dashboard statistiques du logbook — occupe l'onglet 'Logbook Analysis'."""

    def __init__(self, parent, app):
        self.app = app
        self.conn = app.conn
        self.root = app.root
        self._hdr_vars = {}
        self._build(parent)
        self.root.after(300, self.refresh)

    # ==========================================
    # --- UI ---
    # ==========================================
    def _build(self, parent):
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill="both", expand=True)

        top_bar = tk.Frame(outer, bg=BG)
        top_bar.pack(fill="x", padx=5, pady=5)
        ttk.Button(
            top_bar, text="🔄 Actualiser", command=self.refresh, bootstyle="primary"
        ).pack(side="left")
        self._status_var = tk.StringVar(value="")
        tk.Label(
            top_bar,
            textvariable=self._status_var,
            bg=BG,
            fg="#f39c12",
            font=("Consolas", 9, "bold"),
        ).pack(side="left", padx=10)

        # --- En-tête : résumé global ---
        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", padx=5)
        for key, label in [
            ("total", "📊 QSOs Total"),
            ("calls", "📞 Indicatifs uniques"),
            ("dxcc", "🌍 Entités DXCC travaillées"),
            ("pct", "✅ % Confirmé"),
        ]:
            box = tk.Frame(header, bg=BG2, relief="groove", borderwidth=2)
            box.pack(side="left", fill="x", expand=True, padx=4, pady=4)
            tk.Label(
                box, text=label, fg=ACCENT, bg=BG2, font=("Segoe UI", 9, "bold")
            ).pack(pady=(6, 0))
            var = tk.StringVar(value="--")
            tk.Label(
                box, textvariable=var, fg=FG, bg=BG2, font=("Arial", 16, "bold")
            ).pack(pady=(0, 6))
            self._hdr_vars[key] = var

        # --- Zone graphique (scrollable — la grille de 8 blocs dépasse la hauteur visible) ---
        canvas_holder = tk.Frame(outer, bg=BG)
        canvas_holder.pack(fill="both", expand=True, padx=5, pady=5)
        self._canvas = tk.Canvas(canvas_holder, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(
            canvas_holder, orient="vertical", command=self._canvas.yview
        )
        self._graph_frame = tk.Frame(self._canvas, bg=BG)
        self._graph_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._graph_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # ==========================================
    # --- Données ---
    # ==========================================
    def refresh(self):
        self._status_var.set("⏳ Calcul en cours…")
        threading.Thread(target=self._fetch_stats, daemon=True).start()

    def _fetch_stats(self):
        """Agrégation SQL (bande/mode/année/WAS/confirmations) + résolution DXCC/continent/
        zone CQ par indicatif. Tourne en thread pour ne pas geler l'UI."""
        try:
            import station_master as sm

            c = self.conn.cursor()
            c.execute("SELECT COUNT(*) FROM qsos")
            total = c.fetchone()[0]
            c.execute("SELECT COUNT(DISTINCT callsign) FROM qsos")
            n_calls = c.fetchone()[0]

            # Valeurs considérées comme "confirmé" — mêmes règles que _refresh_dashboard()
            # dans station_master.py (club_stat exclu : ne contient jamais 'Y' en pratique,
            # c'est un suivi d'upload Club Log, pas une confirmation reçue — voir CLAUDE.md).
            LOTW_OK = ("Y", "OK", "YES", "LOTW")
            EQSL_OK = ("Y", "OK", "YES", "EQSL")
            QSL_OK = ("Y", "YES", "R")

            c.execute(
                "SELECT band, mode, qso_date, callsign, lotw_stat, eqsl_stat, qsl_rcvd, state "
                "FROM qsos"
            )
            rows = c.fetchall()

            band_ctr = Counter()
            mode_ctr = Counter()
            year_ctr = Counter()
            state_ctr = Counter()
            entity_ctr = Counter()
            continent_ctr = Counter()
            zone_ctr = Counter()
            entities_worked = set()
            n_lotw = n_eqsl = n_qsl = n_award = 0

            # Pour le panneau "bandes prioritaires" (5BDXCC/5BWAZ/5BWAS) : sets de
            # partenaires CONFIRMÉS (pas juste travaillés) par bande, + le plafond
            # global déjà confirmé toutes bandes confondues.
            band_entity_confirmed = defaultdict(set)
            band_zone_confirmed = defaultdict(set)
            band_state_confirmed = defaultdict(set)
            entities_confirmed_overall = set()
            zones_confirmed_overall = set()
            states_confirmed_overall = set()

            for band, mode, date, call, lotw, eqsl, qslr, state in rows:
                b = (band or "").strip().lower()
                if b:
                    band_ctr[b] += 1
                m = (mode or "").strip().upper()
                if m:
                    mode_ctr[m] += 1
                if date and len(date) >= 4:
                    year_ctr[date[:4]] += 1
                s = (state or "").strip().upper()
                if s in sm.US_STATES:
                    state_ctr[s] += 1

                entity, continent, zone = _resolve_call(
                    sm, (call or "").strip().upper()
                )
                # Entités WAE seulement (Sicily...) : affichées, pas comptées DXCC
                is_dxcc = sm.is_dxcc_entity(entity)
                if entity:
                    entity_ctr[entity] += 1
                if is_dxcc:
                    entities_worked.add(entity)
                if continent:
                    continent_ctr[continent] += 1
                zone_norm = None
                if zone:
                    zone_ctr[zone] += 1
                    try:
                        zone_norm = str(int(zone))  # normalise "05"/"5" -> "5"
                    except ValueError:
                        zone_norm = zone

                is_lotw = (lotw or "").strip().upper() in LOTW_OK
                is_eqsl = (eqsl or "").strip().upper() in EQSL_OK
                is_qsl = (qslr or "").strip().upper() in QSL_OK
                if is_lotw:
                    n_lotw += 1
                if is_eqsl:
                    n_eqsl += 1
                if is_qsl:
                    n_qsl += 1
                is_confirmed = is_lotw or is_eqsl or is_qsl
                if is_confirmed:
                    n_award += 1
                    if is_dxcc:
                        entities_confirmed_overall.add(entity)
                        if b:
                            band_entity_confirmed[b].add(entity)
                    if zone_norm:
                        zones_confirmed_overall.add(zone_norm)
                        if b:
                            band_zone_confirmed[b].add(zone_norm)
                    if s in sm.US_STATES:
                        states_confirmed_overall.add(s)
                        if b:
                            band_state_confirmed[b].add(s)

            ceilings = {
                "dxcc": len(entities_confirmed_overall),
                "waz": len(zones_confirmed_overall),
                "was": len(states_confirmed_overall),
            }
            band_gaps = []
            # WAS_BANDS (station_master.py) plutôt que _BAND_ORDER : c'est déjà la
            # convention "bandes pertinentes pour les diplômes multi-bandes" de
            # l'appli (exclut 2m/70cm/23cm, hors-sujet pour 5BDXCC/5BWAZ/5BWAS).
            for b in sm.WAS_BANDS:
                dxcc_conf = len(band_entity_confirmed.get(b, ()))
                waz_conf = len(band_zone_confirmed.get(b, ()))
                was_conf = len(band_state_confirmed.get(b, ()))
                dxcc_gap = ceilings["dxcc"] - dxcc_conf
                waz_gap = ceilings["waz"] - waz_conf
                was_gap = ceilings["was"] - was_conf
                if dxcc_gap <= 0 and waz_gap <= 0 and was_gap <= 0:
                    continue  # bande déjà à son plafond sur les 3 diplômes
                band_gaps.append(
                    {
                        "band": b,
                        "dxcc_conf": dxcc_conf,
                        "dxcc_gap": dxcc_gap,
                        "dxcc_missing": sorted(
                            entities_confirmed_overall
                            - band_entity_confirmed.get(b, set())
                        ),
                        "waz_conf": waz_conf,
                        "waz_gap": waz_gap,
                        "waz_missing": sorted(
                            zones_confirmed_overall - band_zone_confirmed.get(b, set()),
                            key=lambda z: int(z) if z.isdigit() else 999,
                        ),
                        "was_conf": was_conf,
                        "was_gap": was_gap,
                        "was_missing": sorted(
                            states_confirmed_overall
                            - band_state_confirmed.get(b, set())
                        ),
                    }
                )

            data = {
                "total": total,
                "calls": n_calls,
                "dxcc": len(entities_worked),
                "pct": (n_award / total * 100) if total else 0.0,
                "band": band_ctr,
                "mode": mode_ctr,
                "year": year_ctr,
                "state": state_ctr,
                "entity": entity_ctr,
                "continent": continent_ctr,
                "zone": zone_ctr,
                "confirm": [
                    ("LoTW", n_lotw),
                    ("eQSL", n_eqsl),
                    ("QSL papier", n_qsl),
                    ("Award-grade", n_award),
                ],
                "ceilings": ceilings,
                "band_gaps": band_gaps,
            }
            self.root.after(0, lambda: self._render(data))
        except Exception as e:
            import traceback

            traceback.print_exc()
            self.root.after(
                0, lambda: self._status_var.set(f"⚠️ Erreur stats : {str(e)[:70]}")
            )

    # ==========================================
    # --- Rendu ---
    # ==========================================
    def _render(self, data):
        self._status_var.set(f"✅ Mis à jour — {data['total']} QSO")
        self._hdr_vars["total"].set(f"{data['total']:,}".replace(",", " "))
        self._hdr_vars["calls"].set(f"{data['calls']:,}".replace(",", " "))
        self._hdr_vars["dxcc"].set(str(data["dxcc"]))
        self._hdr_vars["pct"].set(f"{data['pct']:.1f}%")

        for w in self._graph_frame.winfo_children():
            w.destroy()

        if data["total"] == 0:
            tk.Label(
                self._graph_frame, text="Aucun QSO dans le journal.", bg=BG, fg=FG
            ).pack(pady=40)
            return

        try:
            import matplotlib

            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            tk.Label(
                self._graph_frame,
                text="⚠️ matplotlib non installé.\nInstallez-le avec : pip install matplotlib",
                bg=BG,
                fg="#f39c12",
                font=("Segoe UI", 11, "bold"),
                justify="center",
            ).pack(pady=40)
            return

        fig = Figure(figsize=(13, 22), dpi=95, facecolor=BG)
        axes = fig.subplots(4, 2)
        fig.subplots_adjust(
            hspace=0.55, wspace=0.35, left=0.16, right=0.97, top=0.97, bottom=0.03
        )

        blocks = [
            (axes[0][0], "Par bande", _sort_bands(data["band"])),
            (axes[0][1], "Par mode (top 12)", data["mode"].most_common(12)),
            (axes[1][0], "Par année", sorted(data["year"].items())),
            (axes[1][1], "Top entités DXCC (top 15)", data["entity"].most_common(15)),
            (
                axes[2][0],
                "Most-worked states — WAS (top 15)",
                data["state"].most_common(15),
            ),
            (axes[2][1], "Confirmations", data["confirm"]),
            (
                axes[3][0],
                "Par zone CQ",
                [(f"CQ {z}", n) for z, n in _sort_zones(data["zone"])],
            ),
            (axes[3][1], "Par continent", data["continent"].most_common()),
        ]
        for ax, title, items in blocks:
            self._draw_hbar(ax, items, title)

        canvas = FigureCanvasTkAgg(fig, master=self._graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        if data.get("band_gaps"):
            self._build_band_priority_panel(data)

        self._graph_frame.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _build_band_priority_panel(self, data):
        """Panneau 'bandes prioritaires' pour les diplômes multi-bandes
        (5BDXCC/5BWAZ/5BWAS) : pour chaque bande, combien de partenaires déjà
        confirmés ailleurs manquent encore SUR cette bande précise — ce sont
        des cases jouables (contact déjà établi et confirmé sur une autre
        bande, donc a priori disposé à confirmer à nouveau)."""
        ceilings = data["ceilings"]
        gaps = sorted(
            data["band_gaps"],
            key=lambda g: g["dxcc_gap"] + g["waz_gap"] + g["was_gap"],
            reverse=True,
        )

        panel = tk.Frame(self._graph_frame, bg=BG2, relief="groove", borderwidth=2)
        panel.pack(fill="x", padx=4, pady=(4, 12))

        tk.Label(
            panel,
            text="🎯 Bandes prioritaires pour les diplômes multi-bandes (5BDXCC / 5BWAZ / 5BWAS)",
            bg=BG2,
            fg="#f39c12",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 2))
        tk.Label(
            panel,
            text=(
                f"Plafond déjà confirmé toutes bandes confondues : DXCC {ceilings['dxcc']} · "
                f"WAZ {ceilings['waz']} · WAS {ceilings['was']}. Le \"manque\" compte des "
                f"partenaires DÉJÀ confirmés sur une autre bande — donc a priori joignables "
                f"à nouveau sur celle-ci pour valider une case supplémentaire."
            ),
            bg=BG2,
            fg="#9fb3d1",
            font=("Segoe UI", 8),
            wraplength=1000,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 8))

        header = tk.Frame(panel, bg=BG2)
        header.pack(fill="x", padx=8)
        for txt, w in [
            ("Bande", 8),
            ("DXCC (confirmé/plafond)", 24),
            ("WAZ (confirmé/plafond)", 24),
            ("WAS (confirmé/plafond)", 24),
        ]:
            tk.Label(
                header,
                text=txt,
                bg=BG2,
                fg="#888",
                font=("Consolas", 9, "bold"),
                width=w,
                anchor="w",
            ).pack(side="left")

        for g in gaps[:10]:
            row = tk.Frame(panel, bg=BG2)
            row.pack(fill="x", padx=8, pady=1)
            tk.Label(
                row,
                text=g["band"],
                bg=BG2,
                fg=FG,
                font=("Consolas", 9, "bold"),
                width=8,
                anchor="w",
            ).pack(side="left")
            for key, ceil_key in [("dxcc", "dxcc"), ("waz", "waz"), ("was", "was")]:
                conf = g[f"{key}_conf"]
                ceil = ceilings[ceil_key]
                gap = g[f"{key}_gap"]
                color = (
                    "#e74c3c"
                    if ceil and gap > ceil * 0.5
                    else ("#f39c12" if gap > 0 else "#2ecc71")
                )
                tk.Label(
                    row,
                    text=f"{conf}/{ceil}  (-{gap})",
                    bg=BG2,
                    fg=color,
                    font=("Consolas", 9),
                    width=24,
                    anchor="w",
                ).pack(side="left")

        if gaps:
            top = gaps[0]
            detail_lines = [f"👉 Priorité n°1 : {top['band']}"]
            for label, key in [
                ("WAS manquants", "was_missing"),
                ("Zones CQ manquantes", "waz_missing"),
                ("Entités DXCC manquantes", "dxcc_missing"),
            ]:
                missing = top[key]
                if not missing:
                    continue
                shown = missing[:15]
                extra = f" (+{len(missing) - 15} autres)" if len(missing) > 15 else ""
                detail_lines.append(
                    f"   {label} : {', '.join(str(m) for m in shown)}{extra}"
                )

            tk.Label(
                panel,
                text="\n".join(detail_lines),
                bg=BG2,
                fg="#e8e8e8",
                font=("Consolas", 9),
                justify="left",
                anchor="w",
                wraplength=1000,
            ).pack(anchor="w", padx=8, pady=(8, 10))

    @staticmethod
    def _draw_hbar(ax, items, title):
        """Dessine un bloc de barres horizontales (le plus grand en haut)."""
        ax.set_facecolor(BG2)
        ax.set_title(title, color=ACCENT, fontsize=11, fontweight="bold", pad=8)
        for spine in ax.spines.values():
            spine.set_color("#22354f")

        if not items:
            ax.text(
                0.5,
                0.5,
                "Aucune donnée",
                ha="center",
                va="center",
                color="#556677",
                transform=ax.transAxes,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            return

        labels = [str(k) for k, v in items][::-1]
        values = [v for k, v in items][::-1]
        bars = ax.barh(labels, values, color=ACCENT, edgecolor=BG2, height=0.65)
        ax.tick_params(colors=FG, labelsize=8)
        ax.grid(True, axis="x", alpha=GRID_ALPHA, color=FG)
        maxv = max(values) if values else 1
        ax.set_xlim(0, maxv * 1.15)
        for bar, v in zip(bars, values):
            ax.text(
                bar.get_width() + maxv * 0.015,
                bar.get_y() + bar.get_height() / 2,
                f"{v}",
                va="center",
                ha="left",
                color=FG,
                fontsize=7,
            )
