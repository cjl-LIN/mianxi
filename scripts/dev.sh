#!/usr/bin/env bash
# 一条命令启动面习的 API 和网页。
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -x apps/api/.venv/bin/python ]]; then
  python3 -m venv apps/api/.venv
fi
apps/api/.venv/bin/pip install -r apps/api/requirements.txt

if [[ ! -d apps/web/node_modules ]]; then
  (cd apps/web && npm install)
fi

cleanup() {
  jobs -p | xargs -r kill
}
trap cleanup EXIT INT TERM

apps/api/.venv/bin/uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8741 &
(cd apps/web && npm run dev) &
wait
