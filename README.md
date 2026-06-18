# 🎙️ Station Master

**Logbook radio amateur & gestion de station — par ON5AM (Albert)**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux-lightgrey.svg)](https://github.com/albertM-hub/StationMaster)

![Station Master](logo/station_masters.png)

---

## 🇫🇷 Français

### Description

**Station Master** est un logbook radio amateur complet développé en Python (Tkinter / ttkbootstrap), conçu pour les radioamateurs qui veulent gérer leur station depuis une interface moderne et intuitive, sous Linux.

### ✨ Fonctionnalités principales

- 📖 **Journal de trafic** — Enregistrement automatique (FT8/WSJT-X) ou manuel des QSOs
- 🔗 **Intégration WSJT-X / Decodium** — Réception UDP des QSOs (port configurable)
- 🌍 **Carte Live & Greyline** — Visualisation des QSOs sur carte interactive animée
- 📡 **DX Cluster** — Spots en temps réel avec filtres par bande/mode/pays
- 🏆 **DXCC & Awards** — Suivi de progression DXCC, WAZ, WAS
- 🌐 **Propagation** — Indices SFI, K, A en temps réel
- 📬 **QSL Manager** — Suivi eQSL, LoTW, ClubLog + envoi par e-mail
- 🖨️ **Cartes QSL** — Génération de cartes QSL personnalisées
- 🏁 **Contest** — Onglet dédié aux contests
- 🎛️ **SPE Expert** — Pilotage de l'ampli SPE Expert via port série
- 💾 **Backup automatique** — Sauvegarde à chaque fermeture

### 📋 Prérequis

- Python 3.9 ou supérieur
- `tkinter` (inclus avec Python sur la plupart des distributions ; sous Debian/Ubuntu : `sudo apt install python3-tk`)

### 📥 Installation depuis les sources

```bash
git clone https://github.com/albertM-hub/StationMaster.git
cd StationMaster
pip install -r requirements.txt
```

### 📦 Installation via l'exécutable Linux

👉 **[Télécharger la dernière version](https://github.com/albertM-hub/StationMaster/releases/latest)**

Décompressez l'archive et lancez le binaire `station_master`. `config.ini` et la base de données seront créés automatiquement au premier lancement.

### ⚙️ Configuration

1. Copiez le fichier d'exemple :
   ```bash
   cp config.ini.example config.ini
   ```
2. Éditez `config.ini` avec votre indicatif, vos identifiants QRZ/eQSL/LoTW/ClubLog et vos ports (CAT, SPE Expert).

### ⚙️ Configuration WSJT-X / Decodium

Dans WSJT-X (ou Decodium) → **File → Settings → Reporting** :
```
UDP Server    : 224.0.0.1
Port          : 2237
✅ Accept UDP requests
```

### 🚀 Usage

```bash
python3 station_master.py
```

Au premier démarrage, Station Master télécharge automatiquement `cty.dat` (base DXCC) et la carte greyline NASA.

### 🔨 Compiler l'exécutable Linux soi-même

```bash
pip install pyinstaller
pyinstaller station_master_linux.spec --clean
```
Le binaire sera dans `dist/station_master/station_master`.

### 🖥️ Installer dans le menu d'applications (Kubuntu)

```bash
mkdir -p ~/Applications
cp -r dist/station_master ~/Applications/
chmod +x ~/Applications/station_master/station_master
cp station_master.desktop ~/.local/share/applications/
```

> Si votre dossier personnel n'est pas `/home/albert`, éditez les chemins `Exec=` et `Icon=` dans le fichier `.desktop` avant de le copier.

### 🤝 Contributing

```bash
git checkout -b feature/ma-fonctionnalite
git commit -m "feat: description"
git push origin feature/ma-fonctionnalite
```
Ouvrez ensuite une Pull Request.

---

## 🇬🇧 English

### Description

**Station Master** is a full-featured ham radio logbook built in Python (Tkinter / ttkbootstrap), designed for amateur radio operators who want to manage their station from a modern, intuitive interface on Linux.

### ✨ Key Features

- 📖 **QSO Log** — Automatic (FT8/WSJT-X) or manual QSO recording
- 🔗 **WSJT-X / Decodium Integration** — UDP QSO reception (configurable port)
- 🌍 **Live Map & Greyline** — Animated interactive QSO map
- 📡 **DX Cluster** — Real-time spots with band/mode/country filters
- 🏆 **DXCC & Awards** — DXCC, WAZ, WAS progress tracking
- 🌐 **Propagation** — Real-time SFI, K, A indices
- 📬 **QSL Manager** — eQSL, LoTW, ClubLog tracking + email sending
- 🖨️ **QSL Cards** — Custom QSL card generator
- 🏁 **Contest** — Dedicated contest tab
- 🎛️ **SPE Expert** — SPE Expert amplifier control via serial port
- 💾 **Auto Backup** — Saved on every close

### 📋 Requirements

- Python 3.9+
- `tkinter` (bundled with Python on most distros; on Debian/Ubuntu: `sudo apt install python3-tk`)

### 📥 Installation from source

```bash
git clone https://github.com/albertM-hub/StationMaster.git
cd StationMaster
pip install -r requirements.txt
```

### 📦 Installation via the Linux executable

👉 **[Download latest release](https://github.com/albertM-hub/StationMaster/releases/latest)**

Unpack the archive and run the `station_master` binary. `config.ini` and the database will be created automatically on first launch.

### ⚙️ Configuration

```bash
cp config.ini.example config.ini
```
Then edit `config.ini` with your callsign, QRZ/eQSL/LoTW/ClubLog credentials, and ports (CAT, SPE Expert).

### 🚀 Usage

```bash
python3 station_master.py
```

### 🔨 Build the Linux executable yourself

```bash
pip install pyinstaller
pyinstaller station_master_linux.spec --clean
```
The binary will be in `dist/station_master/station_master`.

### 🤝 Contributing

Fork, branch, commit, push, open a Pull Request.

---

## 📁 Fichiers principaux / Main files

| Fichier | Description |
|---------|-------------|
| `station_master.py` | Point d'entrée principal |
| `tab_*.py` | Onglets de l'interface (QSL, DXCC, FT8, météo, wiki, contest...) |
| `flex_client.py` | Client FlexRadio |
| `spe_expert.py` | Pilotage ampli SPE Expert |
| `config.ini.example` | Modèle de configuration |
| `station_master_linux.spec` | Configuration PyInstaller (Linux) |
| `station_master.desktop` | Entrée menu Kubuntu |

---

## 📜 License

MIT License — free to use, modify and distribute.
**73 de ON5AM** 🎙️
