"""
Parse every EVTX file in a folder of public attack logs and keep the
process-creation events the detection rules read:
  - Sysmon Event ID 1 (Microsoft-Windows-Sysmon/Operational)
  - Windows Security Event ID 4688
Usage:  python src/parse_evtx.py data/dev results/dev
        python src/parse_evtx.py data/heldout results/heldout
Output: <out_dir>/process_events.csv  (one row per process start)
        <out_dir>/dataset_stats.json
"""
import csv, json, sys
from pathlib import Path
import xml.etree.ElementTree as ET
from evtx import PyEvtxParser   # Rust-based parser (pip install evtx); python-evtx failed on ~13% of held-out records

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "data" / "dev"
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else ROOT / "results" / "dev"
OUT.mkdir(parents=True, exist_ok=True)
NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}

rows, files, total, bad = [], 0, 0, 0
for path in sorted(DATA.rglob("*.evtx")):
    files += 1
    rel = path.relative_to(DATA)
    tactic = rel.parts[0] if len(rel.parts) > 1 else "(root)"
    try:
        for rec in PyEvtxParser(str(path)).records():
            total += 1
            try:
                x = ET.fromstring(rec["data"])
            except Exception:
                bad += 1
                continue
            sysn = x.find("e:System", NS)
            eid = (sysn.findtext("e:EventID", default="", namespaces=NS) or "").strip()
            chan = sysn.findtext("e:Channel", default="", namespaces=NS) or ""
            data = {d.get("Name"): (d.text or "") for d in x.iter("{%s}Data" % NS["e"]) if d.get("Name")}
            if eid == "1" and "Sysmon" in chan:
                src, img, cmd = "sysmon_1", data.get("Image", ""), data.get("CommandLine", "")
                ofn, parent, user, t = data.get("OriginalFileName", ""), data.get("ParentImage", ""), data.get("User", ""), data.get("UtcTime", "")
            elif eid == "4688" and chan == "Security":
                src, img, cmd = "security_4688", data.get("NewProcessName", ""), data.get("CommandLine", "")
                ofn, parent, user = "", data.get("ParentProcessName", ""), data.get("SubjectUserName", "")
                tc = sysn.find("e:TimeCreated", NS); t = tc.get("SystemTime") if tc is not None else ""
            else:
                continue
            rows.append(dict(event_id=f"{len(rows)+1:05d}", source=src, tactic=tactic, evtx_file=rel.name,
                             time=t, Image=img, CommandLine=cmd, OriginalFileName=ofn,
                             ParentImage=parent, User=user))
    except Exception as ex:
        print("skip", rel, ex, file=sys.stderr)

with open(OUT / "process_events.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
stats = dict(evtx_files=files, records=total, unparsed=bad, process_events=len(rows),
             sysmon_1=sum(r["source"] == "sysmon_1" for r in rows),
             security_4688=sum(r["source"] == "security_4688" for r in rows),
             files_with_process_events=len({r["evtx_file"] for r in rows}))
(OUT / "dataset_stats.json").write_text(json.dumps(stats, indent=2))
print(json.dumps(stats, indent=2))
