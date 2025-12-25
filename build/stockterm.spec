# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

project_root = Path(__file__).resolve().parent.parent


a = Analysis(
    ['../main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(project_root / 'app' / 'ui' / 'styles.css'), 'app/ui')],
    hiddenimports=[
        'aiosqlite',
        'plyer.platforms.win.notification',
        'textual.drivers.windows_driver',
        'zoneinfo',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    name='StockTerm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
