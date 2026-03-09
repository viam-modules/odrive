#!/bin/sh
cd `dirname $0`

# Create a virtual environment to run our code
VENV_NAME="venv"
PYTHON="$VENV_NAME/bin/python"

if ! $PYTHON -m pip install -r requirements.txt -qq; then
    exit 1
fi

if ! $PYTHON -m pip install pyinstaller setuptools -Uqq; then
    exit 1
fi

$PYTHON -m PyInstaller --onefile \
    --hidden-import="googleapiclient" \
    --runtime-hook="runtime_hooks/hook_pkg_resources.py" \
    --collect-all="viam" \
    --collect-all="odrive" \
    src/main.py
tar -czvf dist/archive.tar.gz meta.json ./dist/main
