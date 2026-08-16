# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, collect_submodules

datas = [
    ("config/stt.yaml", "config"),
    ("data/hanzi_writer/medians-2.0.1.json.gz", "data/hanzi_writer"),
    ("data/hanzi_writer/README.md", "data/hanzi_writer"),
    ("data/hanzi_writer/ARPHICPL.TXT", "data/hanzi_writer"),
    ("src/gui/styles/style.qss", "src/gui/styles"),
    ("assets/ui/cyber-xuan-paper-concept.png", "assets/ui"),
]
datas += collect_data_files("silero_vad", includes=["data/*.jit", "data/*.onnx", "data/*.safetensors"])
hiddenimports = collect_submodules("faster_whisper") + collect_submodules("silero_vad")
binaries = collect_dynamic_libs("ctranslate2")
for package in ("silero_vad", "zhconv"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    ["src/gui/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "notebook"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="声写机器人",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="声写机器人",
)
