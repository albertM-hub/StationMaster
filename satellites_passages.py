#!/usr/bin/env python3
"""
Prototype autonome : liste des passages de satellites au-dessus de ta position.
Catégories : radioamateur (SO-50, AO-91...), météo (NOAA, Météor-M), ISS/stations.

Dépendance : pip install skyfield --break-system-packages

Une fois validé, ce code sera intégré comme nouvel onglet "Satellites" dans
Station Master (recommandé : via Claude Code vu la taille du projet).
"""

from skyfield.api import load, wgs84, EarthSatellite
from datetime import datetime, timedelta, timezone
import urllib.request
import os

# ------------------------------------------------------------------
# Configuration - À ADAPTER SI BESOIN
# ------------------------------------------------------------------
# Position dérivée de ton locator JO20SP (Ans, Belgique)
# Corrige avec tes coordonnées exactes si tu les connais (plus précis que le locator)
MA_LATITUDE = 50.646
MA_LONGITUDE = 5.542
MON_ALTITUDE_M = 100  # altitude approximative en mètres

# Élévation minimale (en degrés) pour qu'un passage soit considéré comme utile
# (en dessous, le signal est trop dégradé par les obstacles/atmosphère)
ELEVATION_MIN_DEG = 10.0

# Fenêtre de prédiction
HEURES_A_VENIR = 48

# Cache TLE local (évite de re-télécharger à chaque lancement)
CACHE_DIR = os.path.expanduser("~/.station_master_tle_cache")
CACHE_MAX_AGE_HEURES = 24

# Sources Celestrak par catégorie (gratuit, sans clé API)
SOURCES_TLE = {
    "Radioamateur": "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle",
    "Météo":        "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle",
    "Stations":     "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
}


