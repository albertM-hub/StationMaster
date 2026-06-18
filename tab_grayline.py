"""
tab_grayline.py — Onglet Grayline pour Station Master ON5AM
Carte monde avec :
  - Ligne terminatrice jour/nuit en temps réel
  - QTH ON5AM (Ans, JO20SP)
  - Spots DX cluster colorés par bande
  - Tracé grand cercle au clic sur un spot
  - Rafraîchissement automatique toutes les 60 secondes
"""
MAP_URL  = "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57752/land_shallow_topo_2048.jpg"

import tkinter as tk
import threading
import math
import os
import urllib.request
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageTk, ImageFont

# ── Constantes QTH ────────────────────────────────────────────────────────────
QTH_LAT =  50.655   # Ans, Belgique
QTH_LON =   5.548
QTH_CALL = "ON5AM"

# ── Carte monde ───────────────────────────────────────────────────────────────

MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "world_map_grayline.jpg")

# ── Couleurs par bande ────────────────────────────────────────────────────────
BAND_COLORS = {
    "160m": "#ff4444", "80m":  "#ff8800", "60m":  "#ffdd00",
    "40m":  "#88ff00", "30m":  "#00ffcc", "20m":  "#00ccff",
    "17m":  "#0088ff", "15m":  "#aa44ff", "12m":  "#ff44cc",
    "10m":  "#ff0066", "6m":   "#ffffff", "2m":   "#aaaaaa",
}

REFRESH_MS = 60_000   # 60 secondes


