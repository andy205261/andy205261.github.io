"""Build the portfolio page (index.html) from output/metrics.json."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = json.loads((ROOT / "output" / "metrics.json").read_text())
d, v1, v2 = M["dataset"], M["v1"], M["v2"]
esc = html.escape


def pct(x):
    return f"{x * 100:.1f}%"


# ---- scenario table
v1s = {s["scenario"]: s for s in v1["per_scenario"]}
order = sorted(v2["per_scenario"], key=lambda s: (-s["recall"] + v1s[s["scenario"]]["recall"], s["scenario"]))
order = sorted(v2["per_scenario"], key=lambda s: (v1s[s["scenario"]]["recall"] == 1, s["scenario"]))
DESC = {
    "VIP snooping": "Staff open a public figure's chart with no care role",
    "Family record snooping": "Staff open a relative's chart (same last name and address)",
    "Coworker snooping": "Staff open a colleague's chart from another unit",
    "Break-the-glass misuse": "Emergency override used with no emergency",
    "Bulk record browsing": "Dozens of unrelated charts opened in a few hours",
    "Access after termination": "A closed account keeps opening charts",
    "After-hours access": "Unrelated charts opened at 1 to 4 a.m. by day staff",
    "Low-and-slow browsing": "One or two unrelated charts a day, every few days",
    "Excessive access by care-team member": "A nurse on the team reopens a VIP chart far beyond need",
    "Curiosity break-the-glass on coworker": "ED nurse overrides into a coworker's live ED visit",
}


def meter(caught, total):
    w = 0 if total == 0 else caught / total * 100
    return (f'<div class="meter" role="img" aria-label="{caught} of {total} caught">'
            f'<span style="width:{w:.0f}%"></span></div><span class="mnum">{caught}/{total}</span>')


rows = []
for s in order:
    a = v1s[s["scenario"]]
    rows.append(f"<tr><td><b>{esc(s['scenario'])}</b><div class='sub'>{esc(DESC.get(s['scenario'], ''))}</div></td>"
                f"<td class='num'>{s['events']}</td>"
                f"<td class='mcell'>{meter(a['caught'], a['events'])}</td>"
                f"<td class='mcell'>{meter(s['caught'], s['events'])}</td></tr>")
scen_rows = "\n".join(rows)

# ---- false-positive cause bars (v1)
fps = sorted(v1["false_positive_context"].items(), key=lambda kv: -kv[1])
fmax = max(v for _, v in fps)
FIX = {
    "Approved retrospective quality audit": "Approved work queue",
    "Picked up an extra evening shift on another unit": "Staffing schedule",
    "Claim denial rework after hours": "Approved work queue",
    "Specialist consult, not on care team": "Consult orders",
    "Float coverage, assignment not recorded": "Not fixed (no record exists)",
}
bars = []
for k, v in fps:
    w = v / fmax * 100
    bars.append(
        f'<div class="frow" tabindex="0" data-tip="{esc(k)}: {v} false alerts in v1. Fixed in v2 by: {esc(FIX.get(k, "-"))}">'
        f'<div class="flbl">{esc(k)}</div>'
        f'<div class="ftrack"><span class="fbar" style="width:{w:.1f}%"></span><span class="fval">{v}</span></div></div>')
fp_svg = '<div class="fpchart" role="img" aria-label="v1 false alerts by cause">' + "".join(bars) + "</div>"
fp_table = "".join(f"<tr><td>{esc(k)}</td><td class='num'>{v}</td><td>{esc(FIX.get(k, '-'))}</td></tr>" for k, v in fps)

# ---- rules table
RULE_WHY = {
    "R1": "Minimum necessary", "R2": "Family snooping", "R3": "Coworker snooping",
    "R4": "Emergency access review", "R5": "Bulk browsing", "R6": "Termination procedures",
    "R7": "Off-hours curiosity", "R8": "Low-and-slow browsing", "R9": "Over-access by insiders on the team",
}
v1r = {r["rule_id"]: r for r in v1["per_rule"]}
rule_rows = []
for r in v2["per_rule"]:
    a = v1r.get(r["rule_id"])
    tag = "" if a else " <span class='new'>v2</span>"
    v1cell = f"{a['true_pos']} / {a['false_pos']}" if a else "-"
    rule_rows.append(f"<tr><td class='mono'>{r['rule_id']}</td><td>{esc(r['name'])}{tag}</td>"
                     f"<td class='num'>{r['weight']}</td><td class='num'>{v1cell}</td>"
                     f"<td class='num'>{r['true_pos']} / {r['false_pos']}</td></tr>")
rule_rows = "\n".join(rule_rows)

# ---- queue
q_rows = "\n".join(
    f"<tr><td class='num'>{i + 1}</td><td class='mono'>{q['user_id']}</td><td>{esc(q['role'])}</td>"
    f"<td>{esc(q['department'])}</td><td class='mono'>{esc(q['rules'])}</td>"
    f"<td class='num'>{q['flagged_events']}</td><td class='num'><b>{q['risk_score']}</b></td></tr>"
    for i, q in enumerate(v2["top_queue"][:10]))

e1, e2, u1, u2 = v1["event_level"], v2["event_level"], v1["user_level"], v2["user_level"]

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EHR Access Monitoring</title>
<meta name="description" content="Detecting insider snooping in hospital EHR audit logs with SQL rules, tuned from a baseline using clinical context. Synthetic data only.">
<style>
:root {{
  color-scheme: light;
  --bg:#f7f7f5; --surface:#ffffff; --ink:#191919; --ink-2:#555555; --ink-3:#767676;
  --line:#e3e3df; --accent:#0f766e; --accent-soft:#e6f2f0;
  --series-1:#257de0; --meter-track:#ececec; --code:#f1f1ee;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --bg:#121212; --surface:#191919; --ink:#efefef; --ink-2:#b4b4b4; --ink-3:#9c9c9c;
    --line:#2e2e2e; --accent:#3cb5a8; --accent-soft:#16302d;
    --series-1:#338ced; --meter-track:#2c2c2c; --code:#222222;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --bg:#121212; --surface:#191919; --ink:#efefef; --ink-2:#b4b4b4; --ink-3:#9c9c9c;
  --line:#2e2e2e; --accent:#3cb5a8; --accent-soft:#16302d;
  --series-1:#338ced; --meter-track:#2c2c2c; --code:#222222;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
.wrap {{ max-width:960px; margin:0 auto; padding:40px 16px 64px; }}
a {{ color:var(--accent); }}
.eyebrow {{ font-size:13px; letter-spacing:.08em; text-transform:uppercase; color:var(--accent); font-weight:600; }}
h1 {{ font-size:clamp(28px,5vw,42px); line-height:1.15; margin:8px 0 12px; letter-spacing:-.01em; }}
h2 {{ font-size:22px; margin:48px 0 12px; }}
h3 {{ font-size:16px; margin:24px 0 8px; }}
.lede {{ font-size:18px; color:var(--ink-2); max-width:720px; }}
.tags {{ display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; }}
.tags span {{ font-size:13px; padding:3px 10px; border:1px solid var(--line); border-radius:999px; color:var(--ink-2); background:var(--surface); }}
.note {{ background:var(--accent-soft); border-left:3px solid var(--accent); padding:12px 16px; border-radius:6px; font-size:14px; color:var(--ink-2); }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:20px; }}
.grid4 {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
.grid3 {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }}
.stat .k {{ font-size:13px; color:var(--ink-3); }}
.stat .v {{ font-size:30px; font-weight:650; letter-spacing:-.01em; }}
.stat .d {{ font-size:13px; color:var(--ink-2); }}
.arrow {{ color:var(--ink-3); font-weight:400; margin:0 4px; font-size:22px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th {{ text-align:left; font-weight:600; color:var(--ink-3); font-size:12px; text-transform:uppercase; letter-spacing:.05em; padding:8px; border-bottom:1px solid var(--line); }}
td {{ padding:10px 8px; border-bottom:1px solid var(--line); vertical-align:top; }}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.mono {{ font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:13px; }}
.sub {{ color:var(--ink-3); font-size:13px; }}
.tablewrap {{ overflow-x:auto; }}
.tablewrap table {{ min-width:600px; }}
.mcell {{ white-space:nowrap; width:170px; }}
.meter {{ display:inline-block; width:100px; height:8px; background:var(--meter-track); border-radius:4px; vertical-align:middle; overflow:hidden; }}
.meter span {{ display:block; height:100%; background:var(--series-1); border-radius:4px; }}
.mnum {{ margin-left:8px; font-variant-numeric:tabular-nums; font-size:13px; color:var(--ink-2); }}
.new {{ font-size:11px; font-weight:600; color:var(--accent); border:1px solid var(--accent); border-radius:4px; padding:0 4px; margin-left:4px; }}
.flow {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; counter-reset:step; }}
.flow div {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:14px; font-size:14px; color:var(--ink-2); }}
.flow b {{ display:block; color:var(--ink); margin-bottom:4px; }}
.flow div::before {{ counter-increment:step; content:counter(step); display:inline-block; width:22px; height:22px; border-radius:50%; background:var(--accent); color:#fff; font-size:12px; text-align:center; line-height:22px; margin-bottom:6px; }}
.fpchart {{ display:grid; gap:10px; }}
.frow {{ display:grid; grid-template-columns:minmax(0,300px) minmax(0,1fr); gap:12px; align-items:center; font-size:14px; outline:none; }}
.flbl {{ color:var(--ink-2); text-align:right; }}
.ftrack {{ display:flex; align-items:center; gap:8px; }}
.fbar {{ display:block; height:22px; background:var(--series-1); border-radius:0 4px 4px 0; min-width:4px; }}
.fval {{ font-weight:600; font-variant-numeric:tabular-nums; }}
.frow:hover .fbar, .frow:focus .fbar {{ opacity:.8; }}
.tip {{ position:fixed; pointer-events:none; background:var(--ink); color:var(--bg); font-size:13px; padding:6px 10px; border-radius:6px; max-width:280px; opacity:0; transition:opacity .1s; z-index:10; }}
details {{ margin-top:10px; font-size:14px; }}
summary {{ cursor:pointer; color:var(--accent); }}
pre {{ background:var(--code); border:1px solid var(--line); border-radius:8px; padding:14px; overflow-x:auto; font-size:13px; line-height:1.5; }}
ul.clean {{ padding-left:20px; }} ul.clean li {{ margin:4px 0; }}
footer {{ margin-top:56px; font-size:13px; color:var(--ink-3); border-top:1px solid var(--line); padding-top:16px; }}
@media (max-width:720px) {{
  .grid4, .flow {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
  .grid3 {{ grid-template-columns:1fr; }}
  .mcell {{ width:auto; }} .meter {{ width:60px; }}
  .frow {{ grid-template-columns:1fr; gap:4px; }} .flbl {{ text-align:left; }}
}}
</style>
</head>
<body>
<div class="wrap">

<div class="eyebrow">Healthcare security · Project</div>
<h1>EHR Access Monitoring</h1>
<p class="lede">Detecting insider snooping in hospital audit logs: who opened a patient's chart without a reason to.
SQL rules check every chart access against care-team assignments, encounters and roles, then rank users into an investigation queue.</p>
<div class="tags"><span>SQL (SQLite)</span><span>Python</span><span>HIPAA audit controls</span><span>Insider threat</span><span>EHR / Epic-style audit logs</span><span>Detection tuning</span></div>
<p class="note"><b>All data is synthetic.</b> "Riverside General Hospital", its staff and patients are fictional and generated by code in this repo. No real PHI, no real organization, no employer data.</p>

<h2>Why this matters</h2>
<p>Hospitals must record and regularly review who accesses patient records. The hard part isn't logging, it's review: tens of thousands of chart opens a month, almost all legitimate.
A privacy analyst needs a short, ranked list of the people worth investigating, not a wall of alerts. This project builds that list and measures how good it is.</p>

<h2>The dataset</h2>
<div class="grid4">
  <div class="card stat"><div class="k">Chart access events</div><div class="v">{d['events']:,}</div><div class="d">30 days</div></div>
  <div class="card stat"><div class="k">Workforce</div><div class="v">{d['users']}</div><div class="d">{d['active_users']} with activity</div></div>
  <div class="card stat"><div class="k">Patients / encounters</div><div class="v">{d['patients']:,}</div><div class="d">{d['encounters']:,} encounters</div></div>
  <div class="card stat"><div class="k">Planted misuse</div><div class="v">{d['anomalous_events']}</div><div class="d">{d['anomalous_users']} users, {d['scenarios']} scenarios</div></div>
</div>
<p class="sub" style="margin-top:10px">Besides misuse, the data includes legitimate work that looks suspicious on purpose: specialist consults, quality audits, extra shifts, after-hours billing, float coverage. A detector that can't tell these apart is not useful.</p>

<h2>How it works</h2>
<div class="flow">
  <div><b>Ingest</b>Audit log, users, patients, encounters and care teams load into SQLite.</div>
  <div><b>Relationship check</b>Each access is tested: care team, role-based need (lab, pharmacy, registration, billing), or justified emergency access.</div>
  <div><b>Rules</b>{len(v2['per_rule'])} SQL rules flag patterns among accesses with no relationship.</div>
  <div><b>Risk queue</b>Rule weights roll up into one score per user, ranked for review.</div>
</div>

<h3>Detection rules</h3>
<div class="card tablewrap"><table>
<thead><tr><th>ID</th><th>Rule</th><th class="num">Weight</th><th class="num">v1 hits (true / false)</th><th class="num">v2 hits (true / false)</th></tr></thead>
<tbody>{rule_rows}</tbody></table></div>

<h2>Results: baseline, then tuned</h2>
<p><b>v1</b> used only the core clinical tables. Reviewing its false alerts showed they were legitimate work the rules couldn't see.
<b>v2</b> adds three context sources real hospitals already have (consult orders, approved work queues, staffing schedules) and two behavioral rules for the misuse v1 missed.</p>
<div class="grid3">
  <div class="card stat"><div class="k">Users wrongly flagged</div><div class="v">{u1['false_users']}<span class="arrow">→</span>{u2['false_users']}</div><div class="d">Analyst time saved on false leads</div></div>
  <div class="card stat"><div class="k">Event precision</div><div class="v">{pct(e1['precision'])}<span class="arrow">→</span>{pct(e2['precision'])}</div><div class="d">Share of flagged events that were real misuse</div></div>
  <div class="card stat"><div class="k">Misusers caught</div><div class="v">{u1['caught']}<span class="arrow">→</span>{u2['caught']}</div><div class="d">of {d['anomalous_users']} planted</div></div>
</div>
<p class="sub" style="margin-top:10px">Event recall went from {pct(e1['recall'])} to {pct(e2['recall'])}. In v2, all of the top {u2['top_n']} users in the queue are real misusers ({u2['top_n_true']}/{u2['top_n']}); in v1 it was {u1['top_n_true']}/{u1['top_n']}.
Only {u2['flagged']} of {d['active_users']} active users reach the queue.</p>

<h3>Catch rate by misuse scenario</h3>
<div class="card tablewrap"><table>
<thead><tr><th>Scenario</th><th class="num">Events</th><th>v1 caught</th><th>v2 caught</th></tr></thead>
<tbody>{scen_rows}</tbody></table></div>

<h3>Where v1's false alerts came from</h3>
<div class="card">
{fp_svg}
<details><summary>Show as table</summary>
<div class="tablewrap"><table><thead><tr><th>Cause</th><th class="num">False alerts (v1)</th><th>Context added in v2</th></tr></thead><tbody>{fp_table}</tbody></table></div>
</details>
</div>

<h3>Investigation queue (v2, top 10)</h3>
<div class="card tablewrap"><table>
<thead><tr><th class="num">#</th><th>User</th><th>Role</th><th>Dept</th><th>Rules</th><th class="num">Flagged events</th><th class="num">Score</th></tr></thead>
<tbody>{q_rows}</tbody></table></div>

<h2>What's still hard</h2>
<ul class="clean">
<li><b>Curiosity hidden inside a real emergency.</b> An ED nurse used break-the-glass on a coworker's live ED visit. The override looks justified, so v2 still misses it. Fix: always review break-the-glass on staff and VIP records, even when an emergency is active.</li>
<li><b>Rule R9 flags the whole pattern.</b> It marks every open by the over-accessing team member, including routine ones, which accounts for most of v2's remaining false events. At user level the call is correct.</li>
<li><b>Float coverage with no assignment on record</b> still looks like snooping. That is a data-quality gap to fix at the source, not with a looser rule.</li>
<li><b>Thresholds are tuned to this data.</b> A real deployment would baseline each role and unit (peer groups) before setting limits.</li>
</ul>

<h2>HIPAA Security Rule mapping</h2>
<div class="card tablewrap"><table>
<thead><tr><th>Requirement</th><th>Where it shows up</th></tr></thead>
<tbody>
<tr><td>Audit controls, 45 CFR 164.312(b)</td><td>Access log captured and analyzed end to end</td></tr>
<tr><td>Information system activity review, 164.308(a)(1)(ii)(D)</td><td>Ranked investigation queue for regular review</td></tr>
<tr><td>Information access management, 164.308(a)(4); minimum necessary, 164.502(b)</td><td>Relationship check, R1–R3, R5, R8, R9</td></tr>
<tr><td>Emergency access procedure, 164.312(a)(2)(ii)</td><td>Break-the-glass review, R4</td></tr>
<tr><td>Termination procedures, 164.308(a)(3)(ii)(C)</td><td>Closed accounts still in use, R6</td></tr>
</tbody></table></div>

<h2>Run it</h2>
<pre>pip install pandas
python src/generate_data.py   # synthetic hospital + labeled misuse
python src/run_detection.py   # v1 and v2 rules, scored against labels
python src/build_page.py      # this page</pre>
<p class="sub">Rules live in <span class="mono">sql/v1_baseline.sql</span> and <span class="mono">sql/v2_tuned.sql</span>. Ground-truth labels are never visible to the SQL; they are joined only when scoring.</p>

<footer>Built by Andy (Anh Truong Nguyen) · Synthetic data, fictional hospital · Part of a healthcare security portfolio</footer>
</div>
<div class="tip" id="tip" role="tooltip"></div>
<script>
(function () {{
  var tip = document.getElementById('tip');
  document.querySelectorAll('.fpchart .frow').forEach(function (g) {{
    function show(x, y) {{ tip.textContent = g.getAttribute('data-tip'); tip.style.left = Math.min(x + 12, window.innerWidth - 300) + 'px'; tip.style.top = (y + 12) + 'px'; tip.style.opacity = 1; }}
    g.addEventListener('mousemove', function (e) {{ show(e.clientX, e.clientY); }});
    g.addEventListener('mouseleave', function () {{ tip.style.opacity = 0; }});
    g.addEventListener('focus', function () {{ var r = g.getBoundingClientRect(); show(r.left + 40, r.top); }});
    g.addEventListener('blur', function () {{ tip.style.opacity = 0; }});
  }});
}})();
</script>
</body>
</html>
"""
(ROOT / "index.html").write_text(page)
print("wrote index.html")
