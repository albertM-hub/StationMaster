"""
sstv_decoder.py — Décodage SSTV (VIS + image) en pur Python/numpy.

Aucune dépendance à TCI, DAX ou Tkinter : ce module ne fait que du traitement de
signal sur des blocs audio (numpy float32, 48 kHz par défaut). Testable
directement sur un fichier WAV (voir `decode_wav()` et le mode `__main__`).

Modes supportés (Phase 1 — voir docs/plans/2026-08-06-sstv-tab-design.md) :
Scottie 1/2, Martin 1/2, Robot 36.

Avertissement sur les constantes de timing : elles reprennent les valeurs
standard largement documentées et stables depuis des décennies (mêmes valeurs
que QSSTV/MMSSTV/RX-SSTV) et ont été validées par un test synthétique
aller-retour (encodage→décodage interne, voir tests). Mais elles n'ont *pas*
encore été validées contre une vraie capture SSTV hors-air — deux points
précis à confirmer à l'Étape 2 (RX live) :
  - Le "sync bootstrap" ajouté avant la première ligne Scottie (convention
    reprise de pysstv/QSSTV, un pulse sync+porch supplémentaire avant la
    première ligne verte).
  - La reconstruction chrominance de Robot 36 : approximation simplifiée
    (chaque ligne réutilise sa propre chrominance transmise + celle de la
    ligne précédente pour l'autre canal), pas la reconstruction 4:2:0 complète.
"""

import numpy as np

SAMPLE_RATE = 48000

# Fréquences de référence (Hz)
FREQ_SYNC = 1200
FREQ_BLACK = 1500
FREQ_WHITE = 2300
FREQ_VIS_LEADER = 1900
FREQ_VIS_BIT0 = 1300  # bit = 0
FREQ_VIS_BIT1 = 1100  # bit = 1

VIS_LEADER_MS = 300
VIS_BREAK_MS = 10
VIS_BIT_MS = 30


# ------------------------------------------------------------------
# Primitives de traitement du signal
# ------------------------------------------------------------------


def goertzel_power(samples, freq, sample_rate=SAMPLE_RATE):
    """Puissance du signal à `freq` sur la fenêtre `samples` (algorithme de Goertzel)."""
    n = len(samples)
    if n == 0:
        return 0.0
    k = int(0.5 + n * freq / sample_rate)
    w = 2 * np.pi * k / n
    coeff = 2 * np.cos(w)
    q1 = 0.0
    q2 = 0.0
    for s in samples:
        q0 = coeff * q1 - q2 + s
        q2 = q1
        q1 = q0
    return q1 * q1 + q2 * q2 - q1 * q2 * coeff


def _ms_to_n(ms, sample_rate=SAMPLE_RATE):
    return int(round(sample_rate * ms / 1000))


