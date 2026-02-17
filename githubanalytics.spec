# githubanalyticsProject.spec
# Build:
#   pyinstaller --noconfirm githubanalyticsProject.spec
#
# Notes:
# - Entry point is gui.py (windowed app).
# - Includes blocks.py, main.py, pipeline.py automatically (imported by gui/main/blocks).
# - Collects PyQt5 hidden imports to reduce “missing module” surprises.

from PyInstaller.utils.hooks import collect_submodules

hidden = []
hidden += collect_submodules("PyQt5")

a = Analysis(
    ["gui.py"],              # ✅ entrypoint
    pathex=["."],            # project root
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="NatesGitHubAnalyticsProject",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # ✅ windowed GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
