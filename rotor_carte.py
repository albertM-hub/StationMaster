"""
rotor_carte.py — Carte du monde et géographie pour l'onglet Rotor
ON5AM — hamanalyst.org

Repris tel quel de « rotor Yaesu/rotor_control.py » (validé le 2026-10-22) :
projection de Miller recalée, grand cercle, cap, colorisation de la carte.
Aucune commande rotor ici.
"""

import math
import os
import threading

try:
    from PIL import Image, ImageDraw
    import numpy as np
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_DIR = os.path.dirname(os.path.abspath(__file__))

MAP_W     = 720   # Taille d'origine de world_map.png
MAP_H     = 348
# Projection de world_map.png : Miller cylindrique, recalée le 2026-10-22 sur les côtes
# Natural Earth 1:50 M (recouvrement 91 %). x = MAP_X0 + MAP_KX·lon ; y = MAP_Y0 − MAP_KY·Miller(lat)
MAP_X0    = 349.88  # colonne du méridien 0°
MAP_KX    = 1.9300  # px par degré de longitude (la carte couvre ≈ 373° : bord droit au-delà de 180° E)
MAP_Y0    = 219.11  # ligne de l'équateur
MAP_KY    = 1.9063  # px par degré de l'ordonnée de Miller
MAP_CACHE = os.path.join(_DIR, "rotor_map_cache.png")
WORLD_PNG = os.path.join(_DIR, "rotor_world_map.png")

# ── Couleurs de la carte PIL ───────────────────────────────────────────────
PIL_OCEAN = ( 10,  30,  48)
PIL_LAND  = ( 42,  74,  42)
PIL_LOUT  = ( 58, 106,  58)
PIL_GRID  = ( 18,  32,  48)
PIL_EQ    = ( 26,  64,  96)
PIL_BDR   = (180, 210, 180)

# ── Contours continents (lon, lat) ────────────────────────────────────────────
CONTINENTS = [
    [(-168,71),(-160,70),(-141,71),(-135,57),(-130,54),(-125,50),
     (-124,49),(-124,37),(-117,32),(-97,26),(-90,30),(-85,30),
     (-80,25),(-80,31),(-75,35),(-67,45),(-60,47),(-53,47),
     (-55,51),(-64,63),(-83,63),(-95,60),(-110,60),(-135,57),
     (-140,60),(-155,60),(-168,62),(-168,71)],
    [(-52,82),(-20,83),(-18,77),(-18,70),(-25,65),(-44,65),(-52,70),(-52,82)],
    [(-80,10),(-77,8),(-75,0),(-75,-5),(-72,-10),(-72,-18),
     (-65,-22),(-58,-35),(-62,-51),(-68,-55),(-75,-50),(-80,-40),
     (-80,-25),(-73,-15),(-72,-5),(-80,10)],
    [(-9,36),(-9,44),(-8,44),(-1,44),(2,43),(5,44),(2,48),(2,51),
     (5,52),(8,55),(10,55),(12,56),(18,57),(24,58),(25,65),(28,70),
     (20,70),(15,58),(10,57),(8,55),(10,54),(14,54),(18,55),(24,55),
     (27,56),(30,60),(35,62),(40,65),(30,70),(20,72),(18,70),(10,55),
     (8,50),(6,49),(2,49),(0,46),(-2,44),(-5,44),(-9,44),(-9,36)],
    [(-5,50),(-3,52),(0,52),(2,54),(0,58),(-5,58),(-6,54),(-5,50)],
    [(-10,52),(-6,52),(-5,54),(-8,56),(-10,52)],
    [(5,58),(8,55),(11,55),(30,57),(30,70),(16,68),(14,65),(5,58)],
    [(-24,64),(-13,64),(-13,66),(-24,66),(-24,64)],
    [(-17,15),(-15,12),(-15,10),(-17,5),(-10,5),(-5,5),(0,5),(5,5),
     (10,5),(15,0),(35,-5),(40,-5),(42,-12),(38,-20),(36,-25),(32,-30),
     (28,-35),(18,-35),(14,-30),(12,-22),(10,-18),(8,-5),(0,5),
     (-5,10),(-14,10),(-17,15)],
    [(44,-12),(50,-16),(50,-25),(44,-25),(44,-12)],
    [(30,42),(36,37),(36,30),(45,10),(56,12),(60,5),(80,10),(100,5),
     (105,10),(110,18),(120,20),(122,30),(130,35),(140,40),(143,45),
     (135,48),(130,55),(110,55),(100,55),(80,60),(60,70),(40,72),
     (30,70),(25,65),(30,55),(35,50),(40,45),(30,42)],
    [(36,30),(43,12),(46,10),(52,12),(56,22),(58,22),(60,24),(55,28),(43,28),(36,30)],
    [(60,24),(68,24),(80,10),(85,8),(70,8),(68,8),(60,12),(60,24)],
    [(100,22),(105,20),(104,10),(110,10),(115,5),(105,0),(100,5),(96,16),(100,22)],
    [(96,6),(108,0),(106,-6),(100,-4),(96,2),(96,6)],
    [(109,2),(118,4),(118,0),(114,-4),(109,-2),(109,2)],
    [(114,-22),(122,-18),(130,-12),(136,-12),(138,-16),(140,-18),
     (148,-20),(154,-28),(152,-36),(146,-40),(140,-40),(132,-32),
     (124,-28),(114,-26),(114,-22)],
    [(132,-2),(140,-4),(148,-8),(146,-6),(140,-4),(132,-2)],
    [(130,33),(131,34),(134,35),(140,36),(141,40),(140,42),(136,36),(130,33)],
    [(-180,-68),(-90,-70),(0,-68),(90,-70),(180,-68),(180,-90),(-180,-90),(-180,-68)],
]

