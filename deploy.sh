#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890
export all_proxy=socks5://127.0.0.1:7891

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

. ".venv/bin/activate"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

python3 build.py "$@" --deploy
