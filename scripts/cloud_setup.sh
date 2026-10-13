#!/usr/bin/env bash
set -euo pipefail
cd /workspace/legal
if [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi
export PIP_CACHE_DIR=/workspace/.cache/legal-pip
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip check
.venv/bin/python scripts/manage.py init