# ── Géographie ────────────────────────────────────────────────────────────────
def miller_deg(lat):
    # Ordonnée de la projection de Miller, exprimée en degrés
    return math.degrees(1.25 * math.log(math.tan(math.pi/4 + 0.4 * math.radians(lat))))

def ll_to_xy(lon, lat):
    return MAP_X0 + MAP_KX * lon, MAP_Y0 - MAP_KY * miller_deg(lat)

def xy_to_ll(x, y):
    # Inverse de ll_to_xy (coordonnées de la carte de base MAP_W × MAP_H)
    lon = (x - MAP_X0) / MAP_KX
    if lon >  180: lon -= 360   # bord droit de la carte : au-delà de 180° E
    if lon < -180: lon += 360
    ym  = math.radians((MAP_Y0 - y) / MAP_KY)
    lat = math.degrees(2.5 * math.atan(math.exp(0.8 * ym)) - 0.625 * math.pi)
    return lon, lat

def central_angle(lat1, lon1, lat2, lon2):
    # Distance angulaire sur le grand cercle (degrés), formule de haversine
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dla, dlo = la2 - la1, math.radians(lon2 - lon1)
    a = math.sin(dla/2)**2 + math.cos(la1)*math.cos(la2)*math.sin(dlo/2)**2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(a))))

def bearing(lat1, lon1, lat2, lon2):
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(la2)
    y = math.cos(la1)*math.sin(la2) - math.sin(la1)*math.cos(la2)*math.cos(dl)
    return math.degrees(math.atan2(x, y)) % 360

def great_circle_pts(lat1, lon1, az_deg, n=180, dist_deg=180.0):
    # n + 1 points de 0 à dist_deg (degrés d'arc) le long du cap az_deg
    pts = []
    la1r = math.radians(lat1)
    lo1r = math.radians(lon1)
    azr  = math.radians(az_deg)
    for i in range(n + 1):
        d    = math.radians(i * dist_deg / n)
        lat2 = math.asin(math.sin(la1r)*math.cos(d) +
                         math.cos(la1r)*math.sin(d)*math.cos(azr))
        dlon = math.atan2(math.sin(azr)*math.sin(d)*math.cos(la1r),
                          math.cos(d) - math.sin(la1r)*math.sin(lat2))
        pts.append((math.degrees(lat2), math.degrees(lo1r + dlon)))
    return pts

