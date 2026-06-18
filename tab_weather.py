"""tab_weather.py — Widget météo pour le dashboard Station Master.

Mode compact (dashboard row2) ou large (standalone).
API : open-meteo.com — gratuite, sans clé.
Affiche : conditions actuelles + prévisions 6 h.
"""
import threading
import tkinter as tk
from datetime import datetime, timezone

try:
    import requests as _req
except ImportError:
    _req = None

_LAT = 50.5681
_LON = 5.5269
_REFRESH_MS = 3_600_000   # 60 minutes

# Codes WMO → (icône Unicode, description française courte)
_WMO: dict[int, tuple[str, str]] = {
    0:  ("☀️",  "Ciel dégagé"),
    1:  ("🌤️", "Principalement dégagé"),
    2:  ("⛅",  "Partiellement nuageux"),
    3:  ("☁️",  "Couvert"),
    45: ("🌫️", "Brouillard"),
    48: ("🌫️", "Brouillard givrant"),
    51: ("🌦️", "Bruine légère"),
    53: ("🌦️", "Bruine modérée"),
    55: ("🌧️", "Bruine dense"),
    61: ("🌧️", "Pluie légère"),
    63: ("🌧️", "Pluie modérée"),
    65: ("🌧️", "Pluie forte"),
    71: ("🌨️", "Neige légère"),
    73: ("🌨️", "Neige modérée"),
    75: ("❄️",  "Neige forte"),
    77: ("🌨️", "Grains de neige"),
    80: ("🌦️", "Averses légères"),
    81: ("🌧️", "Averses modérées"),
    82: ("⛈️", "Averses violentes"),
    85: ("🌨️", "Averses de neige"),
    86: ("❄️",  "Averses de neige fortes"),
    95: ("⛈️", "Orage"),
    96: ("⛈️", "Orage + grêle"),
    99: ("⛈️", "Orage + grêle forte"),
}

_API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={_LAT}&longitude={_LON}"
    "&current=temperature_2m,weathercode,windspeed_10m"
    "&hourly=temperature_2m,weathercode,precipitation_probability"
    "&timezone=auto&forecast_days=1"
)


def _wmo(code: int) -> tuple[str, str]:
    return _WMO.get(code, ("🌡️", "?"))


