# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect package data and dependencies
datas = []
binaries = []
hiddenimports = [
    'customtkinter',
    'PIL',
    'PIL._tkinter_finder',
    'msal',
    'cryptography',
    'fitz',
    'rapidocr_onnxruntime',
    'onnxruntime',
    'cv2',
    'numpy',
    'resend'
]

# Collect all assets for packages that need runtime data/models
for pkg in ['customtkinter', 'rapidocr_onnxruntime', 'onnxruntime']:
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hidden)

a = Analysis(
    ['app/main.py'],
    pathex=['app', '.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HRPayslipAutomator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI application, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='HRPayslipAutomator',
)
