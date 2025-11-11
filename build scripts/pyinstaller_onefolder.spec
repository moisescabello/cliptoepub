# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Root path so dynamic imports (content_processor) are found
project_root = os.path.abspath('.')

a = Analysis(
    ['src/tray_app_windows.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        ('templates/*', 'templates'),
        ('resources/*', 'resources'),
    ],
    hiddenimports=[
        'content_processor',
        'bs4',
        'newspaper',
        'lxml_html_clean',
        'PIL._imaging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas', 'pytest', 'ipython'
    ],
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
    name='ClipToEpub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # avoid packers that may trigger AV heuristics
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='ClipToEpub'
)