class WeatherWidget:
    """Widget météo autonome avec prévisions horaires.

    Args:
        parent  : frame tkinter parent
        bg      : couleur de fond (héritée du dashboard)
        compact : True → 4 lignes compactes pour row2 du dashboard
    """

    def __init__(self, parent: tk.Frame, bg: str = "#11273f", compact: bool = False):
        self._bg      = bg
        self._compact = compact
        self._root    = parent.winfo_toplevel()

        # Stringvars
        self._var_now      = tk.StringVar(value="⏳ Chargement…")
        self._var_wind     = tk.StringVar(value="")
        self._var_forecast = tk.StringVar(value="")
        self._var_tip      = tk.StringVar(value="")

        if compact:
            self._build_compact(parent)
        else:
            self._build_full(parent)

        self._root.after(1500, self._schedule)

    # ── Layouts ──────────────────────────────────────────────────────────────

    def _build_compact(self, parent: tk.Frame):
        """4 lignes denses pour s'insérer dans un LabelFrame existant."""
        tk.Label(parent, textvariable=self._var_now,
                 font=("Consolas", 12, "bold"), fg="#3daee9", bg=self._bg,
                 justify="left").pack(anchor="w", pady=(2, 0))
        tk.Label(parent, textvariable=self._var_wind,
                 font=("Consolas", 9), fg="#aaa", bg=self._bg,
                 justify="left").pack(anchor="w")
        tk.Label(parent, text="Prochaines heures :",
                 font=("Consolas", 8, "bold"), fg="#f39c12", bg=self._bg).pack(anchor="w", pady=(4, 0))
        tk.Label(parent, textvariable=self._var_forecast,
                 font=("Consolas", 9), fg="#ddd", bg=self._bg,
                 justify="left").pack(anchor="w")
        tk.Label(parent, textvariable=self._var_tip,
                 font=("Consolas", 8, "italic"), fg="#f39c12", bg=self._bg,
                 justify="left", wraplength=220).pack(anchor="w", pady=(3, 0))

    def _build_full(self, parent: tk.Frame):
        """Version large autonome avec LabelFrame propre."""
        outer = tk.LabelFrame(
            parent, text="🌤️ Météo — Ans, Belgique  (JO20SP)",
            bg=self._bg, fg="#3daee9", font=("Arial", 9, "bold"),
            bd=1, relief="groove", padx=10, pady=6,
        )
        outer.pack(fill="x", padx=6)
        tk.Label(outer, textvariable=self._var_now,
                 font=("Consolas", 13, "bold"), fg="#3daee9", bg=self._bg,
                 justify="center").pack()
        tk.Label(outer, textvariable=self._var_wind,
                 font=("Consolas", 9), fg="#aaa", bg=self._bg).pack()
        tk.Label(outer, text="▸ Prochaines heures :",
                 font=("Consolas", 9, "bold"), fg="#f39c12", bg=self._bg).pack(anchor="w", pady=(6, 0))
        tk.Label(outer, textvariable=self._var_forecast,
                 font=("Consolas", 10), fg="#ddd", bg=self._bg, justify="left").pack(anchor="w")
        tk.Label(outer, textvariable=self._var_tip,
                 font=("Consolas", 9, "italic"), fg="#f39c12", bg=self._bg,
                 justify="left", wraplength=500).pack(anchor="w", pady=(4, 0))

    # ── Planification ────────────────────────────────────────────────────────

    def _schedule(self):
        threading.Thread(target=self._fetch, daemon=True).start()
        self._root.after(_REFRESH_MS, self._schedule)

    # ── Appel API ────────────────────────────────────────────────────────────

    def _fetch(self):
        if _req is None:
            self._set_all("🌡️ Météo indisponible", "", "", "")
            return
        try:
            r = _req.get(_API_URL, timeout=10)
            r.raise_for_status()
            data = r.json()

            # ── Conditions actuelles ──────────────────────────────────────
            cur   = data["current"]
            temp  = float(cur["temperature_2m"])
            code  = int(cur["weathercode"])
            wind  = float(cur["windspeed_10m"])
            icon, desc = _wmo(code)
            now_txt  = f"{icon}  {temp:.1f} °C  —  {desc}"
            wind_txt = f"💨 Vent : {wind:.0f} km/h"

            # ── Prévisions horaires (6 prochaines heures utiles) ──────────
            hourly = data.get("hourly", {})
            times  = hourly.get("time", [])
            temps  = hourly.get("temperature_2m", [])
            codes  = hourly.get("weathercode", [])
            probs  = hourly.get("precipitation_probability", [])

            now_utc = datetime.now(timezone.utc)
            now_h   = now_utc.hour
            slots   = []

            for i, t_str in enumerate(times):
                # Format : "2026-05-02T14:00"
                try:
                    h = int(t_str[11:13])
                except (ValueError, IndexError):
                    continue
                # On prend les 6 prochaines heures rondes (par tranches de 2h)
                diff = (h - now_h) % 24
                if 1 <= diff <= 8 and diff % 2 == 0:
                    ic, _ = _wmo(int(codes[i]))
                    prob  = int(probs[i]) if i < len(probs) else 0
                    t_val = float(temps[i])
                    prob_str = f" ({prob}%🌧️)" if prob >= 30 else ""
                    slots.append(f"{h:02d}h {ic} {t_val:.0f}°{prob_str}")
                if len(slots) >= 3:
                    break

            forecast_txt = "  |  ".join(slots) if slots else "—"

            # ── Conseil/explication ───────────────────────────────────────
            tip = self._make_tip(code, codes, probs, times, now_h)

            self._set_all(now_txt, wind_txt, forecast_txt, tip)

        except Exception:
            self._set_all("🌡️ Météo indisponible", "", "", "")

    # ── Conseil contextuel ───────────────────────────────────────────────────

    @staticmethod
    def _make_tip(cur_code: int, codes: list, probs: list, times: list, now_h: int) -> str:
        """Génère une phrase de conseil météo adaptée à la situation."""
        # Pluie imminente ?
        for i, t_str in enumerate(times):
            try:
                h = int(t_str[11:13])
            except (ValueError, IndexError):
                continue
            diff = (h - now_h) % 24
            if 1 <= diff <= 4 and i < len(probs) and i < len(codes):
                if int(probs[i]) >= 60 or int(codes[i]) in (61, 63, 65, 80, 81, 82, 95, 96, 99):
                    return f"⚠️ Pluie probable vers {h:02d}h — prévoyez votre session radio en conséquence."
        # Orage ?
        if cur_code in (95, 96, 99):
            return "⛈️ Orage en cours — évitez les antennes extérieures non protégées !"
        # Brouillard ?
        if cur_code in (45, 48):
            return "🌫️ Brouillard — propagation VHF/UHF potentiellement favorisée."
        # Beau temps stable ?
        if cur_code in (0, 1):
            return "☀️ Beau temps stable — bonnes conditions pour une session DX."
        # Dégradation progressive ?
        cloud_count = sum(1 for c in codes[:6] if int(c) >= 45)
        if cloud_count >= 3:
            return "⛅ Dégradation progressive attendue dans les prochaines heures."
        return ""

    # ── Mise à jour UI (thread-safe) ─────────────────────────────────────────

    def _set_all(self, now: str, wind: str, forecast: str, tip: str):
        self._root.after(0, lambda: (
            self._var_now.set(now),
            self._var_wind.set(wind),
            self._var_forecast.set(forecast),
            self._var_tip.set(tip),
        ))