def telecharger_tle_si_necessaire():
    """Télécharge les fichiers TLE si le cache est absent ou trop vieux."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    fichiers = {}

    for categorie, url in SOURCES_TLE.items():
        chemin_cache = os.path.join(CACHE_DIR, f"{categorie}.tle")

        cache_valide = False
        if os.path.exists(chemin_cache):
            age_heures = (datetime.now().timestamp() - os.path.getmtime(chemin_cache)) / 3600
            cache_valide = age_heures < CACHE_MAX_AGE_HEURES

        if not cache_valide:
            print(f"📡 Téléchargement des TLE {categorie}...")
            try:
                urllib.request.urlretrieve(url, chemin_cache)
            except Exception as e:
                print(f"⚠️  Échec du téléchargement pour {categorie} : {e}")
                if not os.path.exists(chemin_cache):
                    continue  # pas de cache de secours disponible, on saute cette catégorie
                print("   → utilisation de l'ancien cache disponible")
        else:
            print(f"✅ TLE {categorie} en cache (< {CACHE_MAX_AGE_HEURES}h)")

        fichiers[categorie] = chemin_cache

    return fichiers


def charger_satellites(fichiers_tle):
    """Charge tous les satellites depuis les fichiers TLE téléchargés, groupés par catégorie."""
    satellites_par_categorie = {}
    ts = load.timescale()

    for categorie, chemin in fichiers_tle.items():
        sats = load.tle_file(chemin)
        satellites_par_categorie[categorie] = sats
        print(f"   {categorie} : {len(sats)} satellites chargés")

    return satellites_par_categorie, ts


# Priorité d'affichage quand un même satellite (même NORAD ID) apparaît
# dans plusieurs catalogues Celestrak : on ne le garde qu'une fois,
# dans la catégorie la plus utile pour un radioamateur.
PRIORITE_CATEGORIE = {"Radioamateur": 0, "Stations": 1, "Météo": 2}


def calculer_passages(satellites_par_categorie, ts, observateur):
    """
    Calcule tous les passages (AOS -> LOS) pour chaque satellite
    dans la fenêtre de temps définie, en filtrant sur l'élévation minimale.
    """
    t0 = ts.now()
    t1 = ts.from_datetime(datetime.now(timezone.utc) + timedelta(hours=HEURES_A_VENIR))

    passages = []

    # Un même NORAD ID (= même objet physique) peut apparaître dans plusieurs
    # catalogues (ex: l'ISS est à la fois dans "amateur" et "stations").
    # On ne le traite qu'une seule fois, en gardant la catégorie prioritaire.
    norad_deja_traite = {}
    for categorie, sats in satellites_par_categorie.items():
        for sat in sats:
            norad_id = sat.model.satnum
            categorie_actuelle = norad_deja_traite.get(norad_id)
            if categorie_actuelle is None or PRIORITE_CATEGORIE[categorie] < PRIORITE_CATEGORIE[categorie_actuelle]:
                norad_deja_traite[norad_id] = categorie
    satellites_a_calculer = {
        (sat.model.satnum, sat.name): (categorie, sat)
        for categorie, sats in satellites_par_categorie.items()
        for sat in sats
        if norad_deja_traite.get(sat.model.satnum) == categorie
    }

    for (norad_id, nom), (categorie, sat) in satellites_a_calculer.items():
        try:
            # find_events renvoie les instants de lever (AOS), culmination et coucher (LOS)
            t_evenements, evenements = sat.find_events(
                observateur, t0, t1, altitude_degrees=ELEVATION_MIN_DEG
            )
        except Exception:
            continue  # certains TLE peuvent être invalides/décayés, on ignore

        # Les événements arrivent par triplets : 0=lever, 1=culmination, 2=coucher
        aos, culmination, los = None, None, None
        for t_evt, type_evt in zip(t_evenements, evenements):
            if type_evt == 0:
                aos = t_evt
            elif type_evt == 1:
                culmination = t_evt
            elif type_evt == 2:
                los = t_evt
                if aos is not None and culmination is not None:
                    # Élévation max atteinte à la culmination
                    difference = sat - observateur
                    alt, az, distance = difference.at(culmination).altaz()
                    passages.append({
                        "satellite": sat.name,
                        "categorie": categorie,
                        "aos": aos.utc_datetime(),
                        "los": los.utc_datetime(),
                        "duree_min": (los.utc_datetime() - aos.utc_datetime()).total_seconds() / 60,
                        "elevation_max": alt.degrees,
                        "azimut_culmination": az.degrees,
                        "sat_obj": sat,  # référence gardée pour recalculer la trace au sol (carte)
                    })
                aos, culmination, los = None, None, None

    passages.sort(key=lambda p: p["aos"])
    return passages


def regrouper_passages_colocalises(passages):
    """
    Certains objets partagent quasi la même orbite (ex: modules amarrés à l'ISS,
    vaisseaux Soyouz/Progress/Cygnus/Dragon accrochés à la station). Celestrak
    les liste comme des satellites séparés, mais pour un radioamateur ils
    représentent un seul passage utile. On les regroupe si AOS, élévation max
    et azimut sont quasi identiques (même minute, même degré).
    """
    groupes = {}
    for p in passages:
        cle = (p["aos"].strftime("%Y-%m-%d %H:%M"), round(p["elevation_max"]), round(p["azimut_culmination"]))
        groupes.setdefault(cle, []).append(p)

    passages_regroupes = []
    for cle, groupe in groupes.items():
        if len(groupe) == 1:
            passages_regroupes.append(groupe[0])
            continue
        # Plusieurs objets co-localisés : on garde celui dont le nom est le plus
        # court/représentatif (ex: "ISS (ZARYA)" plutôt que "PROGRESS-MS 34")
        representant = min(groupe, key=lambda p: len(p["satellite"]))
        representant = dict(representant)  # copie pour ne pas modifier l'original
        representant["satellite"] = f"{representant['satellite']} (+{len(groupe) - 1} objet(s) lié(s))"
        passages_regroupes.append(representant)

    passages_regroupes.sort(key=lambda p: p["aos"])
    return passages_regroupes


def afficher_passages(passages):
    """Affiche les passages sous forme de tableau lisible."""
    if not passages:
        print("\nAucun passage trouvé dans la fenêtre définie.")
        return

    print(f"\n{'Satellite':<18} {'Type':<12} {'AOS (UTC)':<17} {'Durée':>6} {'Élév.max':>9} {'Azimut':>8}")
    print("-" * 78)
    for p in passages:
        print(
            f"{p['satellite']:<18} {p['categorie']:<12} "
            f"{p['aos'].strftime('%d/%m %H:%M'):<17} "
            f"{p['duree_min']:>5.0f}m "
            f"{p['elevation_max']:>8.0f}° "
            f"{p['azimut_culmination']:>7.0f}°"
        )


def main():
    print(f"🛰️  Recherche des passages satellites - position {MA_LATITUDE}°N, {MA_LONGITUDE}°E")
    print(f"   Fenêtre : {HEURES_A_VENIR}h à venir | Élévation min : {ELEVATION_MIN_DEG}°\n")

    fichiers_tle = telecharger_tle_si_necessaire()
    if not fichiers_tle:
        print("❌ Aucune donnée TLE disponible (téléchargement échoué et pas de cache).")
        return

    satellites_par_categorie, ts = charger_satellites(fichiers_tle)

    observateur = wgs84.latlon(MA_LATITUDE, MA_LONGITUDE, elevation_m=MON_ALTITUDE_M)

    passages = calculer_passages(satellites_par_categorie, ts, observateur)
    passages = regrouper_passages_colocalises(passages)
    afficher_passages(passages)


if __name__ == "__main__":
    main()