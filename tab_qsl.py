"""tab_qsl.py — QSL email : JPEG→PDF overlay, QRZ lookup, SMTP Gmail SSL.
Importé par station_master.py : QSLEmailer(app).send_dialog()
"""
import os, io, threading, tempfile, sqlite3, ssl, smtplib
import xml.etree.ElementTree as ET
import tkinter as tk
import ttkbootstrap as ttk
from tkinter import messagebox
from datetime import datetime
import requests

# ── Chemins ──────────────────────────────────────────────────────────────────
_DIR          = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_JPG = os.path.join(_DIR, "QSL_ON5AM_print.jpg")
_CONFIG_FILE  = os.path.join(_DIR, "config.ini")

# ── Positions pixel dans le template 1654×1063 (mesurées sur l'image) ────────
_TEXT_X = {
    'call':  15,   'date': 235, 'time': 390,
    'band': 520,   'mode': 610, 'freq': 700,
    'rst_s': 815,  'rst_r': 915,
}
_TEXT_Y    = 985   # top du texte, data row zone y=963–1040
_FONT_SIZE = 28
_WHITE     = (255, 255, 255)

MY_CALL  = "ON5AM"
MY_NAME  = "Albert"
MY_QTH   = "Ans, Belgique — JO20SP"
QSL_LINK = "https://hamanalyst.org/qsl"

# ── Helpers de formatage ──────────────────────────────────────────────────────
def _freq_mhz(freq) -> str:
    if not freq:
        return ""
    try:
        f = float(freq)
        return f"{f/1e6:.3f}" if f > 1e4 else f"{f:.3f}"
    except Exception:
        return str(freq)

def _rst(val, mode) -> str:
    if (mode or "").upper() in ("FT8", "FT4", "FT2", "JS8"):
        return f"{val} dB" if val else "—"
    return val or "599"

# ── Détection langue par préfixe d'indicatif ─────────────────────────────────
_PREFIX_LANG = [
    (("ON", "OO", "OT", "OQ", "F", "TM", "TK"), "fr"),
    (("PA", "PB", "PC", "PD", "PE", "PF"),        "nl"),
    (("DL", "DA", "DB"),                           "de"),
    (("SP", "SQ", "SR"),                           "pl"),
    (("EA", "EB", "EC"),                           "es"),
    (("IK", "IW", "IZ", "I"),                     "it"),
    (("RA", "RU", "UA", "UB", "UC", "UJ", "UN", "UR"), "ru"),
    (("B",),                                            "zh"),
    (("YB", "YC", "YD", "YE", "YF", "YG", "YH"),       "id"),
    (("LO", "LP", "LQ", "LR", "LS", "LT", "LU", "LV", "LW"), "es"),
    (("G", "M", "MM", "W", "K", "N"),             "en"),
]

def _get_lang(callsign: str) -> str:
    if not callsign:
        return "en"
    prefix = callsign.upper().split("/")[0]
    for length in (3, 2, 1):
        p = prefix[:length]
        for prefixes, lang in _PREFIX_LANG:
            if p in prefixes:
                return lang
    if len(prefix) >= 2 and prefix[0] == "A" and "A" <= prefix[1] <= "L":
        return "en"
    return "en"

