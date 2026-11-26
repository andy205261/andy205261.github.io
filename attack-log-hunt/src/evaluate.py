"""
Score v1 and v2 rules against the hand-labelled ground truth, on both datasets.

  caught        in-scope actions with at least one hit from the rule family
  false hits    hits on anything not labelled in_scope or duplicate
  repeat alerts hits on a duplicate of an action (cmd.exe wrapper, net1.exe)

Usage: python src/evaluate.py
Output: results/evaluation.json, results/evaluation_actions.csv
"""
import json, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETS = {"dev": ROOT / "results" / "dev", "heldout": ROOT / "results" / "heldout"}
FAMILIES = ["D1", "D2", "D3", "D4", "D5"]
lab = pd.read_csv(ROOT / "labels" / "ground_truth.csv")
key = lambda df: list(zip(df.evtx_file, df.CommandLine.fillna("")))

result, actions = {}, []
for ds, out in SETS.items():
    L = lab[lab.dataset == ds]
    result[ds] = {}
    for ver in ["v1", "v2"]:
        h = pd.read_csv(out / f"hits_{ver}.csv")
        h["family"] = h.rule.str[:2]
        fam_res = {}
        for fam in FAMILIES:
            Lf = L[L.family == fam]
            hk = set(key(h[h.family == fam]))
            ins = Lf[Lf.label == "in_scope"]
            dup = set(key(Lf[Lf.label == "duplicate"]))
            good = set(key(ins))
            caught = [k for k in key(ins) if k in hk]
            fam_res[fam] = dict(in_scope=len(ins), caught=len(caught),
                                false_hits=len([k for k in hk if k not in good and k not in dup]),
                                repeat_alerts=len([k for k in hk if k in dup]))
            for (f, c), why in zip(key(ins), ins.reason):
                actions.append(dict(dataset=ds, version=ver, family=fam, evtx_file=f, reason=why,
                                    caught=(f, c) in hk, CommandLine=c[:200]))
        tot = {k: sum(v[k] for v in fam_res.values()) for k in ["in_scope", "caught", "false_hits", "repeat_alerts"]}
        tot["recall"] = round(tot["caught"] / tot["in_scope"], 3)
        result[ds][ver] = dict(families=fam_res, total=tot)

(ROOT / "results" / "evaluation.json").write_text(json.dumps(result, indent=2))
pd.DataFrame(actions).to_csv(ROOT / "results" / "evaluation_actions.csv", index=False)
for ds in result:
    for ver in result[ds]:
        t = result[ds][ver]["total"]
        fams = "  ".join(f"{f} {v['caught']}/{v['in_scope']}" for f, v in result[ds][ver]["families"].items())
        print(f"{ds:8} {ver}: caught {t['caught']}/{t['in_scope']} ({t['recall']:.0%})  false hits {t['false_hits']}  repeat {t['repeat_alerts']}  | {fams}")
