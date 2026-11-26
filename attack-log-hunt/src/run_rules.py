"""
Convert each Sigma rule to SQL with pySigma (SQLite backend) and run it against
the parsed process events. Output: <out_dir>/hits_<version>.csv, printed summary.
Usage: python src/run_rules.py sigma/v1 v1 results/dev
"""
import csv, glob, sqlite3, sys, json
from pathlib import Path
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend
from defang import defang

ROOT = Path(__file__).resolve().parent.parent
rule_dir, version = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("sigma/v1", "v1")
OUT = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else ROOT / "results" / "dev"
con = sqlite3.connect(":memory:")
rows = list(csv.DictReader(open(OUT / "process_events.csv")))
cols = list(rows[0].keys())
con.execute(f"CREATE TABLE logs ({', '.join(c + ' TEXT' for c in cols)})")
con.executemany(f"INSERT INTO logs VALUES ({','.join('?' * len(cols))})", [tuple(r[c] for c in cols) for r in rows])

hits, summary = [], {}
for f in sorted(glob.glob(str(ROOT / rule_dir / "*.yml"))):
    col = SigmaCollection.from_yaml(open(f).read())
    rule = col.rules[0]
    rid = Path(f).name.split("_")[0]
    q = sqliteBackend().convert(col)[0]
    res = con.execute(q.replace("SELECT *", "SELECT event_id, tactic, evtx_file, Image, CommandLine")).fetchall()
    summary[rid] = dict(title=rule.title, hits=len(res), files=len({r[2] for r in res}))
    for r in res:
        hits.append(dict(rule=rid, event_id=r[0], tactic=r[1], evtx_file=r[2], Image=r[3], CommandLine=defang(r[4])))

with open(OUT / f"hits_{version}.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["rule", "event_id", "tactic", "evtx_file", "Image", "CommandLine"])
    w.writeheader(); w.writerows(hits)
(OUT / f"summary_{version}.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