# ── Génération carte ──────────────────────────────────────────────────────────
def _draw_base(w, h):
    img  = Image.new("RGB", (w, h), PIL_OCEAN)
    draw = ImageDraw.Draw(img)
    sx, sy = w / MAP_W, h / MAP_H   # même projection que world_map.png
    for lon in range(-180, 181, 30):
        x = int(ll_to_xy(lon, 0)[0] * sx)
        draw.line([(x,0),(x,h)], fill=PIL_GRID)
    for lat in range(-60, 61, 30):
        y = int(ll_to_xy(0, lat)[1] * sy)
        draw.line([(0,y),(w,y)], fill=PIL_EQ if lat == 0 else PIL_GRID)
    for poly in CONTINENTS:
        dense = []
        for i in range(len(poly)):
            lo1, la1 = poly[i]
            lo2, la2 = poly[(i+1) % len(poly)]
            n = max(1, int(math.hypot(lo2-lo1, la2-la1) / 3))
            for j in range(n):
                dense.append((lo1+j*(lo2-lo1)/n, la1+j*(la2-la1)/n))
        pts = []
        for lo, la in dense:
            x, y = ll_to_xy(lo, max(-85, min(85, la)))
            pts.append((int(x * sx), int(y * sy)))
        if len(pts) >= 3:
            draw.polygon(pts, fill=PIL_LAND, outline=PIL_LOUT)
    return np.array(img)



def _colorize_bw_map(path):
    """Convertit une carte N/B ou palette+transparence en carte colorée."""
    # Fond blanc = océan ; on colle l'image par-dessus avec son alpha
    raw = Image.open(path).convert("RGBA")
    bg  = Image.new("RGBA", raw.size, (255, 255, 255, 255))
    bg.paste(raw, mask=raw.split()[3])
    arr = np.array(bg.convert("L").resize((MAP_W, MAP_H), Image.LANCZOS))
    out = np.zeros((MAP_H, MAP_W, 3), dtype=np.uint8)
    land_mask = arr < 128
    out[ land_mask] = PIL_LAND
    out[~land_mask] = PIL_OCEAN
    # Grille
    img = Image.fromarray(out)
    draw = ImageDraw.Draw(img)
    for lon in range(-180, 181, 30):
        x = int(ll_to_xy(lon, 0)[0])
        draw.line([(x, 0), (x, MAP_H)], fill=PIL_GRID)
    for lat in range(-60, 61, 30):
        y = int(ll_to_xy(0, lat)[1])
        draw.line([(0, y), (MAP_W, y)], fill=PIL_EQ if lat == 0 else PIL_GRID)
    return img

def _build_map():
    # 1. world_map.png fourni par l'utilisateur (carte N/B) → prioritaire
    if os.path.exists(WORLD_PNG):
        print("[carte] Colorisation de world_map.png…")
        return _colorize_bw_map(WORLD_PNG)

    # 2. Cache existant (généré lors d'un lancement précédent)
    if os.path.exists(MAP_CACHE):
        img = Image.open(MAP_CACHE).convert("RGB")
        if img.size != (MAP_W, MAP_H):
            img = img.resize((MAP_W, MAP_H), Image.LANCZOS)
        return img

    # 3. Fallback vectoriel intégré
    print("[carte] Fallback vectoriel utilisé")
    arr = _draw_base(MAP_W, MAP_H)
    img = Image.fromarray(arr.astype(np.uint8))
    img.save(MAP_CACHE)
    return img

def load_map_async(callback):
    threading.Thread(target=lambda: callback(_build_map()), daemon=True).start()
