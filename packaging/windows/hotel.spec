# PyInstaller recipe for the Windows executable (story 6.4).
#   pyinstaller --noconfirm packaging/windows/hotel.spec
# The result is dist/hotel.exe: Python, the dependencies and the application
# in one file. Templates, styles, translations and SQL migrations are data
# files, so they are listed explicitly.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("hotel") + collect_data_files("tzdata") + collect_data_files("babel")

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    pathex=[],
    datas=datas,
    # Imported lazily inside functions, so PyInstaller cannot see them by itself.
    hiddenimports=collect_submodules("hotel") + collect_submodules("waitress"),
    excludes=["tkinter", "pytest", "hypothesis"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="hotel",
    console=True,  # the window shows the address and stops the server when closed
    upx=False,  # compressed executables are flagged more often by antivirus software
)
