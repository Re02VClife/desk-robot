#!/bin/bash
# ESP-IDF v5.5.3 编译脚本
# 用法: bash esp_idf_build.sh [idf.py 参数]

export IDF_PATH="/e/esp/Espressif/frameworks/esp-idf-v5.5.3"
export IDF_PYTHON_ENV_PATH="/c/Users/24628/.espressif/python_env/idf5.5_py3.11_env"
export ESP_IDF_VERSION="5.5.3"

# Python 虚拟环境
export PATH="/c/Users/24628/.espressif/python_env/idf5.5_py3.11_env/Scripts:$PATH"

# 构建工具
export PATH="/c/Users/24628/.espressif/tools/cmake/3.30.2/bin:$PATH"
export PATH="/c/Users/24628/.espressif/tools/ninja/1.12.1:$PATH"
export PATH="/c/Users/24628/.espressif/tools/idf-exe/1.0.3:$PATH"

# Xtensa 工具链 (ESP32-S3) + RISC-V (ULP) - 使用 E: 盘最新版匹配 ESP-IDF v5.5.3 要求
export PATH="/e/esp/Espressif/tools/xtensa-esp-elf/esp-14.2.0_20251107/xtensa-esp-elf/bin:$PATH"
export PATH="/e/esp/Espressif/tools/riscv32-esp-elf/esp-14.2.0_20251107/riscv32-esp-elf/bin:$PATH"

cd /c/Users/24628/Desktop/vscode/xiaozhiAI

python -u /e/esp/Espressif/frameworks/esp-idf-v5.5.3/tools/idf.py "$@"
