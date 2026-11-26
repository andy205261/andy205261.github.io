"""
Build index.html from the scored results, so every number on the page comes from
results/evaluation.json and results/evaluation_actions.csv.
Usage: python src/build_page.py
"""
import json, html, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
ev = json.loads((ROOT / "results" / "evaluation.json").read_text())
acts = pd.read_csv(ROOT / "results" / "evaluation_actions.csv")
stats = {ds: json.loads((ROOT / "results" / ds / "dataset_stats.json").read_text()) for ds in ["dev", "heldout"]}
hits_dev_v2 = pd.read_csv(ROOT / "results" / "dev" / "hits_v2.csv")
esc = html.escape
fmt = lambda n: f"{n:,}"
pct = lambda x: f"{round(x * 100)}%"

FAM = {
    "D1": ("Hidden or encoded PowerShell", "T1059.001"),
    "D2": ("Backdoor local account", "T1136.001"),
    "D3": ("Scheduled task for persistence", "T1053.005"),
    "D4": ("Backups and recovery destroyed", "T1490"),
    "D5": ("Microsoft Defender turned off", "T1562.001"),
}
V2_CHANGE = {
    "D1": "Added D1b: hidden window, IEX, Base64 decode, download, Gzip in memory",
    "D2": "No change (no examples in the dev set)",
    "D3": "Added the legacy <span class='mono'>at.exe</span> scheduler",
    "D4": "Added <span class='mono'>bcdedit bootstatuspolicy ignoreallfailures</span>",
    "D5": "No change (no examples in the dev set)",
}
FIX = {
    "D1": "PowerShell obfuscation has endless forms: <span class='mono'>-w 1</span> instead of <span class='mono'>-w hidden</span>, "
          "<span class='mono'>IEX</span> assembled from string pieces. Command-line strings will not keep up. PowerShell Script Block "
          "Logging (Event 4104) records the script after it is decoded, which is the better place to look.",
    "D4": "v2 only knew <span class='mono'>vssadmin</span> and the <span class='mono'>wbadmin</span> catalog. WMIC and "
          "<span class='mono'>wbadmin delete backup</span> do the same damage. The rule should follow the behaviour across tools: "
          "any shadow-copy delete, any <span class='mono'>wbadmin delete</span>.",
    "D5": "<span class='mono'>Set-MpPreference</span> has many off switches, and the service can be disabled with "
          "<span class='mono'>sc.exe</span>. Defender's own log records the change itself, whatever tool made it "
          "(Event 5001 real-time protection off, 5007 setting changed).",
}


def meter(c, n):
    if n == 0:
        return "<td class='mcell sub'>no examples</td>"
    w = round(100 * c / n)
    return (f"<td class='mcell'><div class='meter' role='img' aria-label='{c} of {n} caught'>"
            f"<span style='width:{w}%'></span></div><span class='mnum'>{c}/{n}</span></td>")


rows = []
for f, (name, tid) in FAM.items():
    cells = "".join(meter(ev[ds][v]["families"][f]["caught"], ev[ds][v]["families"][f]["in_scope"])
                    for ds in ["dev", "heldout"] for v in ["v1", "v2"])
    rows.append(f"<tr><td><b>{name}</b><div class='sub mono'>{f} · {tid}</div></td>{cells}</tr>")
fam_table = "\n".join(rows)

det_rows = "\n".join(
    f"<tr><td class='mono'>{f}</td><td>{name}<div class='sub mono'>{tid}</div></td><td>{V2_CHANGE[f]}</td></tr>"
    for f, (name, tid) in FAM.items())

miss = acts[(acts.dataset == "heldout") & (acts.version == "v2") & (~acts.caught)]
miss_blocks = []
for f, g in miss.groupby("family"):
    cmds = "".join(f"<div class='cmd'>{esc(c[:120])}{'…' if len(c) > 120 else ''}<div class='sub'>{esc(r)}</div></div>"
                   for c, r in zip(g.CommandLine, g.reason))
    miss_blocks.append(f"<div class='card miss'><div class='eyebrow'>{f} · {FAM[f][0]} · missed {len(g)} of "
                       f"{ev['heldout']['v2']['families'][f]['in_scope']}</div>{cmds}<p class='fix'><b>What it means.</b> {FIX[f]}</p></div>")
miss_html = "\n".join(miss_blocks)

d4 = hits_dev_v2[hits_dev_v2.rule == "D4"]
alert_lines = "".join(f"<div><span class='hl'>D4</span> {esc(c.strip())}</div>" for c in d4.CommandLine)

D, H = ev["dev"], ev["heldout"]
rep = {
    "{{DEV_FILES}}": fmt(stats["dev"]["evtx_files"]), "{{DEV_REC}}": fmt(stats["dev"]["records"]),
    "{{DEV_PROC}}": fmt(stats["dev"]["process_events"]), "{{HO_FILES}}": fmt(stats["heldout"]["evtx_files"]),
    "{{HO_REC}}": fmt(stats["heldout"]["records"]), "{{HO_PROC}}": fmt(stats["heldout"]["process_events"]),
    "{{DEV_N}}": str(D["v1"]["total"]["in_scope"]), "{{HO_N}}": str(H["v1"]["total"]["in_scope"]),
    "{{DEV_V1}}": pct(D["v1"]["total"]["recall"]), "{{DEV_V2}}": pct(D["v2"]["total"]["recall"]),
    "{{HO_V1}}": pct(H["v1"]["total"]["recall"]), "{{HO_V2}}": pct(H["v2"]["total"]["recall"]),
    "{{DEV_V1C}}": str(D["v1"]["total"]["caught"]), "{{DEV_V2C}}": str(D["v2"]["total"]["caught"]),
    "{{HO_V1C}}": str(H["v1"]["total"]["caught"]), "{{HO_V2C}}": str(H["v2"]["total"]["caught"]),
    "{{FALSE}}": str(sum(ev[d][v]["total"]["false_hits"] for d in ev for v in ev[d])),
    "{{REPEAT}}": str(H["v2"]["total"]["repeat_alerts"]),
    "{{ALL_PROC}}": fmt(stats["dev"]["process_events"] + stats["heldout"]["process_events"]),
    "{{FAM_TABLE}}": fam_table, "{{DET_ROWS}}": det_rows, "{{MISSES}}": miss_html, "{{ALERTS}}": alert_lines,
    "{{GAP}}": str(round(100 * (D["v2"]["total"]["recall"] - H["v2"]["total"]["recall"]))),
}
page = (ROOT / "src" / "page_template.html").read_text()
for k, v in rep.items():
    page = page.replace(k, v)
assert "{{" not in page, page[page.index("{{"):page.index("{{") + 40]
(ROOT / "index.html").write_text(page)
print("wrote index.html", len(page), "bytes")
