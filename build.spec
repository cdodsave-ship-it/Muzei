# build.spec
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

panda3d_datas = collect_data_files('panda3d')
panda3d_libs  = collect_dynamic_libs('panda3d')

a = Analysis(
    ['main.py'],          # <-- имя вашего .py файла
    pathex=['.'],
    binaries=panda3d_libs,
    datas=panda3d_datas,
    hiddenimports=[
        'panda3d.core',
        'direct.showbase.ShowBase',
        'direct.task',
        'direct.directnotify',
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
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
    [],
    exclude_binaries=True,
    name='MuseumViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='museum.ico',    # <-- ваша иконка
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MuseumViewer',
)