# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统 - EXE打包脚本
使用 PyInstaller 打包成独立可执行文件

使用方法:
    python build_exe.py

建议:
    使用 Python 3.8 打包以确保最大兼容性

依赖:
    pip install pyinstaller

输出:
    dist/WorkloadManagement.exe
"""

import os
import sys
import shutil
import subprocess

# 推荐的 Python 版本
RECOMMENDED_PYTHON = (3, 8)

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 打包配置
APP_NAME = "WorkloadManagement"
MAIN_SCRIPT = "run_standalone.py"
ICON_FILE = None  # 如果有图标，设置为图标路径

# 需要包含的数据文件
DATA_FILES = [
    ('app/templates', 'app/templates'),
    ('app/static', 'app/static'),
    ('static', 'static'),
]

# 隐式导入的模块
HIDDEN_IMPORTS = [
    'flask',
    'flask_sqlalchemy',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.pool',
    'sqlalchemy.orm',
    'sqlalchemy.ext.declarative',
    'werkzeug',
    'werkzeug.security',
    'werkzeug.routing',
    'werkzeug.serving',
    'werkzeug.middleware',
    'jinja2',
    'jinja2.ext',
    'markupsafe',
    'pandas',
    'openpyxl',
    'openpyxl.cell',
    'openpyxl.styles',
    'openpyxl.utils',
    'waitress',
    'sqlite3',
    'csv',
    'datetime',
    'decimal',
    'hashlib',
    'hmac',
    'json',
    'logging',
    're',
    'typing',
    'uuid',
    'warnings',
    'weakref',
]

def clean_build():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for d in dirs_to_clean:
        path = os.path.join(BASE_DIR, d)
        if os.path.exists(path):
            print(f"[清理] 删除 {path}")
            shutil.rmtree(path)

    # 删除旧的 spec 文件
    spec_file = os.path.join(BASE_DIR, f'{APP_NAME}.spec')
    if os.path.exists(spec_file):
        os.remove(spec_file)

def create_spec_file():
    """创建 PyInstaller spec 文件"""

    # 构建数据文件参数
    datas = []
    for src, dst in DATA_FILES:
        src_path = os.path.join(BASE_DIR, src)
        if os.path.exists(src_path):
            datas.append(f"('{src}', '{dst}')")

    datas_str = ',\n        '.join(datas)

    # 构建隐式导入参数
    hidden_imports_str = ',\n        '.join([f"'{m}'" for m in HIDDEN_IMPORTS])

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec 文件 - {APP_NAME}
# 由 build_exe.py 自动生成

block_cipher = None

a = Analysis(
    '{MAIN_SCRIPT}',
    pathex=['{BASE_DIR.replace(chr(92), '/')}'],
    binaries=[],
    datas=[
        {datas_str}
    ],
    hiddenimports=[
        {hidden_imports_str}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy.f2py',
        'IPython',
        'notebook',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 显示控制台窗口（方便查看日志）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {f'icon="{ICON_FILE}",' if ICON_FILE else ''}
)
'''

    spec_file = os.path.join(BASE_DIR, f'{APP_NAME}.spec')
    # newline='' prevents Windows from converting \n to \r\n
    with open(spec_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(spec_content)

    print(f"[创建] 生成 spec 文件: {spec_file}")
    return spec_file

def build_exe():
    """执行打包"""
    # Use command line arguments instead of spec file to avoid encoding issues
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        '--onefile',
        '--console',
        '--name', APP_NAME,
        MAIN_SCRIPT
    ]

    # Add data files
    for src, dst in DATA_FILES:
        src_path = os.path.join(BASE_DIR, src)
        if os.path.exists(src_path):
            cmd.extend(['--add-data', f'{src}{os.pathsep}{dst}'])

    # Add hidden imports
    for module in HIDDEN_IMPORTS:
        cmd.extend(['--hidden-import', module])

    # Add excludes
    for module in ['tkinter', 'matplotlib', 'numpy.f2py', 'IPython', 'notebook', 'pytest']:
        cmd.extend(['--exclude-module', module])

    print(f"[打包] 执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode == 0:
        exe_path = os.path.join(BASE_DIR, 'dist', f'{APP_NAME}.exe')
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\n{'='*60}")
            print(f"[成功] 打包完成!")
            print(f"[输出] {exe_path}")
            print(f"[大小] {size_mb:.2f} MB")
            print(f"{'='*60}")
        else:
            print("[警告] exe 文件未找到")
    else:
        print(f"[错误] 打包失败，返回码: {result.returncode}")

    return result.returncode

def copy_database():
    """复制数据库文件到 dist 目录"""
    db_file = os.path.join(BASE_DIR, 'workload.db')
    dist_dir = os.path.join(BASE_DIR, 'dist')

    if os.path.exists(db_file) and os.path.exists(dist_dir):
        shutil.copy2(db_file, dist_dir)
        print(f"[复制] 数据库文件已复制到 dist 目录")

def create_readme():
    """创建发布说明"""
    readme_content = '''# 康复科治疗师工作量管理系统

## 运行说明

1. 双击 `WorkloadManagement.exe` 启动系统
2. 打开浏览器访问: http://localhost:5001
3. 按 Ctrl+C 停止服务

## 文件说明

- `WorkloadManagement.exe` - 主程序
- `workload.db` - 数据库文件（首次运行会自动创建）
- `README.txt` - 本说明文件

## 系统要求

- Windows 7 及以上
- 无需安装 Python

## 注意事项

1. 首次运行会自动创建数据库和默认数据
2. 数据保存在 `workload.db` 文件中
3. 请勿删除 `workload.db` 文件，否则数据将丢失
4. 如需备份数据，请复制 `workload.db` 文件

## 默认端口

系统默认使用 5001 端口，如需修改请编辑配置文件。

## 技术支持

如有问题请联系系统管理员。

---
版本: V7.3.0
构建时间: 2026-02-27
'''

    readme_path = os.path.join(BASE_DIR, 'dist', 'README.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"[创建] 发布说明: {readme_path}")

def check_python_version():
    """检查 Python 版本"""
    current_version = sys.version_info[:2]
    print(f"[检查] 当前 Python 版本: {current_version[0]}.{current_version[1]}")

    if current_version == RECOMMENDED_PYTHON:
        print(f"[成功] Python 版本符合推荐要求 (3.8)")
        return True
    elif current_version >= (3, 7) and current_version < (3, 12):
        print(f"[警告] 当前 Python {current_version[0]}.{current_version[1]} 不是推荐的 3.8")
        print(f"[警告] 建议使用 Python 3.8 打包以确保最大兼容性")
        print(f"[警告] 继续打包可能会在某些系统上出现兼容性问题")
        return True
    else:
        print(f"[错误] Python 版本不兼容")
        print(f"[错误] 请使用 Python 3.7 - 3.11")
        return False

def main():
    print("=" * 60)
    print("康复科治疗师工作量管理系统 - 打包工具")
    print("=" * 60)
    print()

    # 检查 Python 版本
    if not check_python_version():
        return 1

    print()

    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"[检查] PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("[错误] 请先安装 PyInstaller:")
        print("       pip install pyinstaller")
        return 1

    # 清理旧文件
    clean_build()

    # 执行打包
    result = build_exe()

    if result == 0:
        # 复制数据库
        copy_database()

        # 创建说明文件
        create_readme()

        print("\n[完成] 打包成功！发布包位于 dist 目录")

    return result

if __name__ == '__main__':
    sys.exit(main())
