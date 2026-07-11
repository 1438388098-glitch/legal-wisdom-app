#!/usr/bin/env python3
"""法律智库 - 个人法条库入口

启动方式:
  源码:   C:\\Users\\20579\\AppData\\Local\\Programs\\Python\\Python313\\python.exe main.py
  或双击: run.bat
  EXE:    dist\\法律智库\\法律智库.exe
"""
import sys
import os

# 最低 Python 版本要求
if sys.version_info < (3, 10):
    sys.exit("需要 Python 3.10+，当前: " + sys.version)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
