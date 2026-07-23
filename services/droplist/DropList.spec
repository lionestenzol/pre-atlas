# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('ui', 'ui')]
binaries = []
hiddenimports = []
# Bundle the runtime packages whose data files / lazily-imported submodules
# PyInstaller's static analysis misses. litellm ships model-pricing JSON + provider
# modules loaded by string; without collect_all, /api/ai/* crashes in the frozen
# exe even though the window opens. See ~/.claude/rules/common/code-as-furniture.md.
for _pkg in ('webview', 'litellm', 'fastapi', 'uvicorn'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d; binaries += _b; hiddenimports += _h


a = Analysis(
    ['droplist\\desktop.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'transformers', 'tensorflow', 'sentence_transformers', 'onnxruntime', 'sympy', 'scipy', 'pandas', 'matplotlib', 'IPython', 'notebook'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DropList',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ui\\icons\\DropList.ico'],
)
