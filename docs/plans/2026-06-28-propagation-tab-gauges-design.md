# Design — Jauges visuelles pour le tab Propagation

Date : 2026-06-28
Fichier concerné : `station_master.py`, méthodes `_build_propagation_tab` / `_update_prop_ui` / `_draw_muf_chart` (lignes ~2887-3187)

## Objectif

Enrichir le panneau gauche du tab Propagation avec des cadrans visuels style "S-mètre" pour SFI, K-index et A-index, tout en conservant le graphique MUF existant à droite et en améliorant la lisibilité générale du panneau.

## Décisions validées

- **Style** : jauges semi-circulaires (gauges analogiques), pas de barres ni LED.
- **Techno** : matplotlib (mini-`Figure` par jauge), cohérent avec le MUF chart déjà présent dans le tab.
- **Conditions** (texte qualitatif type "🟢 Bon") : reste un label texte coloré, pas de jauge dédiée — redondant avec la jauge K-index.
- **Layout** : panneau gauche élargi (`minsize=320` → `440`) plutôt que jauges compactes ou scroll, pour garder une bonne lisibilité sans complexifier le scroll.

## Architecture

### Jauges (3 : SFI, K-index, A-index)

Chaque jauge = une mini `Figure(figsize=(2.2, 1.5))` + `FigureCanvasTkAgg`, stockée dans `self._gauges[key] = (fig, canvas, vmin, vmax, zones)`. Rendu en arc 180° avec zones colorées de fond + aiguille (ligne blanche épaisse) pointant la valeur courante. Redessiné via `fig.clear()` + replot à chaque refresh (même pattern que `_draw_muf_chart`), pas de recréation de widget.

Seuils de zones :
- **SFI** (0–300) : <70 rouge, 70–120 jaune, 120–200 vert, >200 violet
- **K-index** (0–9) : 0–2 vert, 3–4 jaune, 5–6 orange, 7–9 rouge
- **A-index** (0–100) : 0–10 vert, 10–30 jaune, 30–50 orange, >50 rouge

Couleurs réutilisées depuis la palette existante (`color_map` déjà défini dans `_update_prop_ui`) : `#2ecc71` vert, `#f39c12` jaune/orange, `#e74c3c` rouge, fond `#11273f`.

### Intégration

**`_build_propagation_tab`** :
- La boucle qui crée les 7 labels (`SFI, SN, K-index, A-index, Conditions, Hémisphère N, Hémisphère S`) est scindée.
- SFI / K-index / A-index → remplacés par une frame horizontale `self.gauge_frame` contenant les 3 mini-canvases matplotlib.
- SN / Conditions / Hémisphère N/S → restent des labels texte (inchangés).

**`_update_prop_ui`** : après le calcul de `data`, ajout de :
```python
for key in ("SFI", "K-index", "A-index"):
    self._draw_gauge(key, data.get(key, "--"))
```

**Nouvelle méthode `_draw_gauge(key, val_str)`** : parse float (fallback 0 si invalide), récupère le tuple depuis `self._gauges[key]`, redessine arc + zones + aiguille, `canvas.draw()`.

**Gestion d'erreur** : si le fetch réseau échoue (déjà géré dans `_fetch_propagation_data`), aucun redraw n'est déclenché — les jauges gardent leur dernière valeur affichée, cohérent avec le comportement actuel des labels texte.

### Layout final du panneau gauche

1. Boutons (Actualiser / DX Maps / VOACAP / VOACAP P2P) — inchangé
2. **Nouveau** : frame `self.gauge_frame` avec 3 jauges SFI/K-index/A-index côte à côte
3. Labels texte : SN, Conditions, Hémisphère N/S — inchangés (juste retirés de la boucle de jauges)
4. Séparateur, Greyline — inchangé
5. Séparateur, tableau Conditions par bande — inchangé
6. Séparateur, VOACAP P2P — inchangé

Panneau droit (MUF chart) : inchangé en logique, juste moins large par défaut (sash ajustable par l'utilisateur).

## Hors scope

- Pas de changement à la mécanique de fetch (`_fetch_propagation_data`, thread, `root.after`).
- Pas de changement au tableau de bandes, à VOACAP P2P, ni au calcul Greyline.
- Pas de jauge pour "Conditions" (reste texte).
