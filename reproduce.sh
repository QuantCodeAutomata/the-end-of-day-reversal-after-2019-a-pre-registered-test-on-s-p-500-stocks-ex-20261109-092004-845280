#!/usr/bin/env bash
# Runs the test suite and every experiment of this replication, in the same
# commands as README.md. Market-data tests and experiment runs need
# DATALOADER_API_KEY and MASSIVE_API_KEY in the environment or in a .env file.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "== Unit tests (synthetic fixtures) =="
python -m pytest -m "not market_data"

echo "== Full test suite (includes a reduced real-data slice) =="
python -m pytest

echo "== exp1: main reversal test, primary sample =="
python -m exp.exp1

echo "== exp2: proxy sample =="
python -m exp.exp2

echo "== exp3: full index, no exclusions =="
python -m exp.exp3

echo "== exp4: mechanism tests =="
python -m exp.exp4

echo "== exp5: next-morning price pressure =="
python -m exp.exp5

echo "== exp6: change-point test =="
python -m exp.exp6

echo "Done. Results written to results/."
