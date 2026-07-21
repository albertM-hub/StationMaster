#!/usr/bin/env python3
"""
Carte du monde 2D : trace au sol d'un satellite pendant son passage
+ cercle de couverture radio (empreinte au sol).

Dépendances : matplotlib (en plus de skyfield déjà utilisé)
    pip install matplotlib --break-system-packages
"""

import json
import math
import os
import urllib.request

from skyfield.api import load, wgs84

# ------------------------------------------------------------------
# Contours des pays (Natural Earth, résolution 110m = fichier léger ~800Ko)
# Mis en cache localement une fois pour toutes (les frontières ne changent pas souvent)
# ------------------------------------------------------------------
CACHE_DIR = os.path.expanduser("~/.station_master_tle_cache")  # même dossier que les TLE
CHEMIN_CONTOURS = os.path.join(CACHE_DIR, "contours_pays.geojson")
URL_CONTOURS = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_admin_0_countries.geojson"
)

RAYON_TERRE_KM = 6371.0

# Palette cohérente avec le reste de l'application
COULEUR_CONTINENTS = "#2a3b5c"
COULEUR_FOND_CARTE = "#0d1526"
COULEUR_TRACE_SOL = "#4a9eff"
COULEUR_COUVERTURE = "#3ddc84"
COULEUR_OBSERVATEUR = "#e85c5c"
COULEUR_TEXTE = "#e8eef7"


def telecharger_contours_si_necessaire():
    """Télécharge le fichier de contours des pays s'il n'est pas déjà en cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    if not os.path.exists(CHEMIN_CONTOURS):
        urllib.request.urlretrieve(URL_CONTOURS, CHEMIN_CONTOURS)
    return CHEMIN_CONTOURS


def dessiner_continents(ax):
    """Dessine les contours des pays sur les axes matplotlib donnés."""
    chemin = telecharger_contours_si_necessaire()
    with open(chemin, encoding="utf-8") as f:
        donnees = json.load(f)

    for pays in donnees["features"]:
        geometrie = pays["geometry"]
        # Un pays peut être un seul polygone (îles simples) ou plusieurs (archipels)
        polygones = geometrie["coordinates"] if geometrie["type"] == "MultiPolygon" else [geometrie["coordinates"]]
        for polygone in polygones:
            anneau_exterieur = polygone[0]  # on ignore les trous internes (lacs), suffisant pour une vue d'ensemble
            lons = [pt[0] for pt in anneau_exterieur]
            lats = [pt[1] for pt in anneau_exterieur]
            ax.plot(lons, lats, color=COULEUR_CONTINENTS, linewidth=0.6, zorder=1)


def calculer_trace_au_sol(sat, ts, t_debut_dt, t_fin_dt, nb_points=50):
    """
    Calcule la position du point subsatellite (latitude/longitude directement
    sous le satellite) à intervalles réguliers entre le début et la fin du passage.
    Renvoie une liste de (latitude, longitude) en degrés.
    """
    duree_s = (t_fin_dt - t_debut_dt).total_seconds()
    points = []
    for i in range(nb_points + 1):
        t = ts.from_datetime(t_debut_dt + (t_fin_dt - t_debut_dt) * (i / nb_points))
        geocentrique = sat.at(t)
        sous_point = wgs84.subpoint(geocentrique)
        points.append((sous_point.latitude.degrees, sous_point.longitude.degrees))
    return points


def calculer_altitude_satellite_km(sat, ts, t_dt):
    """Altitude du satellite au-dessus de l'ellipsoïde WGS84, à un instant donné."""
    t = ts.from_datetime(t_dt)
    sous_point = wgs84.subpoint(sat.at(t))
    return sous_point.elevation.km


