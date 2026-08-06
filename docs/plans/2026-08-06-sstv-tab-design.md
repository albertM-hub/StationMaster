# Onglet SSTV (RX+TX) — Design

Date : 2026-08-06
Statut : validé, prêt pour implémentation (Étape 0)

## Contexte

Nouvel onglet SSTV inspiré de Nexus, utilisant le flux audio du Flex-6500 via
AetherSDR/TCI. Cahier des charges original fourni par l'utilisateur (RX auto avec
détection VIS + décodage progressif, TX avec PTT). Règle d'or : nouveaux fichiers
séparés, aucune logique métier ajoutée à `station_master.py`.

## Audit préalable (résumé)

- **Aucun protocole TCI n'existe dans le repo.** Zéro occurrence de "TCI" dans le
  code. AetherSDR est piloté uniquement via `rigctld`/Hamlib (`flex_client.py:158-244`,
  port 4532) pour fréquence/mode/S-meter — pas d'audio, pas de contrôle TX par ce
  chemin.
- Le pipeline UDP existant (`WSJTXPacket`, `config.ini [UDP]`) ne transporte **jamais
  d'audio brut** — uniquement des métadonnées de QSO déjà décodées par Decodium.
  Inutilisable comme base pour le SSTV.
- `FlexClient.set_tx(active: bool)` existe déjà (`flex_client.py:313-314`, envoie
  `xmit 1`/`xmit 0`) mais **n'est appelé nulle part** actuellement — réutilisable tel
  quel pour le PTT SSTV.
- Aucune trace de séquence de démarrage/race condition documentée, ni du bug
  "3-cycle FT8/WSJT-X" évoqué dans le cahier des charges initial — à surveiller à
  l'implémentation mais sans précédent technique dans le repo.
- Pas de device audio virtuel configuré, pas de lib audio dans `requirements.txt`
  (seul `numpy` est présent).
- Port TCI d'AetherSDR : **5001** (indiqué par l'utilisateur, non garanti — à
  confirmer en implémentation, donc rendu configurable plutôt que codé en dur).

**Conséquence** : le client TCI est un sous-système entièrement à écrire, pas un
branchement sur un flux déjà en place.

## Choix techniques

- **Décodage et encodage SSTV : hand-roll pur Python/numpy, pas de dépendance
  `pysstv`.** Le décodage doit de toute façon être écrit à la main (pas de lib PyPI
  maintenue pour ça) ; une fois cette logique de signal existante, l'encodage est la
  moitié la plus simple du même problème — un seul corpus de logique VIS/timing
  plutôt que de mélanger un encodeur tiers et un décodeur maison. Seule dépendance
  déjà présente (`numpy`) suffit.
- Port TCI configurable via une nouvelle section `[TCI]` dans `config.ini`, défaut
  `5001`.

## Fichiers et responsabilités

- `tci_client.py` — client TCI générique (WebSocket, spec publique Expert
  Electronics). Thread dédié. RX : file `queue.Queue` de blocs PCM (numpy arrays).
  TX : méthode `send_audio(samples)`. Aucune dépendance Tkinter — testable en
  standalone (script CLI, dump vers WAV).
- `sstv_decoder.py` — pur signal processing : détection VIS (corrélation/Goertzel
  sur tons de calibration 1200/1300 Hz), décodeurs ligne par ligne par mode
  (Scottie 1/2, Martin 1/2, Robot 36), détection FSK ID. Entrée : blocs audio.
  Sortie : callback de mise à jour d'image progressive + métadonnées. Testable avec
  un fichier WAV, sans TCI ni Tkinter.
- `sstv_encoder.py` — encode une `PIL.Image` + mode choisi en tableau de samples
  audio (VIS header + scan lines + FSK ID optionnel avec `MY_CALL`).
- `tab_sstv.py` — onglet Tkinter : waterfall, sélecteurs mode/bande, boutons
  Arm/Send/Stop, galerie. Orchestration : instancie `TCIClient`, pousse les blocs RX
  vers `sstv_decoder`, gère le PTT via `app.flex_client.set_tx()`, garde d'usage
  exclusif vs Decodium. Crée la table `sstv_images` via
  `CREATE TABLE IF NOT EXISTS` sur la connexion SQLite partagée de `app`.

