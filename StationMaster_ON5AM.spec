# -*- mode: python ; coding: utf-8 -*-
# ============================================================
#  Station Master V21.0 — ON5AM
#  Fichier .spec PyInstaller
#  UTILISATION : python -m PyInstaller StationMaster_ON5AM.spec
#
#  Changements v21.0 :
#  - Thème darkly (remplace superhero)
#  - Listener UDP configurable (port WSJT-X / GridTracker)
#  - Anti-doublon QSO 3 minutes
#  - Splash screen corrigé
#  - Greyline map corrigée
# ============================================================

block_cipher = None

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ttkbootstrap_datas  = collect_data_files('ttkbootstrap')
ttkbootstrap_hidden = collect_submodules('ttkbootstrap')

tkmap_datas  = collect_data_files('tkintermapview')
tkmap_hidden = collect_submodules('tkintermapview')

pillow_hidden = collect_submodules('PIL')

reportlab_datas  = collect_data_files('reportlab')
reportlab_hidden = collect_submodules('reportlab')

mpl_datas  = collect_data_files('matplotlib')
mpl_hidden = collect_submodules('matplotlib')

try:
    certifi_datas = collect_data_files('certifi')
except Exception:
    certifi_datas = []

# Collecter aussi les thèmes ttkbootstrap (darkly inclus)
try:
    ttk_themes = collect_data_files('ttkbootstrap', includes=['*.json', '*.tcl', '*.gif', '*.png'])
except Exception:
    ttk_themes = []

all_datas = (
    ttkbootstrap_datas
    + ttk_themes
    + tkmap_datas
    + reportlab_datas
    + mpl_datas
    + certifi_datas
)

all_hidden = (
    ttkbootstrap_hidden
    + tkmap_hidden
    + pillow_hidden
    + reportlab_hidden
    + mpl_hidden
    + [
        # tkinter
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.colorchooser',
        'tkinter.simpledialog',
        '_tkinter',
        # réseau
        'requests',
        'requests.adapters',
        'requests.auth',
        'urllib3',
        'urllib3.util',
        'charset_normalizer',
        'certifi',
        'socket',
        'struct',
        # XML / config
        'xml.etree.ElementTree',
        'configparser',
        # base de données
        'sqlite3',
        '_sqlite3',
        # port série
        'serial',
        'serial.tools.list_ports',
        'serial.tools.list_ports_windows',
        # numpy / matplotlib
        'numpy',
        'numpy.core._methods',
        'numpy.lib.format',
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends._backend_tk',
        'matplotlib.figure',
        'matplotlib.patches',
        'matplotlib.colors',
        'matplotlib.cm',
        # PIL
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        # reportlab
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.platypus',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        'reportlab.lib.enums',
        # notifications Windows
        'win10toast',
        # pyparsing (requis par matplotlib)
        'pyparsing',
        'pyparsing.testing',
        'pyparsing.core',
        'pyparsing.helpers',
        'pyparsing.actions',
        'pyparsing.results',
        'pyparsing.exceptions',
        'unittest',
        'unittest.mock',
        'unittest.case',
        'unittest.suite',
        'unittest.loader',
        'unittest.runner',
        'unittest.result',
        'unittest.signals',
        'unittest.util',
        'doctest',
        'difflib',
        'inspect',
        'linecache',
        'tokenize',
        'token',
        # stdlib
        'threading',
        'io',
        'shutil',
        'time',
        'math',
        'traceback',
        're',
        'os',
        'sys',
        'datetime',
        'webbrowser',
        'json',
        'hashlib',
        'base64',
        'copy',
        'collections',
        'functools',
        'itertools',
        'pathlib',
        'zipfile',
        'csv',
        'locale',
        'platform',
    ]
)

a = Analysis(
    ['mon_logbook.py'],
    pathex=['.'],
    binaries=[],
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Grosses librairies tierces non utilisées
        'scipy', 'pandas', 'IPython', 'jupyter', 'notebook',
        'cv2', 'wx', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'tkinter.tix',
        # Ne PAS exclure les modules stdlib (unittest, difflib, etc.)
        # car matplotlib/pyparsing en ont besoin indirectement
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='StationMaster_ON5AM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # Passer à True pour voir les erreurs au démarrage
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='radio.ico',
)

# ============================================================
#  CHECKLIST AVANT BUILD
#  1. Les deux fichiers dans le même dossier :
#       mon_logbook.py
#       radio.ico
#       StationMaster_ON5AM.spec
#
#  2. Commande de build :
#       python -m PyInstaller StationMaster_ON5AM.spec --clean
#
#  3. Le .exe final se trouve dans :
#       dist\StationMaster_ON5AM.exe
#
#  4. Fichiers créés automatiquement à côté du .exe :
#       config.ini      (paramètres station)
#       mon_logbook.db  (base de données QSOs)
#
#  5. Si le .exe ne démarre pas :
#       Passer console=False → console=True
#       Relancer le build et regarder les erreurs
#       Puis repasser à console=False
#
#  6. En cas d'erreur "module not found" :
#       Ajouter le module manquant dans all_hidden ci-dessus
# ============================================================