def calculer_cercle_couverture(lat_centre_deg, lon_centre_deg, altitude_km, nb_points=72):
    """
    Calcule le contour du disque de visibilité radio (empreinte au sol) : la zone
    où un observateur au sol pourrait théoriquement voir le satellite à l'horizon
    (élévation 0°). Formule de trigonométrie sphérique standard.
    Renvoie une liste de (latitude, longitude) formant le polygone du cercle.
    """
    # Angle au centre de la Terre correspondant à l'horizon radio (élévation 0°)
    rapport = RAYON_TERRE_KM / (RAYON_TERRE_KM + altitude_km)
    angle_central_rad = math.acos(rapport)

    lat_centre_rad = math.radians(lat_centre_deg)
    lon_centre_rad = math.radians(lon_centre_deg)

    points = []
    for i in range(nb_points + 1):
        cap_rad = 2 * math.pi * i / nb_points  # cap (bearing) de 0 à 360°

        # Formule de destination en navigation sphérique (great-circle destination point)
        lat_dest_rad = math.asin(
            math.sin(lat_centre_rad) * math.cos(angle_central_rad)
            + math.cos(lat_centre_rad) * math.sin(angle_central_rad) * math.cos(cap_rad)
        )
        lon_dest_rad = lon_centre_rad + math.atan2(
            math.sin(cap_rad) * math.sin(angle_central_rad) * math.cos(lat_centre_rad),
            math.cos(angle_central_rad) - math.sin(lat_centre_rad) * math.sin(lat_dest_rad)
        )
        points.append((math.degrees(lat_dest_rad), math.degrees(lon_dest_rad)))

    return points


def tracer_passage_sur_carte(ax, passage, ma_latitude, ma_longitude):
    """
    Dessine sur les axes matplotlib donnés : les continents, la trace au sol
    du satellite pendant le passage, sa couverture radio à la culmination,
    et la position de l'observateur.
    """
    ts = load.timescale()
    sat = passage["sat_obj"]

    ax.set_facecolor(COULEUR_FOND_CARTE)
    dessiner_continents(ax)

    # --- Trace au sol pendant le passage ---
    trace = calculer_trace_au_sol(sat, ts, passage["aos"], passage["los"])
    lats_trace = [p[0] for p in trace]
    lons_trace = [p[1] for p in trace]
    ax.plot(lons_trace, lats_trace, color=COULEUR_TRACE_SOL, linewidth=2, zorder=3,
             label="Trace au sol du satellite")
    ax.scatter([lons_trace[0]], [lats_trace[0]], color=COULEUR_TRACE_SOL, marker="o", s=50, zorder=4)
    ax.scatter([lons_trace[-1]], [lats_trace[-1]], color=COULEUR_TRACE_SOL, marker="s", s=50, zorder=4)

    # --- Couverture radio (empreinte) au moment de la culmination (milieu du passage) ---
    t_milieu = passage["aos"] + (passage["los"] - passage["aos"]) / 2
    altitude_km = calculer_altitude_satellite_km(sat, ts, t_milieu)
    idx_milieu = len(trace) // 2
    lat_milieu, lon_milieu = trace[idx_milieu]
    cercle = calculer_cercle_couverture(lat_milieu, lon_milieu, altitude_km)
    lats_cercle = [p[0] for p in cercle]
    lons_cercle = [p[1] for p in cercle]
    ax.plot(lons_cercle, lats_cercle, color=COULEUR_COUVERTURE, linewidth=1, linestyle="--",
             zorder=2, label="Couverture radio (à la culmination)")

    # --- Position de l'observateur (toi) ---
    ax.scatter([ma_longitude], [ma_latitude], color=COULEUR_OBSERVATEUR, marker="*", s=200,
               zorder=5, label="Ta position")

    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_xlabel("Longitude", color=COULEUR_TEXTE)
    ax.set_ylabel("Latitude", color=COULEUR_TEXTE)
    ax.tick_params(colors=COULEUR_TEXTE)
    for spine in ax.spines.values():
        spine.set_color(COULEUR_CONTINENTS)
    ax.set_title(
        f"{passage['satellite']} — passage du {passage['aos'].strftime('%d/%m %H:%M')} UTC "
        f"(altitude ≈ {altitude_km:.0f} km)",
        color=COULEUR_TEXTE, fontsize=11
    )
    legende = ax.legend(loc="lower left", fontsize=8, facecolor=COULEUR_FOND_CARTE, edgecolor=COULEUR_CONTINENTS)
    for texte in legende.get_texts():
        texte.set_color(COULEUR_TEXTE)
