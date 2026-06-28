# Design — Tab "Logbook Analysis"

Date : 2026-06-28
Fichier concerné : `station_master.py` (nouvelle méthode `_build_logbook_analysis_tab` + helpers), inséré après le tab Propagation.
Source : `logbook_analysis_base.py` (structure de base fournie par l'utilisateur, à intégrer et corriger).

## Objectif

Ajouter un tab "📊 Logbook Analysis" indépendant : stats QSO locales (total, indicatifs confirmés, bandes actives, dernier QSO), treeview par bande, graphiques matplotlib (Bandes/Modes/USA States/Timeline/Awards), export CSV.

## Décisions validées

- **Chevauchement avec Graphiques/Statistiques** : accepté, nouveau tab indépendant, pas de fusion ni de réutilisation de code entre tabs.
- **Palette** : accent cyan `#00d4ff` conservé (identité visuelle propre pour ce tab), fond `#11273f`/`#0d1e30` inchangé.
- **Position** : inséré juste après le tab Propagation, avant Journal.

## Architecture

### Intégration structurelle

- `_build_logbook_analysis_tab(self, parent)` — signature alignée sur le pattern existant (`_build_propagation_tab(self, parent)`, etc.), `parent` est le `tk.Frame` créé par l'appelant.
- Insertion dans `__init__` (juste après le bloc Propagation) :
  ```python
  t_loganalysis = tk.Frame(self.nb, bg=BG); self.nb.add(t_loganalysis, text="📊 Logbook Analysis")
  self._build_logbook_analysis_tab(t_loganalysis)
  ```
- Variables d'instance ajoutées dans `__init__` : `self.logbook_qsos_var`, `self.logbook_dxcc_var`, `self.logbook_bands_var`, `self.logbook_last_qso_var`, `self.logbook_graph_var`.
- Tous les emojis mojibake corrigés en UTF-8 propre (`📊`, `🌍`, `📡`, `📅`, `📋`, `🔄`, `📤`, `🇺🇸`, `🏆`).

### Threading et données

- `_refresh_logbook_analysis()` → `threading.Thread(daemon=True)` sur `_fetch_logbook_data()`, résultat renvoyé via `self.root.after(0, lambda: self._update_logbook_ui(...))` — même pattern que `_fetch_propagation_data`/`_update_prop_ui`.
- Le calcul "DXCC Confirmés" est en réalité un comptage d'indicatifs distincts avec QSL reçue, pas une vraie logique DXCC (qui existe déjà ailleurs via `cty.dat`). Renommé honnêtement en **"📡 Indicatifs confirmés"** pour ne pas induire en erreur.
- Stats par bande (treeview `band/qsos/pct/dxcc`) inchangées dans leur requête SQL, basées sur les colonnes réelles de `qsos` (`qsl_rcvd`, `lotw_stat`, `eqsl_stat`).

### Graphiques

- Remplacement de `plt.subplots()` (pyplot global, fuite mémoire à chaque régénération) par le pattern déjà utilisé dans `_build_graphs_tab` : `Figure(figsize=..., facecolor=...)` instanciée directement, widget détruit/recréé à chaque clic "Générer" (le frame est vidé via `winfo_children()` + `destroy()` avant chaque génération).
- 5 types de graphiques conservés : Bandes (bar), Modes (pie), USA States (texte simple, approximation par préfixe W/K/N), Timeline (line), Awards (bar estimé) — logique SQL inchangée par rapport au fichier de base, sauf le rendu matplotlib.

### Export CSV

- Correction des `headers` : la liste fournie (19 colonnes) ne correspondait pas aux 21 colonnes réelles de la table `qsos` (`id, qso_date, time_on, callsign, band, mode, rst_sent, rst_rcvd, name, qth, qsl_sent, qsl_rcvd, distance, grid, freq, qrz_stat, eqsl_stat, lotw_stat, club_stat, comment, qsl_email_sent`). Headers alignés 1:1 sur `SELECT * FROM qsos`.

### Gestion d'erreur

- `try/except` avec `print()` + `self.status_var.set(str(e)[:50])`, cohérent avec le reste de l'app (pas de nouveau pattern introduit).

## Plan de test

1. `python3 -m py_compile station_master.py`
2. Lancer l'app sur le display réel, capture d'écran (`spectacle`) du nouveau tab
3. Vérifier : remplissage des 4 stat-boxes après "🔄 Actualiser", treeview par bande peuplé, les 5 types de graphique se génèrent sans erreur, export CSV avec le bon nombre de colonnes

## Hors scope

- Pas de vraie logique DXCC (réutilisation `cty.dat` serait un projet séparé).
- Pas de fusion/déduplication avec les tabs Graphiques ou Statistiques existants.
- `logbook_analysis_base.py` n'est pas supprimé ni commité — fichier de travail de l'utilisateur.