def _analytic_signal(x):
    """Signal analytique via transformée de Hilbert (FFT, numpy pur — pas de scipy)."""
    n = len(x)
    xf = np.fft.fft(x)
    h = np.zeros(n)
    if n % 2 == 0:
        h[0] = h[n // 2] = 1
        h[1 : n // 2] = 2
    else:
        h[0] = 1
        h[1 : (n + 1) // 2] = 2
    return np.fft.ifft(xf * h)


def instantaneous_freq(x, sample_rate=SAMPLE_RATE):
    """Fréquence instantanée de `x` (même longueur que `x`), via Hilbert."""
    if len(x) < 4:
        return np.zeros(len(x))
    analytic = _analytic_signal(x)
    phase = np.unwrap(np.angle(analytic))
    freq = np.diff(phase) / (2 * np.pi) * sample_rate
    return np.concatenate([freq, freq[-1:]])


def freq_to_luma(freq, lo=FREQ_BLACK, hi=FREQ_WHITE):
    """Mappe une fréquence (Hz) vers une luminance 0-255."""
    val = (freq - lo) / (hi - lo) * 255.0
    return np.clip(val, 0, 255)


# ------------------------------------------------------------------
# Détection VIS
# ------------------------------------------------------------------


def find_vis(samples, sample_rate=SAMPLE_RATE):
    """Cherche l'en-tête VIS (leader-break-leader + 7 bits + parité + stop).

    Retourne (vis_code, index_fin_header) ou None si rien trouvé.
    """
    win = _ms_to_n(20, sample_rate)
    hop = _ms_to_n(10, sample_rate)
    if win <= 0 or len(samples) < win:
        return None

    powers = []
    positions = []
    i = 0
    while i + win <= len(samples):
        powers.append(
            goertzel_power(samples[i : i + win], FREQ_VIS_LEADER, sample_rate)
        )
        positions.append(i)
        i += hop
    if not powers:
        return None
    powers = np.array(powers)
    if powers.max() <= 0:
        return None
    threshold = powers.max() * 0.25
    is_leader = powers > threshold

    min_leader_hops = max(1, int(0.7 * VIS_LEADER_MS / 10))  # tolérance -30%
    max_break_hops = int(2 * VIS_BREAK_MS / 10) + 2

    n = len(is_leader)
    idx = 0
    while idx < n:
        if not is_leader[idx]:
            idx += 1
            continue
        # run de leader1
        start1 = idx
        while idx < n and is_leader[idx]:
            idx += 1
        len1 = idx - start1
        if len1 < min_leader_hops:
            continue
        # run de break (creux)
        start_break = idx
        while idx < n and not is_leader[idx]:
            idx += 1
        len_break = idx - start_break
        if len_break == 0 or len_break > max_break_hops:
            continue
        # run de leader2
        start2 = idx
        while idx < n and is_leader[idx]:
            idx += 1
        len2 = idx - start2
        if len2 < min_leader_hops:
            continue

        header_end_sample = positions[idx - 1] + hop  # fin approx. du 2e leader
        result = _read_vis_bits(samples, header_end_sample, sample_rate)
        if result is not None:
            return result
    return None


def _read_vis_bits(samples, start, sample_rate=SAMPLE_RATE):
    """Lit le bit de start, 7 bits de données (LSB first), la parité et le
    bit de stop à partir de l'index `start`. Retourne (vis_code, fin) ou None."""
    slot = _ms_to_n(VIS_BIT_MS, sample_rate)
    pos = start + slot  # on saute le start bit (toujours 1200Hz)
    bits = []
    for _ in range(8):  # 7 bits de données + parité
        if pos + slot > len(samples):
            return None
        chunk = samples[pos : pos + slot]
        p1 = goertzel_power(chunk, FREQ_VIS_BIT1, sample_rate)
        p0 = goertzel_power(chunk, FREQ_VIS_BIT0, sample_rate)
        bits.append(1 if p1 > p0 else 0)
        pos += slot
    data_bits = bits[:7]
    vis_code = sum(b << i for i, b in enumerate(data_bits))
    pos += slot  # bit de stop, non vérifié
    return vis_code, pos


# ------------------------------------------------------------------
# Spécification des modes
# ------------------------------------------------------------------


class ModeSpec:
    """Décrit une ligne comme une suite de segments (type, durée_ms, canal).

    type ∈ {"sync", "porch", "sep", "scan"}. Pour "scan", `canal` indique le
    canal couleur alimenté par ce segment (ex: "G", "B", "R").
    """

    def __init__(
        self, name, vis_code, width, height, line_segments_ms, bootstrap_ms=None
    ):
        self.name = name
        self.vis_code = vis_code
        self.width = width
        self.height = height
        self.line_segments_ms = line_segments_ms
        self.bootstrap_ms = (
            bootstrap_ms or []
        )  # segments joués une seule fois avant la ligne 0

    @property
    def line_ms(self):
        return sum(seg[1] for seg in self.line_segments_ms)


def _scottie_segments(scan_ms):
    return [
        ("sep", 1.5, None),
        ("scan", scan_ms, "G"),
        ("sep", 1.5, None),
        ("scan", scan_ms, "B"),
        ("sync", 9.0, None),
        ("porch", 1.5, None),
        ("scan", scan_ms, "R"),
    ]


def _martin_segments(scan_ms):
    return [
        ("sync", 4.862, None),
        ("porch", 0.572, None),
        ("scan", scan_ms, "G"),
        ("sep", 0.572, None),
        ("scan", scan_ms, "B"),
        ("sep", 0.572, None),
        ("scan", scan_ms, "R"),
    ]


MODES = {
    60: ModeSpec(
        "Scottie 1",
        60,
        320,
        256,
        _scottie_segments(138.240),
        bootstrap_ms=[("sync", 9.0, None), ("porch", 1.5, None)],
    ),
    56: ModeSpec(
        "Scottie 2",
        56,
        320,
        256,
        _scottie_segments(88.064),
        bootstrap_ms=[("sync", 9.0, None), ("porch", 1.5, None)],
    ),
    44: ModeSpec("Martin 1", 44, 320, 256, _martin_segments(146.432)),
    40: ModeSpec("Martin 2", 40, 320, 256, _martin_segments(73.216)),
}

ROBOT36_VIS = 8
ROBOT36_WIDTH = 320
ROBOT36_HEIGHT = 240
# Sync 9ms, porch 3ms, Y scan 88ms, séparateur 4.5ms, chroma scan 44ms
ROBOT36_LINE_MS = 9.0 + 3.0 + 88.0 + 4.5 + 44.0


def mode_info(vis_code):
    """Retourne (nom, durée_approx_s, résolution) pour affichage UI, ou None."""
    if vis_code in MODES:
        m = MODES[vis_code]
        duration_s = (sum(b[1] for b in m.bootstrap_ms) + m.line_ms * m.height) / 1000
        return m.name, duration_s, (m.width, m.height)
    if vis_code == ROBOT36_VIS:
        duration_s = ROBOT36_LINE_MS * ROBOT36_HEIGHT / 1000
        return "Robot 36", duration_s, (ROBOT36_WIDTH, ROBOT36_HEIGHT)
    return None


# ------------------------------------------------------------------
# Décodage image
# ------------------------------------------------------------------


def _decode_scan_segment(samples, width, sample_rate=SAMPLE_RATE):
    """Convertit un segment audio "scan" en `width` valeurs de luminance 0-255."""
    freq = instantaneous_freq(samples, sample_rate)
    n = len(freq)
    if n == 0:
        return np.zeros(width)
    edges = np.linspace(0, n, width + 1).astype(int)
    out = np.zeros(width)
    for i in range(width):
        lo, hi = edges[i], max(edges[i] + 1, edges[i + 1])
        out[i] = np.mean(freq[lo:hi])
    return freq_to_luma(out)


def decode_generic_mode(samples, mode: ModeSpec, slant=1.0, on_line=None):
    """Décode un mode RGB séquentiel (Scottie/Martin) à partir des samples
    juste après l'en-tête VIS. `slant` : facteur de correction (1.0 = neutre).
    `on_line(y, image_partielle)` est appelé après chaque ligne décodée."""
    image = np.zeros((mode.height, mode.width, 3), dtype=np.uint8)
    pos = 0
    for seg_type, dur_ms, _ in mode.bootstrap_ms:
        pos += _ms_to_n(dur_ms * slant, sample_rate=SAMPLE_RATE)

    for y in range(mode.height):
        for seg_type, dur_ms, channel in mode.line_segments_ms:
            n = _ms_to_n(dur_ms * slant, sample_rate=SAMPLE_RATE)
            if pos + n > len(samples):
                if on_line:
                    on_line(y, image)
                return image
            if seg_type == "scan":
                chunk = samples[pos : pos + n]
                luma = _decode_scan_segment(chunk, mode.width)
                ch_idx = {"R": 0, "G": 1, "B": 2}[channel]
                image[y, :, ch_idx] = luma.astype(np.uint8)
            pos += n
        if on_line:
            on_line(y, image)
    return image


def _ycrcb_to_rgb(y, cr, cb):
    r = y + 1.402 * (cr - 128)
    g = y - 0.344136 * (cb - 128) - 0.714136 * (cr - 128)
    b = y + 1.772 * (cb - 128)
    return (
        np.clip(r, 0, 255).astype(np.uint8),
        np.clip(g, 0, 255).astype(np.uint8),
        np.clip(b, 0, 255).astype(np.uint8),
    )


def decode_robot36(samples, slant=1.0, on_line=None):
    """Décode Robot 36 (YCrCb, chroma sous-échantillonnée). Approximation :
    chaque ligne réutilise la chrominance de la ligne impaire/paire la plus
    récente plutôt qu'une reconstruction 4:2:0 complète (voir avertissement
    en tête de fichier)."""
    width, height = ROBOT36_WIDTH, ROBOT36_HEIGHT
    image = np.zeros((height, width, 3), dtype=np.uint8)
    y_lines = np.zeros((height, width))
    cr_last = np.full(width, 128.0)
    cb_last = np.full(width, 128.0)

    pos = 0
    sync_n = _ms_to_n(9.0 * slant)
    porch_n = _ms_to_n(3.0 * slant)
    y_n = _ms_to_n(88.0 * slant)
    sep_n = _ms_to_n(4.5 * slant)
    chroma_n = _ms_to_n(44.0 * slant)

    for y in range(height):
        needed = sync_n + porch_n + y_n + sep_n + chroma_n
        if pos + needed > len(samples):
            if on_line:
                on_line(y, image)
            return image
        pos += sync_n + porch_n
        y_luma = freq_to_luma(instantaneous_freq(samples[pos : pos + y_n]))
        y_edges = np.linspace(0, len(y_luma), width + 1).astype(int)
        y_row = np.array(
            [
                np.mean(y_luma[y_edges[i] : max(y_edges[i] + 1, y_edges[i + 1])])
                for i in range(width)
            ]
        )
        pos += y_n + sep_n

        chroma = freq_to_luma(instantaneous_freq(samples[pos : pos + chroma_n]))
        c_edges = np.linspace(0, len(chroma), width + 1).astype(int)
        chroma_row = np.array(
            [
                np.mean(chroma[c_edges[i] : max(c_edges[i] + 1, c_edges[i + 1])])
                for i in range(width)
            ]
        )
        pos += chroma_n

        if y % 2 == 0:
            cr_last = chroma_row
        else:
            cb_last = chroma_row

        r, g, b = _ycrcb_to_rgb(y_row, cr_last, cb_last)
        image[y, :, 0] = r
        image[y, :, 1] = g
        image[y, :, 2] = b
        if on_line:
            on_line(y, image)
    return image


# ------------------------------------------------------------------
# Orchestration
# ------------------------------------------------------------------


def decode(samples, sample_rate=SAMPLE_RATE, slant=1.0, on_line=None, on_vis=None):
    """Point d'entrée haut niveau : cherche le VIS puis décode l'image.

    Retourne (nom_mode, image np.uint8 HxWx3) ou (None, None) si aucun VIS
    détecté.
    """
    found = find_vis(samples, sample_rate)
    if found is None:
        return None, None
    vis_code, header_end = found
    if on_vis:
        on_vis(vis_code)

    remaining = samples[header_end:]
    if vis_code in MODES:
        image = decode_generic_mode(
            remaining, MODES[vis_code], slant=slant, on_line=on_line
        )
        return MODES[vis_code].name, image
    if vis_code == ROBOT36_VIS:
        image = decode_robot36(remaining, slant=slant, on_line=on_line)
        return "Robot 36", image
    return f"VIS inconnu ({vis_code})", None


def detect_fsk_id(samples, sample_rate=SAMPLE_RATE):
    """FSK ID (indicatif en fin de transmission) : non implémenté en Phase 1.

    Toujours retourne None — pas de comportement inventé silencieusement.
    """
    return None


def decode_wav(path, **kwargs):
    """Décode un fichier WAV mono 16 bits. Utilitaire de test/CLI."""
    import wave

    with wave.open(path, "rb") as wf:
        sample_rate = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    return decode(samples, sample_rate=sample_rate, **kwargs)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Décode un fichier WAV SSTV (test hors-ligne)."
    )
    parser.add_argument("wav_path")
    parser.add_argument("--out", default="sstv_decoded.png")
    args = parser.parse_args()

    mode_name, image = decode_wav(args.wav_path)
    if image is None:
        print(f"Aucun VIS détecté ({mode_name}).")
    else:
        print(f"Mode détecté : {mode_name}, image {image.shape}")
        from PIL import Image

        Image.fromarray(image).save(args.out)
        print(f"Sauvegardé dans {args.out}")
