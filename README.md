# 🎙️ Station Master

**Logbook radio amateur & gestion de station — par ON5AM (Albert)**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-lightgrey.svg)](https://github.com/albertM-hub/StationMaster)

![Station Master](logo/station_masters.png)

---

## 🇫🇷 Français

### Description

**Station Master** est un logbook radio amateur complet écrit en Python (Tkinter / ttkbootstrap), base SQLite. Il gère le journal de trafic, les confirmations QSL, les diplômes, la propagation et le matériel de la station (FlexRadio, ampli SPE Expert). Les QSO FT8 arrivent automatiquement depuis **Decodium** (ou WSJT-X) par UDP.

Développé et utilisé au quotidien sous Linux (Kubuntu) ; le code prend aussi en charge Windows.

### 🗂️ Les onglets

| Onglet | Rôle |
|--------|------|
| 🏠 Dashboard | QSOs du jour, DXCC travaillés/confirmés, propagation, barres Awards, activité |
| 📻 Flex-6500 | Pilotage et mesures du transceiver FlexRadio |
| ⚡ SPE | Ampli SPE Expert 1.3K-FA (port série) |
| 🌐 Propagation | SFI, K, A, MUF estimée, synthèse des conditions du jour |
| 📊 Logbook Analysis | Statistiques du log, bandes prioritaires pour les diplômes multi-bandes |
| 🔴 Journal | Saisie et liste des QSOs, envoi automatique QRZ / eQSL / LoTW / Club Log |
| 🌍 Carte Live | Carte des QSOs et des spots |
| 📧 QSL Email | Envoi des cartes QSL par e-mail |
| 🖨️ QSL Card | Création de cartes QSL (PNG / PDF) |
| 🌙 Grayline | Carte jour/nuit en temps réel |
| 🛰️ Satellites | Prochains passages des satellites radioamateurs |
| 📡 DX Live | DX Cluster enrichi et DXpéditions |
| 📻 PSK Reporter | Où votre signal est entendu |
| 🌍 DX World / DXCC | Les 340 entités DXCC, statut travaillé / confirmé |
| 📊 Graphiques | QSOs par bande, mode, année |
| 🗺️ Heatmap | Densité des QSOs par locator |
| 🏆 Contests | Calendrier des contests (WA7BNM) |
| 📖 Wiki | Aide intégrée |

### 📋 Prérequis

- **Python 3.10 ou plus récent**
- `tkinter` : fourni avec Python sous Windows ; sous Debian/Ubuntu, paquet `python3-tk`
- Bibliothèques Python : voir [`requirements.txt`](requirements.txt) — ttkbootstrap, tkintermapview, requests, pyserial, matplotlib, Pillow, reportlab, skyfield (+ win10toast, optionnel, sous Windows)

### 📥 Installation — Linux (Debian, Ubuntu, Kubuntu)

```bash
sudo apt install python3-tk python3-venv git
git clone https://github.com/albertM-hub/StationMaster.git
cd StationMaster
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 📥 Installation — Windows

Installez Python 3.10+ depuis [python.org](https://www.python.org/downloads/) (tkinter est inclus), puis dans une invite de commandes :

```bat
git clone https://github.com/albertM-hub/StationMaster.git
cd StationMaster
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 🚀 Lancement

```bash
# Linux (environnement virtuel activé)
python3 station_master.py
```

```bat
:: Windows (environnement virtuel activé)
py station_master.py
```

Le programme peut être lancé depuis n'importe quel répertoire : `config.ini`, la base `station_master.db`, `cty.dat` (base DXCC) et la carte greyline sont créés ou téléchargés dans le dossier de `station_master.py` au premier démarrage.

### ⚙️ Configuration

Au premier lancement, ouvrez **⚙️ Paramètres** et indiquez votre indicatif, votre locator, le port CAT et, si vous les utilisez, vos identifiants QRZ / eQSL / LoTW / Club Log et le port de l'ampli SPE Expert.

Vous pouvez aussi partir du modèle :

```bash
cp config.ini.example config.ini
```

> `config.ini` contient vos mots de passe et clés : il est exclu du dépôt par `.gitignore`, ne le publiez jamais.

> **Carte QSL** : modèle de carte personnel (FlexRadio 6500, Ultrabeam, 100W, Membre UBA, CQ/ITU/Région 1), à adapter dans `tab_qsl.py`.

### 📡 Réception des QSO FT8 (Decodium ou WSJT-X)

Dans Decodium → **Settings → Reporting** :

```
UDP Server    : 224.0.0.1      Port : 2237
✅ Accept UDP requests
✅ N1MM Logger+ Broadcasts : 127.0.0.1      Port : 2333
```

Chaque QSO validé dans Decodium (Log QSO → OK) arrive dans le Journal, par l'ADIF du port 2333 ou par le port 2237, sans doublon. Le bandeau en haut à droite affiche `RX: Decodium UDP 2237 + ADIF 2333`.

> Sous Linux, le multicast 224.0.0.1 sur l'interface `lo` n'aboutit souvent pas : le port 2333 suffit.

### 📦 Exécutable Linux

La page [Releases](https://github.com/albertM-hub/StationMaster/releases) propose une archive Linux (v1.0.0, juin 2026) **antérieure à cette version**. Pour la version à jour, installez depuis les sources ou compilez vous-même :

```bash
pip install pyinstaller
pyinstaller station_master_linux.spec --clean
```

Le binaire se trouve dans `dist/station_master/station_master`.

### 🖥️ Installer dans le menu d'applications (Kubuntu)

```bash
mkdir -p ~/Applications
cp -r dist/station_master ~/Applications/
chmod +x ~/Applications/station_master/station_master
cp station_master.desktop ~/.local/share/applications/
```

> Si votre dossier personnel n'est pas `/home/albert`, éditez les chemins `Exec=` et `Icon=` dans le fichier `.desktop` avant de le copier.

### 🤝 Contribuer

```bash
git checkout -b feature/ma-fonctionnalite
git commit -m "feat: description"
git push origin feature/ma-fonctionnalite
```
Ouvrez ensuite une Pull Request.

---

## 🇬🇧 English

### Description

**Station Master** is a full-featured ham radio logbook written in Python (Tkinter / ttkbootstrap) with an SQLite database. It handles the QSO log, QSL confirmations, awards, propagation and station hardware (FlexRadio, SPE Expert amplifier). FT8 QSOs are received automatically from **Decodium** (or WSJT-X) over UDP.

Developed and used daily on Linux (Kubuntu); the code also supports Windows. The user interface is in French.

### 🗂️ Tabs

Dashboard · Flex-6500 · SPE · Propagation · Logbook Analysis · Journal (log) · Carte Live (live map) · QSL Email · QSL Card · Grayline · Satellites · DX Live · PSK Reporter · DX World / DXCC · Graphiques (charts) · Heatmap · Contests · Wiki

### 📋 Requirements

- **Python 3.10 or newer**
- `tkinter`: bundled with Python on Windows; on Debian/Ubuntu install `python3-tk`
- Python libraries: see [`requirements.txt`](requirements.txt)

### 📥 Installation — Linux

```bash
sudo apt install python3-tk python3-venv git
git clone https://github.com/albertM-hub/StationMaster.git
cd StationMaster
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 📥 Installation — Windows

Install Python 3.10+ from [python.org](https://www.python.org/downloads/), then:

```bat
git clone https://github.com/albertM-hub/StationMaster.git
cd StationMaster
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 🚀 Usage

```bash
python3 station_master.py      # Linux
py station_master.py           # Windows
```

It can be started from any directory: `config.ini`, the `station_master.db` database, `cty.dat` and the greyline map are created next to `station_master.py` on first launch. Then open **⚙️ Paramètres** to enter your callsign, locator, CAT port and service credentials. `config.ini` holds your passwords: never publish it (it is git-ignored).

> **QSL card**: personal card template (FlexRadio 6500, Ultrabeam, 100W, UBA member, CQ/ITU/Region 1), to be adapted in `tab_qsl.py`.

### 📡 FT8 QSOs (Decodium or WSJT-X)

Settings → Reporting → UDP Server `224.0.0.1`, port `2237`, ✅ Accept UDP requests, and ✅ N1MM Logger+ Broadcasts to `127.0.0.1`, port `2333` (the most reliable path on Linux). A QSO received on both ports is stored once.

### 📦 Linux executable

The archive on the [Releases](https://github.com/albertM-hub/StationMaster/releases) page (v1.0.0, June 2026) predates this version. Install from source, or build it with `pyinstaller station_master_linux.spec --clean`.

### 🤝 Contributing

Fork, branch, commit, push, open a Pull Request.

---

## 📁 Fichiers principaux / Main files

| Fichier | Description |
|---------|-------------|
| `station_master.py` | Point d'entrée et fenêtre principale |
| `tab_*.py`, `contest_tab.py` | Onglets externes (QSL, DXCC, DX Live, Satellites, Logbook Analysis, Contests, Wiki…) |
| `satellites_*.py` | Calcul et carte des passages satellites |
| `flex_client.py` | Client FlexRadio |
| `spe_expert.py` | Pilotage de l'ampli SPE Expert |
| `requirements.txt` | Dépendances Python |
| `config.ini.example` | Modèle de configuration (sans données sensibles) |
| `station_master_linux.spec` | Configuration PyInstaller (Linux) |
| `station_master.desktop` | Entrée de menu Kubuntu |

---

## 📜 License

MIT License — free to use, modify and distribute.
**73 de ON5AM** 🎙️
