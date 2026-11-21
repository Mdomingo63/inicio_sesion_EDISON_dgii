# -*- mode: python ; coding: utf-8 -*-
# Especificación de PyInstaller para generar el ejecutable de LoginDGII.
# Compila con:  .venv/Scripts/python.exe -m PyInstaller LoginDGII.spec --noconfirm
#
# Incluye el driver de Playwright (Node.exe) y el navegador Chromium completo,
# de modo que el .exe funcione en PCs sin Python ni navegadores instalados.

import os
import playwright

DRIVER_DIR = os.path.join(os.path.dirname(playwright.__file__), "driver")

a = Analysis(
    ["app_oficina_virtual.py"],
    pathex=[],
    binaries=[],
    datas=[(DRIVER_DIR, os.path.join("playwright", "driver")), ("recursos", "recursos")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="LoginDGII",
    debug=False,
    strip=False,
    upx=False,
    console=False,  # Aplicación con ventana; sin consola negra
    icon="recursos/app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LoginDGII",
)
