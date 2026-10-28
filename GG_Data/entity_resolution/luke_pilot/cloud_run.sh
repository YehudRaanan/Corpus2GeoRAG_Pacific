#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/luke-pilot"
mkdir -p outputs
date --iso-8601=seconds > outputs/environment_start.txt
nvidia-smi > outputs/nvidia-smi.txt
python3 -m venv --system-site-packages "$HOME/luke-pilot-venv"
PY="$HOME/luke-pilot-venv/bin/python"
"$PY" -m pip install --disable-pip-version-check 'transformers==5.6.2' 'pytest==9.0.2'
"$PY" -m pip freeze > outputs/pip-freeze.txt
"$PY" -m pytest code/test_pilot.py -q
export TOKENIZERS_PARALLELISM=false
export HF_HOME="$HOME/luke-pilot/hf-cache"
export PYTHONUNBUFFERED=1
"$PY" code/train.py train --inputs inputs --output outputs --max-hours 7
date --iso-8601=seconds > outputs/train_finished.txt