# ── Templates email multilingues ──────────────────────────────────────────────
def _email_body(qso: dict, lang: str) -> str:
    call  = qso.get("call") or ""
    date  = qso.get("date") or ""
    time_ = qso.get("time") or ""
    band  = qso.get("band") or ""
    mode  = (qso.get("mode") or "").upper()
    _f    = _freq_mhz(qso.get("freq", ""))
    freq  = f"{_f} MHz" if _f else band  # band already contains unit (e.g. "20m")
    rst_s = _rst(qso.get("rst_s", ""), mode)
    sig   = f"73 de {MY_NAME}, {MY_CALL} — {MY_QTH}"

    T = {
        "fr": (
            f"Cher {call},\n\n"
            f"Merci pour notre QSO du {date} à {time_} UTC sur {freq} en {mode}.\n"
            f"Rapport envoyé : {rst_s}.\n\n"
            f"Vous trouverez ci-joint ma carte QSL en PDF confirmant notre contact.\n"
            f"J'attends avec impatience votre carte QSL en retour !\n\n{sig}"
        ),
        "de": (
            f"Lieber {call},\n\n"
            f"Vielen Dank für unser QSO am {date} um {time_} UTC auf {freq} ({mode}).\n"
            f"Gesendeter Rapport: {rst_s}.\n\n"
            f"Anbei finden Sie meine QSL-Karte als PDF, die unseren Kontakt bestätigt.\n"
            f"Ich freue mich auf Ihre QSL-Karte!\n\n{sig}"
        ),
        "nl": (
            f"Beste {call},\n\n"
            f"Hartelijk dank voor ons QSO van {date} om {time_} UTC op {freq} ({mode}).\n"
            f"Verzonden rapport: {rst_s}.\n\n"
            f"Bijgevoegd vindt u mijn QSL-kaart in PDF die ons contact bevestigt.\n"
            f"Ik kijk uit naar uw QSL-kaart!\n\n{sig}"
        ),
        "pl": (
            f"Drogi {call},\n\n"
            f"Dziękuję za nasze QSO z dnia {date} o {time_} UTC na {freq} ({mode}).\n"
            f"Wysłany raport: {rst_s}.\n\n"
            f"W załączniku znajdziesz moją kartę QSL w formacie PDF potwierdzającą nasz kontakt.\n"
            f"Z niecierpliwością czekam na Twoją kartę QSL!\n\n{sig}"
        ),
        "es": (
            f"Estimado {call},\n\n"
            f"Muchas gracias por nuestro QSO del {date} a las {time_} UTC en {freq} ({mode}).\n"
            f"Informe enviado: {rst_s}.\n\n"
            f"Adjunto mi tarjeta QSL en PDF confirmando nuestro contacto.\n"
            f"¡Espero con impaciencia su tarjeta QSL!\n\n{sig}"
        ),
        "it": (
            f"Caro {call},\n\n"
            f"Grazie per il nostro QSO del {date} alle {time_} UTC su {freq} ({mode}).\n"
            f"Rapporto inviato: {rst_s}.\n\n"
            f"In allegato la mia QSL card in PDF che conferma il nostro contatto.\n"
            f"Attendo con piacere la sua QSL card!\n\n{sig}"
        ),
        "pt": (
            f"Caro {call},\n\n"
            f"Muito obrigado pelo nosso QSO em {date} às {time_} UTC em {freq} ({mode}).\n"
            f"Relatório enviado: {rst_s}.\n\n"
            f"Em anexo a minha QSL card em PDF confirmando o nosso contacto.\n"
            f"Aguardo a sua QSL card!\n\n{sig}"
        ),
        "ru": (
            f"Дорогой {call},\n\n"
            f"Спасибо за наше QSO {date} в {time_} UTC на {freq} ({mode}).\n"
            f"Рапорт: {rst_s}.\n\n"
            f"К письму прилагается моя QSL-карточка в формате PDF.\n"
            f"С нетерпением жду вашу QSL!\n\n{sig}"
        ),
        "ja": (
            f"{call} OM,\n\n"
            f"{date} {time_} UTC、{freq} ({mode}) のQSOありがとうございました。\n"
            f"レポート: {rst_s}。\n\n"
            f"添付のQSLカード（PDF）をご確認ください。\n"
            f"お返しのQSLカードを楽しみにしております！\n\n{sig}"
        ),
        "en": (
            f"Dear {call},\n\n"
            f"Thank you for our QSO on {date} at {time_} UTC on {freq} ({mode}).\n"
            f"Report sent: {rst_s}.\n\n"
            f"Please find attached my QSL card in PDF confirming our contact.\n"
            f"I look forward to receiving your QSL card!\n\n{sig}"
        ),
        "zh": (
            f"亲爱的 {call}，\n\n"
            f"感谢我们于 {date} {time_} UTC 在 {freq}（{mode}）上的 QSO。\n"
            f"发送的信号报告：{rst_s}。\n\n"
            f"随信附上我的 QSL 卡（PDF），以确认我们的联系。\n"
            f"期待收到您的 QSL 卡！\n\n{sig}"
        ),
        "id": (
            f"Yth. {call},\n\n"
            f"Terima kasih atas QSO kita pada {date} pukul {time_} UTC di {freq} ({mode}).\n"
            f"Laporan yang dikirim: {rst_s}.\n\n"
            f"Terlampir kartu QSL saya dalam format PDF sebagai konfirmasi kontak kita.\n"
            f"Saya menantikan kartu QSL Anda!\n\n{sig}"
        ),
    }
    return T.get(lang, T["en"])

