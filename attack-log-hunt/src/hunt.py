"""Broad, deliberately loose hunt for every event that *might* belong to one of the five
techniques. Each candidate is then labelled by hand in src/label.py.
Usage: python src/hunt.py results/dev
The labels, not the rules, decide what counts as a real in-scope attack action."""
import sqlite3, sys, pandas as pd, pathlib
from defang import defang
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'results/dev'); df = pd.read_csv(OUT / 'process_events.csv')
con = sqlite3.connect(':memory:'); df.to_sql('logs', con, index=False)
HUNTS = {
  'T1059.001 PowerShell': "lower(Image) LIKE '%powershell%' OR lower(Image) LIKE '%pwsh%' OR lower(CommandLine) LIKE '%powershell%'",
  'T1136.001 Local account': "(lower(Image) LIKE '%\\net.exe' OR lower(Image) LIKE '%\\net1.exe' OR lower(CommandLine) LIKE '%net user%' OR lower(CommandLine) LIKE '%new-localuser%') ",
  'T1053.005 Scheduled task': "lower(Image) LIKE '%schtasks%' OR lower(Image) LIKE '%\\at.exe' OR lower(CommandLine) LIKE '%register-scheduledtask%' OR lower(CommandLine) LIKE '%schtasks%'",
  'T1490 Inhibit recovery': "lower(CommandLine) LIKE '%shadow%' OR lower(Image) LIKE '%wbadmin%' OR lower(Image) LIKE '%bcdedit%' OR lower(Image) LIKE '%vssadmin%' OR lower(Image) LIKE '%diskshadow%'",
  'T1562.001 Defender tampering': "lower(CommandLine) LIKE '%mppreference%' OR lower(CommandLine) LIKE '%windefend%' OR lower(CommandLine) LIKE '%windows defender%' OR lower(Image) LIKE '%mpcmdrun%' OR lower(CommandLine) LIKE '%disablerealtime%'",
}
rows = []
for tech, where in HUNTS.items():
    q = f"SELECT evtx_file, Image, CommandLine, ParentImage FROM logs WHERE {where}"
    for r in con.execute(q).fetchall():
        rows.append((tech,) + r)
c = pd.DataFrame(rows, columns=['technique', 'evtx_file', 'Image', 'CommandLine', 'ParentImage'])
c['image_name'] = c.Image.str.split('\\').str[-1].str.lower()
c['CommandLine'] = c.CommandLine.map(defang)
c = c.drop_duplicates(['technique', 'evtx_file', 'CommandLine'])
c.to_csv(OUT / 'hunt_candidates.csv', index=False)
print(c.groupby('technique').size())
