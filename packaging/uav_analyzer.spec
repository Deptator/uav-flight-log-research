
# -*- mode: python ; coding: utf-8 -*-
"""Development build specification for the UAV Flight Analysis System."""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
)

project_root = Path.cwd().resolve()

dashboard_path = project_root / "dashboard"
src_path = project_root / "src"
outputs_path = project_root / "outputs"

datas = [
    (str(dashboard_path), "dashboard"),
    (str(outputs_path), "outputs"),
]

hiddenimports = collect_submodules("src")
hiddenimports += collect_submodules("components")

# Streamlit uses dynamically loaded modules and static frontend resources.
streamlit_datas, streamlit_binaries, streamlit_hidden = collect_all("streamlit")
datas += streamlit_datas
hiddenimports += streamlit_hidden

# Include the RFC 3987 grammar required by jsonschema/Altair.
rfc_datas, rfc_binaries, rfc_hidden = collect_all("rfc3987_syntax")
datas += rfc_datas
hiddenimports += rfc_hidden

a = Analysis(
    [str(project_root / "packaging" / "launcher.py")],
    pathex=[
        str(project_root),
        str(dashboard_path),
    ],
    binaries=streamlit_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="UAV-Flight-Analyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="UAV-Flight-Analyzer",
)
