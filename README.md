# 🎙️ ON5AM Station Master V21.0

**Ham Radio Logbook & Station Management — by ON5AM (Albert)**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://github.com/albertM-hub)

---
![Ham Radio Logbook Station Master ON5AM](https://raw.githubusercontent.com/albertM-hub/StationMaster/main/vignette_station_master.png)
## 🇫🇷 Français

### Description

**Station Master V21.0** est un logbook radio amateur complet développé en Python, conçu pour les radioamateurs qui veulent gérer leur station depuis une interface moderne et intuitive.

### ✨ Fonctionnalités principales

- 📖 **Journal de trafic** — Enregistrement automatique ou manuel des QSOs
- 🔗 **Intégration WSJT-X** — Réception automatique des QSOs via UDP (port configurable)
- 🌍 **Carte Live** — Visualisation des QSOs sur carte interactive avec greyline animée
- 📡 **DX Cluster** — Spots en temps réel avec filtres par bande/mode/pays
- 🏆 **DXCC & Awards** — Suivi de progression DXCC, WAZ, WAS
- 📊 **Statistiques & Graphiques** — Analyse complète de l'activité
- 🌐 **Propagation** — Indices SFI, K, A en temps réel
- 📬 **QSL Manager** — Suivi eQSL, LoTW, ClubLog
- 🖨️ **Cartes QSL** — Génération de cartes QSL personnalisées
- 📻 **PSK Reporter** — Visualisation des spots PSK Reporter
- 🗺️ **Heatmap** — Carte de chaleur de l'activité mondiale
- 💾 **Backup automatique** — Sauvegarde à chaque fermeture

### 📥 Installation (source)

**Prérequis :**
```
Python 3.10+
```

**Installer les dépendances :**
```bash
pip install ttkbootstrap tkintermapview requests pyserial matplotlib pillow reportlab win10toast
```

**Lancer l'application :**
```bash
python mon_logbook.py
```

### 📦 Télécharger le .exe (Windows)

👉 **[Télécharger la dernière version](https://github.com/albertM-hub/StationMaster/releases/latest)**

Aucune installation requise — placez le `.exe` dans un dossier et lancez-le.  
`config.ini` et `mon_logbook.db` seront créés automatiquement au premier lancement.

### ⚙️ Configuration WSJT-X

Dans WSJT-X → **File → Settings → Reporting** :
```
UDP Server    : 224.0.0.1
Port          : 2237
✅ Accept UDP requests
```

Dans Station Master → **⚙️ Paramètres → 📻 UDP / WSJT-X** :
```
Source : wsjtx
Port   : 2237
```

### 🔨 Compiler le .exe soi-même

```bash
pip install pyinstaller
python -m PyInstaller StationMaster_ON5AM.spec --clean
```
Le `.exe` sera dans `dist\StationMaster_ON5AM.exe`.

---

## 🇬🇧 English

### Description

**Station Master V21.0** is a full-featured ham radio logbook built in Python, designed for amateur radio operators who want to manage their station from a modern and intuitive interface.

### ✨ Key Features

- 📖 **QSO Log** — Automatic or manual QSO recording
- 🔗 **WSJT-X Integration** — Automatic QSO reception via UDP (configurable port)
- 🌍 **Live Map** — Interactive QSO map with animated greyline
- 📡 **DX Cluster** — Real-time spots with band/mode/country filters
- 🏆 **DXCC & Awards** — DXCC, WAZ, WAS progress tracking
- 📊 **Statistics & Charts** — Full activity analysis
- 🌐 **Propagation** — Real-time SFI, K, A indices
- 📬 **QSL Manager** — eQSL, LoTW, ClubLog tracking
- 🖨️ **QSL Cards** — Custom QSL card generator
- 📻 **PSK Reporter** — PSK Reporter spot display
- 🗺️ **Heatmap** — Global activity heatmap
- 💾 **Auto Backup** — Saved on every close

### 📥 Installation (from source)

**Requirements:**
```
Python 3.10+
```

**Install dependencies:**
```bash
pip install ttkbootstrap tkintermapview requests pyserial matplotlib pillow reportlab win10toast
```

**Run:**
```bash
python mon_logbook.py
```

### 📦 Download .exe (Windows)

👉 **[Download latest release](https://github.com/albertM-hub/StationMaster/releases/latest)**

No installation needed — place the `.exe` in a folder and run it.  
`config.ini` and `mon_logbook.db` will be created automatically on first launch.

### ⚙️ WSJT-X Configuration

In WSJT-X → **File → Settings → Reporting**:
```
UDP Server    : 224.0.0.1
Port          : 2237
✅ Accept UDP requests
```

In Station Master → **⚙️ Settings → 📻 UDP / WSJT-X**:
```
Source : wsjtx
Port   : 2237
```

### 🔨 Build the .exe yourself

```bash
pip install pyinstaller
python -m PyInstaller StationMaster_ON5AM.spec --clean
```
The `.exe` will be in `dist\StationMaster_ON5AM.exe`.

---

## 📁 Files

| File | Description |
|------|-------------|
| `mon_logbook.py` | Main source code |
| `StationMaster_ON5AM.spec` | PyInstaller build config |
| `radio.ico` | Application icon |
| `config.ini` | *(auto-created)* Station settings |
| `mon_logbook.db` | *(auto-created)* QSO database |

---

## 📜 License

MIT License — free to use, modify and distribute.  
**73 de ON5AM** 🎙️
