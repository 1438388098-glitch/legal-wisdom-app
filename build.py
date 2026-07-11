#!/usr/bin/env python3
"""PyInstaller 打包脚本 - 生成 法律智库.exe"""
import os
import sys
import subprocess
import shutil

# 解决 Windows 终端编码问题
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

APP_NAME = "法律智库"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
SPEC_FILE = os.path.join(PROJECT_DIR, f"{APP_NAME}.spec")
DB_PATH = os.path.join(PROJECT_DIR, "data", "database", "legal.db")

# 确保数据库已初始化
if not os.path.exists(DB_PATH):
    print("[!] 数据库不存在，正在导入数据...")
    from data.database.import_data import import_all
    result = import_all()
    print(f"导入完成: {result['imported']}/{result['total']} 条")


def build():
    # 清理旧构建
    for d in [DIST_DIR, BUILD_DIR, SPEC_FILE]:
        path = d if isinstance(d, str) else d
        if os.path.exists(path):
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)

    icon_path = os.path.join(PROJECT_DIR, "assets", "icon.ico")
    icon_arg = f'--icon={icon_path}' if os.path.exists(icon_path) else ""

    # Note: Noto Serif SC and Inter fonts are not bundled with the EXE.
    # To include them, download from Google Fonts and add:
    # --add-data "path/to/NotoSerifSC-Regular.otf;assets/fonts"

    pyinstaller_exe = r"C:\Users\20579\AppData\Local\Programs\Python\Python313\Scripts\pyinstaller.exe"
    if not os.path.exists(pyinstaller_exe):
        pyinstaller_exe = "pyinstaller"

    cmd = [
        pyinstaller_exe,
        "--noconfirm",
        "--windowed",
        f"--name={APP_NAME}",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        "--add-data", f"{os.path.join(PROJECT_DIR, 'assets')}{os.pathsep}assets",
        "--add-data", f"{DB_PATH}{os.pathsep}data/database",
        "--hidden-import=pdfminer",
        "--hidden-import=pdfminer.high_level",
        "--hidden-import=pdfminer.layout",
        "--hidden-import=docx",
        "--hidden-import=PySide6.QtXml",
        os.path.join(PROJECT_DIR, "main.py"),
    ]

    if icon_arg:
        cmd.append(icon_arg)

    print(f"[*] 正在打包 '{APP_NAME}' ...")
    print(f"[*] 命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)

    if result.stdout:
        for line in result.stdout.splitlines():
            if "INFO" not in line and "WARNING" not in line:
                print(f"  {line}")
    if result.stderr:
        for line in result.stderr.splitlines():
            if "Traceback" in line or "Error" in line or "error" in line:
                print(f"  [ERR] {line}")

    if result.returncode != 0:
        print(f"\n[-] 打包失败 (exit code {result.returncode})")
        sys.exit(1)

    print("\n[+] 打包成功!")

    # === 修复 shiboken6 的 VC++ 运行时 DLL ===
    # shiboken6 自带的 vcruntime140.dll 版本过旧
    # Qt6 DLL 需要较新的版本否则报 [WinError 127] 找不到指定的程序
    exe_dir = os.path.join(DIST_DIR, APP_NAME)
    internal_dir = os.path.join(exe_dir, "_internal")
    pyside_dir = os.path.join(internal_dir, "PySide6")
    shiboken_dir = os.path.join(internal_dir, "shiboken6")
    for dll_name in ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll"]:
        src = os.path.join(pyside_dir, dll_name)
        dst = os.path.join(shiboken_dir, dll_name.upper())
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  修复 shiboken6/{dll_name.upper()} ({os.path.getsize(dst)} bytes)")

    exe_path = os.path.join(exe_dir, f"{APP_NAME}.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"  输出: {exe_path}")
        print(f"  大小: {size_mb:.1f} MB")


if __name__ == "__main__":
    build()
