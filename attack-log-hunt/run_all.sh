#!/usr/bin/env bash
# Reproduce every number in this project from scratch.
# Downloads two public attack-log datasets (pinned commits), parses them, runs the
# Sigma rules, labels the hunt candidates and scores v1 vs v2.
set -euo pipefail
cd "$(dirname "$0")"

fetch () {  # fetch <repo url> <commit> <dest>
  if [ ! -d "$3/.git" ]; then
    mkdir -p "$3" && git -C "$3" init -q && git -C "$3" remote add origin "$1"
    git -C "$3" fetch -q --depth 1 origin "$2" && git -C "$3" checkout -q FETCH_HEAD
  fi
}
# Dev set: used to write and tune the rules (GPL-3.0, not redistributed here)
fetch https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES.git 4ceed2f4706daf601c212a8f91c113dd85349a2c data/dev
# Held-out set: only opened after v2 was frozen (CC0-1.0)
fetch https://github.com/mdecrevoisier/EVTX-to-MITRE-Attack.git 474856008f037ccd42753f02a631b42690195829 data/heldout

for set in dev heldout; do
  python src/parse_evtx.py data/$set results/$set
  python src/run_rules.py sigma/v1 v1 results/$set > /dev/null
  python src/run_rules.py sigma/v2 v2 results/$set > /dev/null
  python src/hunt.py results/$set > /dev/null
done
python src/label.py
python src/evaluate.py
