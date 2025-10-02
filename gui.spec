# -*- mode: python ; coding: utf-8 -*-

import os
import glob
import ortools

ortools_path = ortools.__path__[0]
libs_dir = os.path.join(ortools_path, '.libs')
dll_files = glob.glob(os.path.join(libs_dir, '*.dll'))

binaries_list = [(dll, 'ortools/.libs') for dll in dll_files]


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=binaries_list,
    datas=[('shapes.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='gui',
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
)


# COLLECT 用于创建多文件（文件夹）模式的打包。
# 它将可执行文件、二进制文件和数据文件收集到一个名为 'gui' 的文件夹中。
# 为了切换到单文件可执行模式，此部分被注释掉。
# 如果要实现多文件打包，以方便直接修改 shapes.json 文件设置，可将以下代码的注释取消。
# 之后可直接修改 internal/shapes.json 以适配其他情况的求解。
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='gui',
# )
