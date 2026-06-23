#!/bin/bash
# 安装 ESP-IDF v5.5 所需的 Python 包
/c/Users/24628/.espressif/python_env/idf5.5_py3.11_env/Scripts/python -m pip install "esptool>=4.12.dev1,<5.0" tree-sitter tree-sitter-c -q
echo "Done: $?"
