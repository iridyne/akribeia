#!/usr/bin/env bash
# Fail when a mapped rule is missing from the provider payload, or an extension failed to load.
# Detection is the existing probe (adapters/omp/prompt-assert.ts); this script only gates on it.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# ponytail: PCH_PROBE is a test hook so the pass path is runnable while delivery is broken.
PROBE="${PCH_PROBE:-$REPO/adapters/omp/prompt-assert.ts}"

OUT="$(omp -p "Reply with the single word: ok" --no-title --no-session -e "$PROBE" 2>&1)"
STATUS=0

if grep -q 'Failed to load extension' <<<"$OUT"; then
  echo "delivery: extension failed to load"
  STATUS=1
fi
if grep -q 'ASSERT .*=false' <<<"$OUT"; then
  echo "delivery: rule missing from payload"
  STATUS=1
fi
grep -E '^ASSERT ' <<<"$OUT" || true

if [[ $STATUS -ne 0 ]]; then
  echo "delivery: broken; fix delivery and record an incident before measuring"
fi
exit $STATUS
