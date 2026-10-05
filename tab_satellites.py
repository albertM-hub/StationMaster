"""
tab_satellites.py — Onglet Satellites pour Station Master (ON5AM)
Passages satellites (radioamateur, météo, stations) + carte de passage.
Logique de calcul reprise telle quelle de satellites_passages.py / satellites_carte.py
(prototypes validés en standalone, voir mémo de session).
"""

import tkinter as tk
from tkinter import ttk
import threading

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from satellites_passages import (
    telecharger_tle_si_necessaire,
    charger_satellites,
    calculer_passages,
    regrouper_passages_colocalises,
    MA_LATITUDE as _DEFAUT_LATITUDE,
    MA_LONGITUDE as _DEFAUT_LONGITUDE,
    MON_ALTITUDE_M,
)
from satellites_carte import tracer_passage_sur_carte
from skyfield.api import wgs84

# ------------------------------------------------------------------
# Palette "dark blue-night" - cohérente avec le reste de Station Master
# ------------------------------------------------------------------
COULEUR_FOND = "#0d1526"
COULEUR_FOND_PANNEAU = "#152238"
COULEUR_TEXTE = "#e8eef7"
COULEUR_ACCENT = "#4a9eff"
COULEUR_BORDURE = "#2a3b5c"

COULEUR_ELEVATION_HAUTE = "#3ddc84"
COULEUR_ELEVATION_MOYENNE = "#f5b942"
COULEUR_ELEVATION_BASSE = "#e85c5c"

POLICE_TITRE = ("Segoe UI", 16, "bold")
POLICE_NORMALE = ("Segoe UI", 10)
POLICE_MONO = ("Consolas", 10)