## Chaîne RX

- Connexion TCI établie à l'ouverture de l'onglet (pas au démarrage de l'app). Échec
  de connexion → message clair dans l'onglet + bouton "Reconnecter", pas de retry
  agressif.
- Garde Decodium : avant "Arm", vérifie si Decodium tourne (port UDP déjà occupé, ou
  process check) → avertissement bloquant si actif (usage exclusif, jamais
  simultané).
- "Arm" démarre un thread daemon consommant la queue audio TCI en continu.
- Waterfall : FFT glissante (numpy `rfft`, fenêtres ~50ms) → colormap spectrogramme
  → rendu via `self._tk_queue` (cohérent avec le pattern déjà utilisé pour
  CAT/cluster/solar).
- Détection VIS en continu sur le même flux → identification du mode → décodage
  ligne par ligne avec callback `on_line_decoded()` mettant à jour l'image affichée
  en direct (pas seulement à la fin).
- Slider Slant : recalcule la correction de timing sur l'image déjà décodée, pas
  juste un ré-affichage cosmétique.
- Fin de réception (dernière ligne ou timeout) → sauvegarde auto + réinitialisation
  pour la détection VIS suivante.
- Sélecteur manuel de mode en bas si l'auto-détection échoue, avec info
  durée/résolution par mode.

## Chaîne TX

- "Choose image..." (`filedialog`, drop optionnel si simple à intégrer) →
  recadrage cover-crop `PIL` à la résolution du mode choisi.
- `sstv_encoder.encode(image, mode)` → tableau de samples.
- PTT : `set_tx(True)` → pause ~200ms → `tci_client.send_audio()` en streaming par
  blocs → `set_tx(False)` **dans un `finally`** pour garantir la coupure même en cas
  d'erreur pendant l'envoi (point sensible identifié explicitement).
- "Stop" interrompt la boucle d'envoi et force le passage au `finally` de coupure
  PTT immédiatement.
- Indicateur "TX On"/"TX Off" reflète l'état réel retourné par `set_tx()`, pas
  l'intention.
- Pas de slider Slant en TX (RX seulement).

## Stockage / galerie

- Table `sstv_images` (`id, timestamp, callsign, mode, freq_hz, image_path,
  direction`) — `direction` = 'rx'/'tx' pour retrouver aussi les images envoyées.
- Images stockées dans `sstv_images/` à la racine du repo, nommage
  `YYYYMMDD_HHMMSS_MODE.png`.
- Galerie en bas de l'onglet : miniatures + colonnes callsign/mode/fréquence/date,
  double-clic pour taille réelle.

## Intégration onglet

- Pattern strict `tab_satellites.py` : frame ajouté au `Notebook` avant l'import,
  `try/except Exception` autour de l'import + instanciation, message d'erreur dans
  l'onglet plutôt que crash de l'appli. Placé après l'onglet Satellites dans l'ordre
  de création.
- Bandeau haut : mode/fréquence/bande, slider Slant, bouton Arm, indicateur
  connexion TCI, indicateur TX On/Off.
- `tab_wiki.py` mis à jour avec une section documentant RX auto/TX manuel,
  dépendance AetherSDR/TCI (port configurable), rappel usage exclusif vs Decodium.

## Plan de livraison phasé

1. **TCI client isolé** — script CLI testant `tci_client.py` seul (connexion port
   5001, dump audio reçu vers WAV).
2. **Décodeur hors-ligne** — `sstv_decoder.py` testé sur fichiers WAV connus, un par
   mode, sans TCI ni Tkinter.
3. **RX live minimal** — `tab_sstv.py` avec waterfall + Arm + décodage live, sans
   galerie ni TX. Test réel sur un signal SSTV connu.
4. **Galerie** — table `sstv_images` + sauvegarde auto + vue galerie.
5. **Encodeur isolé** — `sstv_encoder.py` testé en aller-retour encode→decode via le
   décodeur de l'étape 2, avant de toucher au TX live.
6. **TX live** — Send/Stop, PTT réel, vérification stricte du `finally` de coupure.
7. **Wiki + checklist finale** — pas de régression Decodium/Flex, fichier principal
   inchangé.

Chaque étape est un point d'arrêt pour validation avant la suivante.
