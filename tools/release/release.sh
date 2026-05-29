#!/usr/bin/env bash
# Cython 发布脚本: 将 src/qsim 编译成 .so 并打包安装。
# 与 uv/pyproject.toml 不冲突 —— pyproject.toml 是源码安装路径,
# 这个脚本是给生产环境的 Cython 编译路径。
#
# 用法:
#   OUTPUT=./build bash tools/release/release.sh
set -e

basepath=$(cd "$(dirname "$0")" && pwd)
cd "$basepath"

OUTPUT=${OUTPUT:-./build}

BIN=${CONDA_PREFIX:-/usr}/bin
PIP=${BIN}/pip
PYTHON=${BIN}/python

${PYTHON} ./build_cython.py "${OUTPUT}" append

cd "${OUTPUT}" && "${PIP}" install . && cd -
