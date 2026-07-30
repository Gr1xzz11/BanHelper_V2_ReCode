# -*- mode: python ; coding: utf-8 -*-
import os

project_root = os.path.abspath(os.path.join(SPECPATH, ".."))
output_name = os.environ.get("BANHELPER_OUTPUT_NAME", "BanHelper")
fabric_jar = os.path.join(project_root, "release", "banhelper-bridge-2.0.0.jar")
datas = [
    (os.path.join(project_root, "assets", "banhelper.ico"), "assets"),
    (os.path.join(project_root, "assets", "banhelper.svg"), "assets"),
    (os.path.join(project_root, "assets", "banhelper.png"), "assets"),
    (fabric_jar, "fabric"),
]

a = Analysis(
    [os.path.join(project_root, "run.py")], pathex=[project_root], binaries=[], datas=datas,
    hiddenimports=["PySide6.QtSvg", "PySide6.QtNetwork"],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name=output_name,
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None, codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, "assets", "banhelper.ico") if os.name == "nt"
    else os.path.join(project_root, "assets", "banhelper.png"),
)