class TabSatellites:
    """Onglet Satellites : tableau des passages + carte au double-clic.

    Args:
        parent         : tk.Frame fourni par le Notebook de station_master.py
        app            : référence vers l'application principale (StationMasterApp)
        grid_to_latlon : callable(grid: str) -> (lat, lon) | None, injectée par
                         station_master.py pour éviter de dupliquer la logique
                         de conversion locator -> lat/lon (cf. tab_dxcc.py).
    """

    def __init__(self, parent, app, grid_to_latlon=None):
        self.parent = parent
        self.app = app
        self._grid_to_latlon = grid_to_latlon or (lambda g: None)

        self.ma_latitude, self.ma_longitude = self._determiner_position()

        self.tous_les_passages = []
        self.passage_par_ligne = {}

        self.parent.configure(bg=COULEUR_FOND)
        self._construire_interface()
        self._lancer_chargement_async()

    # ------------------------------------------------------------------
    # Position observateur — dérivée de MY_GRID (config Station Master)
    # ------------------------------------------------------------------
    def _determiner_position(self):
        """Calcule la position depuis MY_GRID (station_master.py), avec repli
        sur les constantes du prototype si la conversion échoue."""
        try:
            import station_master as _sm
            position = self._grid_to_latlon(_sm.MY_GRID)
            if position:
                return position
        except Exception:
            pass
        return (_DEFAUT_LATITUDE, _DEFAUT_LONGITUDE)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------
    def _construire_interface(self):
        self._appliquer_style_ttk()

        entete = tk.Frame(self.parent, bg=COULEUR_FOND)
        entete.pack(fill="x", padx=16, pady=(14, 6))

        tk.Label(
            entete, text="🛰️  Passages satellites", font=POLICE_TITRE,
            bg=COULEUR_FOND, fg=COULEUR_TEXTE
        ).pack(side="left")

        self.label_position = tk.Label(
            entete, text=f"Position : {self.ma_latitude:.3f}°N, {self.ma_longitude:.3f}°E",
            font=POLICE_NORMALE, bg=COULEUR_FOND, fg=COULEUR_ACCENT
        )
        self.label_position.pack(side="right")

        barre_filtres = tk.Frame(self.parent, bg=COULEUR_FOND_PANNEAU)
        barre_filtres.pack(fill="x", padx=16, pady=(0, 10))

        tk.Label(
            barre_filtres, text="  Catégorie :", font=POLICE_NORMALE,
            bg=COULEUR_FOND_PANNEAU, fg=COULEUR_TEXTE
        ).pack(side="left", pady=8)

        self.filtre_categorie = tk.StringVar(value="Toutes")
        menu_categorie = ttk.Combobox(
            barre_filtres, textvariable=self.filtre_categorie,
            values=["Toutes", "Radioamateur", "Météo", "Stations"],
            state="readonly", width=15
        )
        menu_categorie.pack(side="left", padx=8)
        menu_categorie.bind("<<ComboboxSelected>>", lambda e: self._rafraichir_tableau())

        tk.Label(
            barre_filtres, text="Élévation min :", font=POLICE_NORMALE,
            bg=COULEUR_FOND_PANNEAU, fg=COULEUR_TEXTE
        ).pack(side="left", padx=(20, 0))

        self.filtre_elevation = tk.StringVar(value="10°")
        menu_elevation = ttk.Combobox(
            barre_filtres, textvariable=self.filtre_elevation,
            values=["10°", "20°", "30°", "45°"],
            state="readonly", width=6
        )
        menu_elevation.pack(side="left", padx=8)
        menu_elevation.bind("<<ComboboxSelected>>", lambda e: self._rafraichir_tableau())

        self.bouton_actualiser = tk.Button(
            barre_filtres, text="🔄 Actualiser", font=POLICE_NORMALE,
            bg=COULEUR_ACCENT, fg="#0d1526", activebackground="#6ab4ff",
            relief="flat", padx=14, pady=4, cursor="hand2",
            command=self._lancer_chargement_async
        )
        self.bouton_actualiser.pack(side="right", padx=10, pady=6)

        conteneur_tableau = tk.Frame(self.parent, bg=COULEUR_FOND)
        conteneur_tableau.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        colonnes = ("satellite", "categorie", "aos", "duree", "elevation", "azimut")
        self.tableau = ttk.Treeview(
            conteneur_tableau, columns=colonnes, show="headings", style="Satellites.Treeview"
        )

        entetes = {
            "satellite": ("Satellite", 260),
            "categorie": ("Catégorie", 110),
            "aos": ("Lever (AOS, UTC)", 150),
            "duree": ("Durée", 70),
            "elevation": ("Élév. max", 90),
            "azimut": ("Azimut culm.", 100),
        }
        for cle, (titre, largeur) in entetes.items():
            self.tableau.heading(cle, text=titre)
            self.tableau.column(cle, width=largeur, anchor="w" if cle == "satellite" else "center")

        self.tableau.tag_configure("haute", foreground=COULEUR_ELEVATION_HAUTE)
        self.tableau.tag_configure("moyenne", foreground=COULEUR_ELEVATION_MOYENNE)
        self.tableau.tag_configure("basse", foreground=COULEUR_ELEVATION_BASSE)

        defilement = ttk.Scrollbar(conteneur_tableau, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defilement.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        defilement.pack(side="right", fill="y")

        self.tableau.bind("<Double-1>", self._au_double_clic)

        self.label_statut = tk.Label(
            self.parent, text="Chargement...", font=POLICE_NORMALE,
            bg=COULEUR_FOND, fg=COULEUR_TEXTE, anchor="w"
        )
        self.label_statut.pack(fill="x", padx=16, pady=(0, 12))

    def _appliquer_style_ttk(self):
        """Configure uniquement les styles nommés de cet onglet — ne touche
        jamais le thème global (l'app tourne sous ttkbootstrap "darkly")."""
        style = ttk.Style()
        style.configure(
            "Satellites.Treeview",
            background=COULEUR_FOND_PANNEAU,
            fieldbackground=COULEUR_FOND_PANNEAU,
            foreground=COULEUR_TEXTE,
            font=POLICE_MONO,
            rowheight=26,
            borderwidth=0,
        )
        style.configure(
            "Satellites.Treeview.Heading",
            background=COULEUR_BORDURE,
            foreground=COULEUR_TEXTE,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map("Satellites.Treeview", background=[("selected", COULEUR_ACCENT)])
        style.map("Satellites.Treeview.Heading", background=[("active", COULEUR_ACCENT)])

    # ------------------------------------------------------------------
    # Chargement des données (en arrière-plan pour ne pas geler l'UI)
    # ------------------------------------------------------------------
    def _lancer_chargement_async(self):
        self.bouton_actualiser.config(state="disabled", text="⏳ Chargement...")
        self.label_statut.config(text="📡 Téléchargement/lecture des TLE...")
        threading.Thread(target=self._charger_donnees, daemon=True).start()

    def _charger_donnees(self):
        try:
            fichiers_tle = telecharger_tle_si_necessaire()
            satellites_par_categorie, ts = charger_satellites(fichiers_tle)
            observateur = wgs84.latlon(self.ma_latitude, self.ma_longitude, elevation_m=MON_ALTITUDE_M)
            passages = calculer_passages(satellites_par_categorie, ts, observateur)
            passages = regrouper_passages_colocalises(passages)
            self.tous_les_passages = passages
            self.parent.after(0, self._rafraichir_tableau)
        except Exception as e:
            # Message figé tout de suite : « e » n'existe plus à la sortie du except
            msg = f"❌ Erreur : {e}"
            self.parent.after(0, lambda: self.label_statut.config(text=msg))
        finally:
            self.parent.after(0, lambda: self.bouton_actualiser.config(state="normal", text="🔄 Actualiser"))

    # ------------------------------------------------------------------
    # Affichage / filtrage
    # ------------------------------------------------------------------
    def _rafraichir_tableau(self):
        self.tableau.delete(*self.tableau.get_children())
        self.passage_par_ligne = {}

        categorie_choisie = self.filtre_categorie.get()
        elevation_min = int(self.filtre_elevation.get().replace("°", ""))

        passages_filtres = [
            p for p in self.tous_les_passages
            if (categorie_choisie == "Toutes" or p["categorie"] == categorie_choisie)
            and p["elevation_max"] >= elevation_min
        ]

        for p in passages_filtres:
            if p["elevation_max"] >= 50:
                tag = "haute"
            elif p["elevation_max"] >= 20:
                tag = "moyenne"
            else:
                tag = "basse"

            id_ligne = self.tableau.insert(
                "", "end", tags=(tag,),
                values=(
                    p["satellite"],
                    p["categorie"],
                    p["aos"].strftime("%d/%m %H:%M"),
                    f"{p['duree_min']:.0f} min",
                    f"{p['elevation_max']:.0f}°",
                    f"{p['azimut_culmination']:.0f}°",
                )
            )
            self.passage_par_ligne[id_ligne] = p

        self.label_statut.config(
            text=(
                f"✅ {len(passages_filtres)} passage(s) affiché(s) sur {len(self.tous_les_passages)} au total"
                "  —  double-clique une ligne pour voir la carte 🗺️"
            )
        )

    # ------------------------------------------------------------------
    # Carte du passage sélectionné
    # ------------------------------------------------------------------
    def _au_double_clic(self, event):
        id_ligne = self.tableau.identify_row(event.y)
        if not id_ligne:
            return
        passage = self.passage_par_ligne.get(id_ligne)
        if passage is None:
            return
        self._ouvrir_fenetre_carte(passage)

    def _ouvrir_fenetre_carte(self, passage):
        fenetre = tk.Toplevel(self.parent)
        fenetre.title(f"Carte — {passage['satellite']}")
        fenetre.geometry("900x600")
        fenetre.configure(bg=COULEUR_FOND)

        figure = Figure(figsize=(9, 5.6), dpi=100, facecolor=COULEUR_FOND)
        ax = figure.add_subplot(111)
        tracer_passage_sur_carte(ax, passage, self.ma_latitude, self.ma_longitude)

        canevas = FigureCanvasTkAgg(figure, master=fenetre)
        canevas.draw()
        canevas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