class TabGrayline:
    def __init__(self, parent, app):
        self.parent = parent
        self.app    = app
        self._photo          = None
        self._map_base       = None   # PIL Image carte de base
        self._after_id       = None
        self._selected_spot  = None   # spot cliqué → grand cercle
        self._cty_coords     = None   # cache cty.dat
        self._status_var     = tk.StringVar(value="Chargement de la carte...")

        self._build_ui()
        threading.Thread(target=self._load_map, daemon=True).start()

    # ── Interface ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        bg = "#0d1117"

        # Barre supérieure
        ctrl = tk.Frame(self.parent, bg=bg)
        ctrl.pack(fill="x", padx=6, pady=3)

        tk.Label(ctrl, text="🌍 Grayline Temps Réel", bg=bg, fg="#00d4ff",
                 font=("Helvetica", 11, "bold")).pack(side="left", padx=8)

        self._lbl_utc = tk.Label(ctrl, text="", bg=bg, fg="#cccccc",
                                  font=("Courier", 10))
        self._lbl_utc.pack(side="left", padx=20)

        self._lbl_spot = tk.Label(ctrl, text="", bg=bg, fg="#ffcc00",
                                   font=("Courier", 9))
        self._lbl_spot.pack(side="left", padx=10)

        tk.Button(ctrl, text="✖ Effacer tracé", bg="#2a2a4e", fg="#cccccc",
                  relief="flat", padx=6,
                  command=self._clear_gc).pack(side="right", padx=4)
        tk.Button(ctrl, text="🔄 Rafraîchir", bg="#2a2a4e", fg="#cccccc",
                  relief="flat", padx=6,
                  command=self._draw).pack(side="right", padx=4)
        self._btn_tune = tk.Button(ctrl, text="📻 Syntoniser radio", bg="#1a3a1a", fg="#88ff88",
                                    relief="flat", padx=6,
                                    command=self._tune_selected_spot, state="disabled")
        self._btn_tune.pack(side="right", padx=4)

        # Légende bandes
        leg = tk.Frame(self.parent, bg=bg)
        leg.pack(fill="x", padx=8, pady=1)
        tk.Label(leg, text="Bandes : ", bg=bg, fg="#666",
                 font=("Courier", 8)).pack(side="left")
        for band, color in BAND_COLORS.items():
            tk.Label(leg, text=f"■ {band}", bg=bg, fg=color,
                     font=("Courier", 8)).pack(side="left", padx=3)

        # Barre de statut
        tk.Label(self.parent, textvariable=self._status_var,
                 bg=bg, fg="#555555", font=("Courier", 8),
                 anchor="w").pack(fill="x", padx=8)

        # Canvas principal
        self._canvas = tk.Canvas(self.parent, bg="#050a14", cursor="crosshair",
                                  highlightthickness=0)
        self._canvas.pack(fill="both", expand=True, padx=5, pady=(2, 5))
        self._canvas.bind("<Configure>", lambda e: self._draw())
        self._canvas.bind("<Button-1>",  self._on_click)

    # ── Chargement carte ──────────────────────────────────────────────────────

    def _load_map(self):
        if not os.path.exists(MAP_FILE):
            self._set_status("Téléchargement de la carte monde...")
            try:
                req = urllib.request.Request(MAP_URL,
                    headers={"User-Agent": "StationMaster/21 ON5AM"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                with open(MAP_FILE, "wb") as f:
                    f.write(data)
                self._set_status("Carte téléchargée.")
            except Exception as e:
                self._set_status(f"Téléchargement échoué : {e}")
                self._post(self._draw)
                return

        try:
            self._map_base = Image.open(MAP_FILE).convert("RGB")
            self._set_status("")
        except Exception as e:
            self._set_status(f"Lecture carte échouée : {e}")
            self._map_base = None

        self._post(self._draw)
        self._post(self._schedule)

    def _post(self, cb):
        """Poste un callback vers le thread principal (thread-safe Python 3.14)."""
        q = getattr(self.app, '_tk_queue', None)
        if q is not None:
            q.put(cb)
        else:
            self.parent.after(0, cb)

    def _set_status(self, txt):
        self._post(lambda: self._status_var.set(txt))

    def _schedule(self):
        if self._after_id:
            self.parent.after_cancel(self._after_id)
        self._after_id = self.parent.after(REFRESH_MS, self._auto_refresh)

    def _auto_refresh(self):
        self._draw()
        self._schedule()

    # ── Projection équirectangulaire ──────────────────────────────────────────

    def _ll2xy(self, lat, lon, w, h):
        x = int((lon + 180) / 360 * w)
        y = int((90  - lat) / 180 * h)
        return x, y

    def _xy2ll(self, x, y, w, h):
        return 90 - y / h * 180, x / w * 360 - 180

    # ── Calcul solaire (sans bibliothèque externe) ────────────────────────────

    def _sun_position(self, dt):
        """Retourne (déclinaison_deg, longitude_subsolaire_deg)."""
        doy = dt.timetuple().tm_yday
        # Déclinaison
        decl = -23.45 * math.cos(math.radians(360 / 365 * (doy + 10)))
        # Équation du temps
        B   = math.radians(360 / 365 * (doy - 81))
        eot = 9.87 * math.sin(2*B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)
        # Longitude sub-solaire
        ut      = dt.hour + dt.minute / 60 + dt.second / 3600
        sub_lon = -(ut - 12) * 15 - eot / 4
        return decl, sub_lon

    def _terminator(self, decl_deg, sub_lon, npts=720):
        """Retourne la liste (lat, lon) de la ligne terminatrice."""
        d  = math.radians(decl_deg)
        pts = []
        for i in range(npts + 1):
            lon = -180 + 360 * i / npts
            ha  = math.radians(lon - sub_lon)
            cos_ha = math.cos(ha)
            if abs(cos_ha) < 1e-9:
                lat = 90.0 if math.sin(ha) < 0 else -90.0
            else:
                lat = math.degrees(math.atan(-cos_ha / math.tan(d)))
            pts.append((max(-89.9, min(89.9, lat)), lon))
        return pts

    # ── Dessin principal ──────────────────────────────────────────────────────

    def _draw(self):
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w < 20 or h < 20:
            return

        now = datetime.now(timezone.utc)
        self._lbl_utc.config(text=now.strftime("UTC  %H:%M:%S   %d %b %Y"))

        # Image de base
        if self._map_base:
            img = self._map_base.copy().resize((w, h), Image.LANCZOS)
        else:
            # Carte de secours : fond bleu foncé avec grille
            img = Image.new("RGB", (w, h), (10, 20, 50))
            draw0 = ImageDraw.Draw(img)
            for lat in range(-60, 90, 30):
                y = self._ll2xy(lat, 0, w, h)[1]
                draw0.line([(0, y), (w, y)], fill=(30, 40, 70), width=1)
            for lon in range(-180, 181, 30):
                x = self._ll2xy(0, lon, w, h)[0]
                draw0.line([(x, 0), (x, h)], fill=(30, 40, 70), width=1)

        draw = ImageDraw.Draw(img, "RGBA")

        # ── Overlay nuit ──────────────────────────────────────────────────────
        decl, sub_lon = self._sun_position(now)
        term_pts = self._terminator(decl, sub_lon)

        term_px = [self._ll2xy(lat, lon, w, h) for lat, lon in term_pts]

        if decl >= 0:
            night = [(0, h)] + term_px + [(w, h)]
        else:
            night = [(0, 0)] + term_px + [(w, 0)]

        if len(night) > 2:
            draw.polygon(night, fill=(0, 0, 30, 150))

        # Ligne terminatrice
        if len(term_px) > 1:
            draw.line(term_px, fill=(255, 200, 50, 230), width=2)

        # ── Point sub-solaire ─────────────────────────────────────────────────
        sx, sy = self._ll2xy(decl, sub_lon % 360 - 180, w, h)
        draw.ellipse([sx-7, sy-7, sx+7, sy+7], fill=(255, 240, 0, 210))
        draw.ellipse([sx-10, sy-10, sx+10, sy+10],
                     outline=(255, 240, 0, 120), width=1)

        # ── Spots DX ──────────────────────────────────────────────────────────
        spots     = getattr(self.app, '_all_spots', [])
        cty       = self._get_cty_coords()
        plotted   = {}   # (lat_r, lon_r) → liste de bandes (pour empilement)

        for spot in spots[:200]:
            country = spot.get("country", "")
            band    = spot.get("band", "")
            coords  = cty.get(country)
            if not coords:
                continue
            lat, lon = coords
            key = (round(lat), round(lon))
            plotted.setdefault(key, []).append((lat, lon, band, spot))

        for key, items in plotted.items():
            lat, lon, band, spot = items[0]
            color = BAND_COLORS.get(band, "#ffffff")
            x, y  = self._ll2xy(lat, lon, w, h)
            r = 5
            # Halo si plusieurs bandes sur le même pays
            if len(items) > 1:
                draw.ellipse([x-r-3, y-r-3, x+r+3, y+r+3],
                             outline=color + "55", width=2)
            draw.ellipse([x-r, y-r, x+r, y+r],
                         fill=color + "CC", outline="#ffffff44")

        # ── Grand cercle ──────────────────────────────────────────────────────
        if self._selected_spot:
            coords = cty.get(self._selected_spot.get("country", ""))
            if coords:
                self._draw_great_circle(draw,
                    QTH_LAT, QTH_LON, coords[0], coords[1], w, h)

        # ── QTH ON5AM ─────────────────────────────────────────────────────────
        qx, qy = self._ll2xy(QTH_LAT, QTH_LON, w, h)
        draw.ellipse([qx-5, qy-5, qx+5, qy+5], fill=(255, 50, 50, 255))
        draw.ellipse([qx-9, qy-9, qx+9, qy+9],
                     outline=(255, 100, 100, 180), width=2)
        draw.text((qx + 11, qy - 7), QTH_CALL, fill=(255, 255, 255, 230))

        # ── Grille (si carte de secours) ──────────────────────────────────────
        if not self._map_base:
            for lat_g in range(-60, 91, 30):
                y_g = self._ll2xy(lat_g, 0, w, h)[1]
                draw.text((4, y_g), f"{lat_g:+d}°", fill=(80, 80, 120, 180))
            for lon_g in range(-120, 181, 60):
                x_g = self._ll2xy(0, lon_g, w, h)[0]
                draw.text((x_g, h//2), f"{lon_g:+d}°", fill=(80, 80, 120, 180))

        # ── Affichage ─────────────────────────────────────────────────────────
        self._photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)

    # ── Grand cercle ──────────────────────────────────────────────────────────

    def _draw_great_circle(self, draw, lat1, lon1, lat2, lon2, w, h):
        la1 = math.radians(lat1); lo1 = math.radians(lon1)
        la2 = math.radians(lat2); lo2 = math.radians(lon2)
        cos_d = (math.sin(la1)*math.sin(la2) +
                 math.cos(la1)*math.cos(la2)*math.cos(lo2-lo1))
        d = math.acos(max(-1.0, min(1.0, cos_d)))
        if d < 1e-6:
            return

        # Distance en km
        dist_km = int(d * 6371)

        pts = []
        prev_x = None
        for i in range(101):
            t = i / 100
            A = math.sin((1-t)*d) / math.sin(d)
            B = math.sin(t*d)     / math.sin(d)
            x3 = A*math.cos(la1)*math.cos(lo1) + B*math.cos(la2)*math.cos(lo2)
            y3 = A*math.cos(la1)*math.sin(lo1) + B*math.cos(la2)*math.sin(lo2)
            z3 = A*math.sin(la1)               + B*math.sin(la2)
            lat3 = math.degrees(math.atan2(z3, math.sqrt(x3**2+y3**2)))
            lon3 = math.degrees(math.atan2(y3, x3))
            px, py = self._ll2xy(lat3, lon3, w, h)
            # Coupe si saut de méridien anti-horaire
            if prev_x is not None and abs(px - prev_x) > w // 2:
                if len(pts) > 1:
                    draw.line(pts, fill=(0, 255, 180, 210), width=2)
                pts = []
            pts.append((px, py))
            prev_x = px

        if len(pts) > 1:
            draw.line(pts, fill=(0, 255, 180, 210), width=2)

        # Distance au milieu du tracé
        mid = pts[len(pts)//2]
        draw.text((mid[0]+4, mid[1]-10), f"{dist_km} km", fill=(0, 255, 180, 230))

    # ── Clic ──────────────────────────────────────────────────────────────────

    def _on_click(self, event):
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        click_lat, click_lon = self._xy2ll(event.x, event.y, w, h)

        spots   = getattr(self.app, '_all_spots', [])
        cty     = self._get_cty_coords()
        best    = None
        best_d  = 12.0   # degrés max

        for spot in spots[:200]:
            coords = cty.get(spot.get("country", ""))
            if not coords:
                continue
            d = math.hypot(coords[0]-click_lat, coords[1]-click_lon)
            if d < best_d:
                best_d = d
                best   = spot

        self._selected_spot = best
        if best:
            call    = best.get("call", "?")
            country = best.get("country", "?")
            freq    = best.get("freq", 0)
            band    = best.get("band", "?")
            self._lbl_spot.config(
                text=f"▶ {call}  {country}  {freq:.1f} kHz  [{band}]")
            self._btn_tune.config(state="normal")
        else:
            self._lbl_spot.config(text="")
            self._btn_tune.config(state="disabled")
        self._draw()

    def _clear_gc(self):
        self._selected_spot = None
        self._lbl_spot.config(text="")
        self._btn_tune.config(state="disabled")
        self._draw()

    def _tune_selected_spot(self):
        """Syntonise la radio sur la fréquence du spot sélectionné."""
        if not self._selected_spot:
            return
        freq = self._selected_spot.get("freq", 0)
        mode = self._selected_spot.get("mode", "SSB")
        call = self._selected_spot.get("call", "?")
        try:
            if hasattr(self.app, '_tune_spot_freq'):
                self.app._tune_spot_freq(str(freq), mode)
            elif hasattr(self.app, 'cat') and self.app.cat:
                self.app.cat.set_freq(float(freq) * 1000)
                self.app.current_freq_hz = str(int(float(freq) * 1000))
            self._lbl_spot.config(text=f"📻 Radio accordée → {freq:.1f} kHz  {call}")
        except Exception as e:
            self._lbl_spot.config(text=f"⚠️ Syntonisation : {e}")

    # ── Coordonnées cty.dat ───────────────────────────────────────────────────

    def _get_cty_coords(self):
        if self._cty_coords is not None:
            return self._cty_coords

        coords  = {}
        cty_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cty.dat")
        try:
            with open(cty_path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
            for record in text.split(";"):
                record = record.strip()
                if not record:
                    continue
                for line in record.splitlines():
                    if line and not line[0].isspace() and ":" in line:
                        parts = line.split(":")
                        if len(parts) >= 6:
                            country = parts[0].strip()
                            try:
                                lat =  float(parts[4].strip())
                                lon = -float(parts[5].strip())  # cty.dat: W positif
                                if country:
                                    coords[country] = (lat, lon)
                            except (ValueError, IndexError):
                                pass
                        break
        except Exception as e:
            print(f"[Grayline] cty.dat : {e}")

        self._cty_coords = coords
        print(f"[Grayline] {len(coords)} pays chargés depuis cty.dat")
        return coords
