# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Station Master — Linux x86_64

a = Analysis(
    ['station_master.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('logo/station_masters.png', 'logo'),
    ],
    hiddenimports=[
        'ttkbootstrap', 'ttkbootstrap.constants', 'ttkbootstrap.themes',
        'ttkbootstrap.style', 'ttkbootstrap.widgets',
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw', 'PIL.ImageFont',
        'PIL.ImageGrab', 'PIL._tkinter_finder',
        'serial', 'serial.tools', 'serial.tools.list_ports',
        'requests', 'requests.adapters', 'urllib3',
        'xml.etree.ElementTree',
        'sqlite3', 'configparser',
        'smtplib', 'ssl', 'email', 'email.mime.multipart',
        'email.mime.text', 'email.mime.application',
        'tkintermapview',
        'flex_client', 'spe_expert', 'contest_tab',
        'tab_dxcc', 'tab_dxpeditions', 'tab_dx_unified', 'tab_ft8_monitor',
        'tab_grayline', 'tab_qsl', 'tab_qsl_email', 'tab_spe_expert',
        'tab_weather', 'tab_wiki',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'doctest', 'pdb', 'profile',
        'tkinter.test', 'winsound', 'win10toast',
        'matplotlib', 'numpy', 'reportlab',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='station_master',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='logo/station_masters.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='station_master',
)
