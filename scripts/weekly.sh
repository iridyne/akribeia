#!/usr/bin/env bash
# Weekly PCH loop: deterministic audit/report, then one batch reviewer pass.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
mkdir -p data

STAMP="$(date +%Y-%m-%d)"
LOG="data/weekly-$STAMP.log"

{
  echo "== PCH weekly $STAMP =="
  python3 scripts/audit.py --selftest
  python3 scripts/audit.py
  python3 scripts/report.py --write

  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "dry run: skipping batch reviewer"
    exit 0
  fi

  omp -p "Read prompts/weekly-review.md and execute it. Work only inside this repository. Do not merge, force-push, or commit to main." \
    --no-session --no-title --cwd "$REPO"

  python3 scripts/audit.py
  python3 scripts/report.py --write
  echo "== done =="
} 2>&1 | tee "$LOG"