# ── QRZ.com XML API — lookup email ────────────────────────────────────────────
_qrz_session = {"key": None}  # session key cache (module-level)

def _qrz_session_key(conf) -> str:
    """Authentifie sur QRZ.com (user/pass) et retourne la clé de session."""
    if _qrz_session["key"]:
        return _qrz_session["key"]
    user = ""
    pwd  = ""
    if conf:
        user = (conf.get("API", "qrz_user", fallback="") or
                conf.get("QRZ", "user",     fallback=""))
        pwd  = (conf.get("API", "qrz_pass", fallback="") or
                conf.get("QRZ", "password", fallback=""))
    if not user or not pwd:
        raise ValueError(
            "Identifiants QRZ manquants dans config.ini.\n"
            "Vérifiez [API] qrz_user et qrz_pass."
        )
    r = requests.get(
        "https://xmldata.qrz.com/xml/current/",
        params={"username": user, "password": pwd, "agent": "StationMaster/ON5AM"},
        timeout=10,
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    ns   = {"q": "http://xmldata.qrz.com"}
    key  = root.findtext("q:Session/q:Key", namespaces=ns)
    if not key:
        err = root.findtext("q:Session/q:Error", namespaces=ns) or "Login QRZ échoué"
        raise ValueError(err)
    _qrz_session["key"] = key
    return key


def _qrz_email(callsign: str, conf) -> str:
    """Retourne l'email du callsign via QRZ.com XML API, ou '' si non disponible."""
    if not callsign:
        return ""
    key = _qrz_session_key(conf)
    r   = requests.get(
        "https://xmldata.qrz.com/xml/current/",
        params={"s": key, "callsign": callsign.upper()},
        timeout=10,
    )
    r.raise_for_status()
    root  = ET.fromstring(r.text)
    ns    = {"q": "http://xmldata.qrz.com"}
    email = (root.findtext("q:Callsign/q:email", namespaces=ns) or "").strip()
    # Session expirée → réinitialiser et réessayer une seule fois
    if not email:
        err = root.findtext("q:Session/q:Error", namespaces=ns) or ""
        if "session" in err.lower():
            _qrz_session["key"] = None
            key2 = _qrz_session_key(conf)
            r2   = requests.get(
                "https://xmldata.qrz.com/xml/current/",
                params={"s": key2, "callsign": callsign.upper()},
                timeout=10,
            )
            r2.raise_for_status()
            root2 = ET.fromstring(r2.text)
            email = (root2.findtext("q:Callsign/q:email", namespaces=ns) or "").strip()
    return email

# ── Génération QSL PDF depuis template JPEG ───────────────────────────────────
def _load_font(size: int):
    """Charge DejaVuSans-Bold si disponible, sinon police par défaut PIL."""
    from PIL import ImageFont
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _render_qsl_image(qso) -> "PIL.Image.Image":
    """Rend la carte QSL navy-blue en PIL Image (1360×840 px).
    Utilisé pour l'aperçu miniature ET la pièce jointe PDF.
    """
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1360, 840

    def _fnt(size, bold=True, mono=False):
        paths = (
            ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"]
            if mono else
            ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
            if bold else
            ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
        )
        for fp in paths:
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    img  = Image.new("RGB", (W, H), "#0d1b2e")
    draw = ImageDraw.Draw(img)

    def t(x, y, text, fill, size, bold=True, mono=False, anchor="la"):
        try:
            draw.text((x, y), text, fill=fill,
                      font=_fnt(size, bold, mono), anchor=anchor)
        except TypeError:
            draw.text((x, y), text, fill=fill, font=_fnt(size, bold, mono))

    # ── 1. HEADER (y=0–110) ────────────────────────────────────────────
    draw.rectangle([0, 0, W, 110], fill="#0a1520")
    draw.line([0, 110, W, 110], fill="#c8a800", width=4)
    t(36,    14, "ON5AM",                                  "#c8a800", 48, mono=True)
    t(W//2,  10, "Albert  •  Ans, Wallonie, Belgique  •  JO20SP", "#8899aa", 17, bold=False, anchor="mt")
    t(W//2,  36, "Rig: FlexRadio 6500  •  Membre UBA",    "#8899aa", 15, bold=False, anchor="mt")
    t(W//2,  58, "LoTW  •  eQSL  •  ClubLog  •  QRZ.com", "#5577aa", 15, bold=False, anchor="mt")
    t(W-16,  10, "CONFIRMING OUR QSO",                    "#ffffff", 17, mono=True,  anchor="rt")
    t(W-16,  36, "PSE QSL — TNX 73 !",                    "#c8a800", 17, mono=True,  anchor="rt")
    t(W-16,  58, "hamanalyst.org",                         "#8899aa", 15, bold=False, anchor="rt")

    # ── 2. ZONE CENTRALE (y=114–670) ───────────────────────────────────
    draw.rectangle([0, 114, W, 670], fill="#0d1b2e")
    t(36, 128, "CONFIRMING QSO WITH :", "#8899aa", 16, bold=False)

    dx_call    = str(qso.get("call",    "") or "——") if qso else "——"
    dx_country = str(qso.get("country", "") or "")   if qso else ""
    dx_qth     = str(qso.get("qth",     "") or "")   if qso else ""
    t(36, 154, dx_call, "#c8a800", 52, mono=True)
    if qso:
        if dx_country: t(480, 160, dx_country, "#ffffff", 22, bold=False)
        if dx_qth:     t(480, 196, dx_qth,     "#8899aa", 18, bold=False)
    else:
        t(36, 196, "← Sélectionnez un QSO dans l'onglet Journal", "#334455", 20, bold=False)

    draw.line([36, 256, W-36, 256], fill="#1e3a5a", width=2)

    def qval(key, default="——"):
        return str(qso.get(key) or default) if qso else "——"

    if qso:
        try:
            _f = _freq_mhz(qso.get("freq", ""))
            freq_disp = f"{_f} MHz" if _f else str(qso.get("band") or "——")
        except Exception:
            freq_disp = str(qso.get("band") or "——")
    else:
        freq_disp = "——"

    qso_cols = [("DATE", qval("date")), ("TIME UTC", qval("time")),
                ("BAND", qval("band")), ("MODE",     qval("mode")),
                ("FREQ", freq_disp),    ("RST SENT", qval("rst_s")),
                ("RST RCVD", qval("rst_r"))]
    cw = (W - 72) // len(qso_cols)
    for i, (lbl, val) in enumerate(qso_cols):
        x = 36 + i * cw
        t(x, 272, lbl, "#8899aa", 14, bold=False)
        t(x, 294, val, "#ffffff", 22, mono=True)

    draw.line([36, 356, W-36, 356], fill="#1e3a5a", width=2)

    sta_cols = [("RIG", "FlexRadio 6500"), ("ANTENNA", qval("ant")),
                ("POWER", "100W"), ("GRID", "JO20SP"),
                ("QSL VIA", "Bureau / Direct / LoTW")]
    cw2 = (W - 72) // len(sta_cols)
    for i, (lbl, val) in enumerate(sta_cols):
        x = 36 + i * cw2
        t(x, 372, lbl, "#8899aa", 14, bold=False)
        t(x, 394, val, "#ffffff", 20, mono=True)

    draw.line([36, 452, W-36, 452], fill="#1e3a5a", width=2)
    t(W//2, 468, "Confirming our QSO with pleasure !", "#7799bb", 18, bold=False, anchor="mt")
    t(W//2, 504, "✓ LoTW    ✓ eQSL    ✓ ClubLog    ✓ QRZ.com", "#3a7a4a", 18, mono=True, anchor="mt")
    draw.line([36, 564, W-36, 564], fill="#1e3a5a", width=2)
    t(36,   576, "CQ: 14  •  ITU: 27  •  Region 1  •  UBA", "#8899aa", 16, bold=False)
    t(W-36, 576, "hamanalyst.org/qsl",                        "#446688", 16, bold=False, anchor="ra")

    # ── 3. ZONE DONNÉES BAS (y=670–820) ────────────────────────────────
    draw.rectangle([0, 670, W, 820], fill="#f5f0e0")
    draw.line([0, 670, W, 670], fill="#c8a800", width=4)

    cols_bot = [("TO / CALLSIGN", 232), ("DATE UTC", 164), ("TIME UTC", 140),
                ("BAND", 112), ("MODE", 112), ("FREQ MHz", 164),
                ("RST SENT", 140), ("RST RCVD", 140), ("QSL", 112)]
    vals_bot = (
        [str(qso.get("call","") or ""), str(qso.get("date","") or ""),
         str(qso.get("time","") or ""), str(qso.get("band","") or ""),
         str(qso.get("mode","") or ""), freq_disp,
         str(qso.get("rst_s","") or ""), str(qso.get("rst_r","") or ""), ""]
        if qso else [""] * len(cols_bot)
    )
    cx_ = 12
    for i, (col_lbl, cw3) in enumerate(cols_bot):
        if i > 0:
            draw.line([cx_-2, 672, cx_-2, 818], fill="#c4bda0", width=2)
        t(cx_+4, 680, col_lbl, "#445566", 12)
        draw.line([cx_, 736, cx_+cw3-8, 736], fill="#aaa08a", width=2)
        if col_lbl == "QSL":
            t(cx_+4, 742, "☐ YES  ☐ NO", "#445566", 14, bold=False)
        elif i < len(vals_bot) and vals_bot[i]:
            t(cx_+4, 700, vals_bot[i], "#1a2a3a", 20, mono=True)
        cx_ += cw3

    # ── 4. PIED (y=820–840) ────────────────────────────────────────────
    draw.rectangle([0, 820, W, H], fill="#0a1520")
    t(W//2, 826, "ON5AM  •  Ans, JO20SP  •  Belgique  •  73 de Albert  •  hamanalyst.org",
      "#446688", 14, bold=False, anchor="mt")

    return img


def generate_qsl_pdf(qso: dict) -> str:
    """Génère la carte QSL navy-blue en PDF temporaire pour pièce jointe email."""
    from reportlab.pdfgen import canvas as rl_canvas

    img = _render_qsl_image(qso)

    tmp_jpg = tempfile.mktemp(suffix=".jpg")
    img.save(tmp_jpg, "JPEG", quality=95)

    try:
        tmp_pdf = tempfile.mktemp(suffix=".pdf")
        W, H    = img.size                 # 1360 × 840
        pt_w    = W * 72 / 200            # 200 DPI → points
        pt_h    = H * 72 / 200
        c       = rl_canvas.Canvas(tmp_pdf, pagesize=(pt_w, pt_h))
        c.drawImage(tmp_jpg, 0, 0, pt_w, pt_h)
        c.save()
    finally:
        try:
            os.remove(tmp_jpg)
        except OSError:
            pass

    return tmp_pdf


# ── Classe principale ─────────────────────────────────────────────────────────
class QSLEmailer:
    """Gère la génération de QSL PDF et l'envoi SMTP Gmail.

    Instancié par station_master.py : QSLEmailer(app)
    Appelé via : self._qsl_emailer.send_dialog()
    """

    def __init__(self, app):
        self.app = app

    # ── Helpers config ────────────────────────────────────────────────────────
    def _get_conf(self):
        import configparser
        fresh = configparser.ConfigParser()
        fresh.read(_CONFIG_FILE)
        return fresh

    def _get_smtp_creds(self, conf):
        """Retourne (email, password, host, port) depuis [GMAIL] ou [EMAIL]."""
        if conf and conf.has_section("GMAIL"):
            return (
                conf.get("GMAIL", "email",        fallback=""),
                conf.get("GMAIL", "app_password",  fallback=""),
                "smtp.gmail.com",
                465,
            )
        if conf and conf.has_section("EMAIL"):
            return (
                conf.get("EMAIL", "smtp_user",     fallback=""),
                conf.get("EMAIL", "smtp_password", fallback=""),
                conf.get("EMAIL", "smtp_host",     fallback="smtp.gmail.com"),
                465,
            )
        return ("", "", "smtp.gmail.com", 465)

    # ── Point d'entrée ────────────────────────────────────────────────────────
    def send_dialog(self):
        """Ouvre la fenêtre de confirmation et lance l'envoi."""
        qso = self.app._get_selected_qso()
        if not qso:
            messagebox.showinfo("QSL Email",
                "Sélectionnez d'abord un QSO dans l'onglet Journal.")
            return

        # Compléter freq et rst_rcvd depuis la DB (absents du Treeview)
        try:
            row = self.app.conn.cursor().execute(
                "SELECT freq, rst_rcvd FROM qsos WHERE id=?", (qso["id"],)
            ).fetchone()
            qso["freq"]  = (row[0] or "") if row else ""
            qso["rst_r"] = (row[1] or qso.get("rst_r", "")) if row else qso.get("rst_r", "")
        except Exception:
            qso["freq"] = ""

        conf = self._get_conf()
        smtp_user, smtp_pass, smtp_host, smtp_port = self._get_smtp_creds(conf)

        if not smtp_user or not smtp_pass:
            messagebox.showerror("Config email",
                "Identifiants SMTP manquants.\n\n"
                "Ajoutez dans config.ini :\n\n"
                "[GMAIL]\nemail = on5amplus@gmail.com\n"
                "app_password = xxxx xxxx xxxx xxxx")
            return

        call = qso.get("call", "")

        # Lookup email QRZ (non bloquant — l'utilisateur peut saisir manuellement)
        dest_email = ""
        try:
            dest_email = _qrz_email(call, conf)
        except Exception as e:
            print(f"[QRZ] Lookup échoué : {e}")

        lang = _get_lang(call)
        self._open_confirm_win(qso, lang, dest_email, conf,
                               smtp_user, smtp_pass, smtp_host, smtp_port)

    # ── Fenêtre de confirmation ───────────────────────────────────────────────
    def _open_confirm_win(self, qso, lang, dest_email, conf,
                          smtp_user, smtp_pass, smtp_host, smtp_port):
        from PIL import Image, ImageTk

        root = self.app.root
        win  = tk.Toplevel(root)
        call = qso.get("call", "")
        win.title(f"📧 Envoyer QSL — {call}")
        win.resizable(True, True)
        win.grab_set()

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)

        # ── Miniature QSL générée (400 px de large) ──────────────────────────
        try:
            _img  = _render_qsl_image(qso)
            ratio = 400 / _img.width
            thumb = _img.resize((400, int(_img.height * ratio)), Image.LANCZOS)
            tkimg = ImageTk.PhotoImage(thumb)
            lbl   = tk.Label(frm, image=tkimg)
            lbl.image = tkimg
            lbl.pack(pady=(0, 8))
        except Exception:
            ttk.Label(frm, text="[Aperçu QSL indisponible]").pack()

        # ── Infos QSO ─────────────────────────────────────────────────────────
        ttk.Label(frm,
            text=(f"📡 {call}  |  {qso.get('date','')} {qso.get('time','')} UTC"
                  f"  |  {qso.get('band','')} {qso.get('mode','')}"),
            font=("Consolas", 10, "bold"),
            foreground="#f39c12",
        ).pack(anchor="w")

        ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=6)

        # ── Email destinataire ─────────────────────────────────────────────────
        ef = ttk.Frame(frm); ef.pack(fill="x", pady=2)
        ttk.Label(ef, text="Email destinataire :", width=20, anchor="e").pack(side="left")
        dest_var = tk.StringVar(value=dest_email)
        ttk.Entry(ef, textvariable=dest_var, width=38).pack(side="left", padx=4)
        if not dest_email:
            ttk.Label(ef, text="⚠ Non trouvé sur QRZ",
                      foreground="#e74c3c").pack(side="left", padx=4)

        # ── Sélection langue ───────────────────────────────────────────────────
        lf = ttk.Frame(frm); lf.pack(fill="x", pady=2)
        ttk.Label(lf, text="Langue :", width=20, anchor="e").pack(side="left")
        lang_var = tk.StringVar(value=lang)
        ttk.Combobox(lf, textvariable=lang_var,
                     values=["en", "fr", "de", "nl", "pl", "es", "it", "pt", "ru", "ja", "zh", "id"],
                     width=6, state="readonly").pack(side="left", padx=4)

        # ── Corps email éditable ───────────────────────────────────────────────
        ttk.Label(frm, text="Corps du message :",
                  font=("Arial", 9, "bold")).pack(anchor="w", pady=(8, 2))
        txt = tk.Text(frm, height=10, width=70, wrap="word", font=("Consolas", 9))
        txt.insert("1.0", _email_body(qso, lang))
        txt.pack(fill="both", expand=True)

        def _refresh_body(*_):
            txt.delete("1.0", "end")
            txt.insert("1.0", _email_body(qso, lang_var.get()))

        lang_var.trace_add("write", _refresh_body)

        # ── Boutons ────────────────────────────────────────────────────────────
        def do_send():
            dest = dest_var.get().strip()
            if not dest:
                messagebox.showerror("Email manquant",
                    "Saisissez l'adresse email du destinataire.", parent=win)
                return
            body = txt.get("1.0", "end").strip()
            try:
                pdf_path = generate_qsl_pdf(qso)
            except Exception as exc:
                messagebox.showerror("Erreur PDF",
                    f"Génération PDF échouée :\n{exc}", parent=win)
                return
            win.destroy()
            self._do_smtp(dest, body, pdf_path,
                          smtp_user, smtp_pass, smtp_host, smtp_port,
                          call, qso.get("id"))

        bf = ttk.Frame(frm); bf.pack(fill="x", pady=(10, 0))
        ttk.Button(bf, text="📧 Envoyer",  command=do_send,
                   bootstyle="success",   width=14).pack(side="left",  padx=4)
        ttk.Button(bf, text="✖ Annuler",  command=win.destroy,
                   bootstyle="secondary", width=12).pack(side="right", padx=4)

    # ── Envoi SMTP en thread background ───────────────────────────────────────
    def _do_smtp(self, dest, body, pdf_path,
                 smtp_user, smtp_pass, smtp_host, smtp_port, call, qso_id):
        """Envoie l'email QSL en thread background. Met à jour qsl_sent en DB."""
        from email.mime.multipart  import MIMEMultipart
        from email.mime.text       import MIMEText
        from email.mime.application import MIMEApplication

        root = self.app.root

        def _set_status(msg):
            try:
                self.app.status_var.set(msg)
            except Exception:
                pass

        _set_status(f"📧 Envoi QSL à {call}…")

        def _send():
            try:
                msg             = MIMEMultipart()
                msg["From"]     = smtp_user
                msg["To"]       = dest
                msg["Subject"]  = f"QSL Card — {MY_CALL} × {call}"
                msg.attach(MIMEText(body, "plain", "utf-8"))

                with open(pdf_path, "rb") as fh:
                    att = MIMEApplication(fh.read(), _subtype="pdf")
                att.add_header("Content-Disposition", "attachment",
                               filename=f"QSL_{MY_CALL}_{call}.pdf")
                msg.attach(att)

                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx) as srv:
                    srv.login(smtp_user, smtp_pass)
                    srv.sendmail(smtp_user, dest, msg.as_string())

                # Mise à jour qsl_sent + qsl_email_sent dans la DB
                try:
                    today = datetime.utcnow().strftime("%Y-%m-%d")
                    self.app.conn.execute(
                        "UPDATE qsos SET qsl_sent=?, qsl_email_sent=1 WHERE id=?",
                        (today, qso_id)
                    )
                    self.app.conn.commit()
                    root.after(0, self.app.load_data)
                    tab = getattr(self.app, "_qsl_email_tab", None)
                    if tab is not None:
                        root.after(0, tab.refresh)
                except Exception as db_err:
                    print(f"[QSL] DB update échoué : {db_err}")

                try:
                    os.remove(pdf_path)
                except OSError:
                    pass

                root.after(0, lambda: (
                    messagebox.showinfo("QSL envoyée",
                        f"✅ QSL envoyée à {dest}\nCorrespondant : {call}"),
                    _set_status(f"📧 QSL envoyée à {call} ({dest})"),
                ))

            except Exception as exc:
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
                err_msg = str(exc)
                root.after(0, lambda: messagebox.showerror(
                    "Erreur envoi email",
                    f"Envoi échoué :\n{err_msg}\n\n"
                    "Vérifiez config.ini [GMAIL] et votre App Password.",
                ))

        threading.Thread(target=_send, daemon=True).start()
