# Ransomware Precursor Hunt

Five Sigma detections for the steps ransomware takes before it encrypts a hospital's files, tuned on one set of public attack logs and tested on a second set that was opened only after the rules were frozen.

**Results page:** https://andy205261.github.io/attack-log-hunt/

| | Dev set (tuned on) | Held-out set (never seen) |
|---|---|---|
| Dataset | [EVTX-ATTACK-SAMPLES](https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES) (GPL-3.0) | [EVTX-to-MITRE-Attack](https://github.com/mdecrevoisier/EVTX-to-MITRE-Attack) (CC0-1.0) |
| Log files / events / process starts | 278 / 37,364 / 1,533 | 293 / 12,812 / 1,296 |
| In-scope attack actions (labelled) | 19 | 18 |
| v1 caught | 11 (58%) | 3 (17%) |
| v2 caught | 18 (95%) | 10 (56%) |
| False hits, v1 and v2 | 0 | 0 (1 repeat alert: `net1.exe`) |

The gap between 95% and 56% is the point: the dev-set number shows how well the rules fit the data I studied; the held-out number is closer to what a SOC would get. Every held-out miss, and what it says about the rule, is on the results page.

## Detections

| ID | Attacker step | ATT&CK |
|---|---|---|
| D1, D1b | Hidden, encoded or in-memory PowerShell | T1059.001 |
| D2 | Backdoor local account (`net user /add`) | T1136.001 |
| D3 | Scheduled task for persistence (`schtasks /create`, `at`) | T1053.005 |
| D4 | Shadow copies, backup catalog or recovery destroyed | T1490 |
| D5 | Microsoft Defender turned off | T1562.001 |

## How it works

1. `src/parse_evtx.py` reads every EVTX file and keeps process starts (Sysmon Event 1, Security Event 4688).
2. `src/run_rules.py` converts each Sigma rule to SQL with pySigma (SQLite backend) and runs it.
3. `src/hunt.py` pulls every possible candidate with loose keyword searches.
4. `src/label.py` labels each candidate by hand (in_scope / duplicate / out_of_scope, with a reason). Every candidate must match a label or the script stops.
5. `src/evaluate.py` scores caught, missed, false hits and repeat alerts per rule, dataset and version.
6. `src/build_page.py` builds `index.html` from the results.

The unit of scoring is one unique action (log file + command line). A `cmd.exe /c` wrapper or a `net.exe` → `net1.exe` pair is the same action seen twice.

## Run it

```bash
pip install -r requirements.txt
bash run_all.sh            # downloads both datasets at pinned commits, then parses, detects, labels, scores
python src/build_page.py
```

## Layout

```
sigma/v1, sigma/v2   detection rules
src/                 pipeline (above)
labels/              hand labels for every hunt candidate
results/             hits per rule, dataset stats, evaluation
```

## Limits

- Both datasets are lab attack recordings, not a hospital workday, so zero false hits says nothing about noise at a real site.
- 19 and 18 actions are enough to find blind spots, not to quote a detection rate with confidence.
- One labeller (me). Labels and reasons are in `src/label.py` so any call can be challenged.

## Data and safety

Raw logs are not redistributed: `run_all.sh` downloads them. Command lines in `results/` and `labels/` are short excerpts for analysis, with URLs defanged (`hxxps`). No patient data, no employer data.

---
Andy (Anh Truong) Nguyen · Healthcare security portfolio
