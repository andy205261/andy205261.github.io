"""
Load the synthetic data into SQLite, run the v1 (baseline) and v2 (tuned) SQL
rule sets, and score each against the ground-truth labels.

Outputs (output/):
  alerts_v1.csv, alerts_v2.csv        flagged events with the rules that fired
  user_risk_v1.csv, user_risk_v2.csv  investigation queue ranked by risk score
  metrics.json                        precision/recall, per-rule and per-scenario results
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "output"
OUT.mkdir(exist_ok=True)
TABLES = ["users", "patients", "encounters", "care_team", "consult_orders", "work_queue", "extra_shifts"]
LABELS = ["is_anomaly", "scenario", "context"]

truth = pd.read_csv(DATA / "access_log.csv").fillna({"context": ""})
bad_users = set(truth[truth.is_anomaly == 1].user_id)


def pr(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return round(p, 3), round(r, 3)


def run(version, sql_file):
    db = OUT / f"audit_{version}.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    for t in TABLES:
        pd.read_csv(DATA / f"{t}.csv").to_sql(t, con, index=False)
    # the detection layer only ever sees raw audit fields, never the labels
    truth.drop(columns=LABELS).to_sql("access_log", con, index=False)
    con.executescript("""
    CREATE INDEX ix_ct ON care_team(user_id, encounter_id);
    CREATE INDEX ix_enc ON encounters(patient_id);
    CREATE INDEX ix_enc_id ON encounters(encounter_id);
    CREATE INDEX ix_wq ON work_queue(user_id, patient_id);
    """)
    con.executescript((ROOT / "sql" / sql_file).read_text())

    hits = pd.read_sql("SELECT * FROM rule_hits", con)
    weights = pd.read_sql("SELECT * FROM rule_weights", con)
    risk = pd.read_sql("SELECT * FROM user_risk", con)
    con.close()

    alerts = (hits.groupby(["event_id", "user_id"])["rule_id"]
              .apply(lambda s: ", ".join(sorted(set(s)))).reset_index(name="rules"))
    alerts = alerts.merge(truth[["event_id", "patient_id", "access_time", "action", "break_the_glass"]],
                          on="event_id").sort_values("access_time")
    alerts.to_csv(OUT / f"alerts_{version}.csv", index=False)

    # ---- evaluation (labels joined only here)
    t = truth.copy()
    t["flagged"] = t.event_id.isin(set(hits.event_id)).astype(int)
    tp = int(((t.flagged == 1) & (t.is_anomaly == 1)).sum())
    fp = int(((t.flagged == 1) & (t.is_anomaly == 0)).sum())
    fn = int(((t.flagged == 0) & (t.is_anomaly == 1)).sum())
    ev_p, ev_r = pr(tp, fp, fn)

    # a user counts as caught only if at least one of their misuse events was flagged
    caught_users = set(t[(t.is_anomaly == 1) & (t.flagged == 1)].user_id)
    flag_users = set(risk.user_id)
    false_users = flag_users - bad_users
    us_p, us_r = pr(len(caught_users), len(false_users), len(bad_users - caught_users))

    risk["ground_truth_anomalous"] = risk.user_id.isin(bad_users).astype(int)
    risk.to_csv(OUT / f"user_risk_{version}.csv", index=False)
    top_n = 20
    top_true = int(risk.head(top_n).ground_truth_anomalous.sum())

    per_rule = []
    for _, w in weights.iterrows():
        ev = set(hits[hits.rule_id == w.rule_id].event_id)
        sub = t[t.event_id.isin(ev)]
        per_rule.append(dict(rule_id=w.rule_id, name=w["name"], weight=int(w.weight), events=len(ev),
                             true_pos=int(sub.is_anomaly.sum()), false_pos=int((sub.is_anomaly == 0).sum())))
    per_scen = []
    for s, g in t[t.is_anomaly == 1].groupby("scenario"):
        per_scen.append(dict(scenario=s, events=len(g), caught=int(g.flagged.sum()),
                             recall=round(float(g.flagged.mean()), 3),
                             users=int(g.user_id.nunique()),
                             users_caught=int(g[g.flagged == 1].user_id.nunique())))
    fpe = t[(t.flagged == 1) & (t.is_anomaly == 0)]
    fp_context = fpe.context.replace("", "Routine opens by the same care-team member").value_counts().to_dict()

    return dict(
        event_level=dict(flagged=int(t.flagged.sum()), tp=tp, fp=fp, fn=fn, precision=ev_p, recall=ev_r),
        user_level=dict(flagged=len(flag_users), caught=len(caught_users), false_users=len(false_users),
                        missed=len(bad_users - caught_users), precision=us_p, recall=us_r,
                        top_n=top_n, top_n_true=top_true),
        per_rule=per_rule, per_scenario=per_scen, false_positive_context=fp_context,
        top_queue=risk.head(12).to_dict(orient="records"),
    )


v1 = run("v1", "v1_baseline.sql")
v2 = run("v2", "v2_tuned.sql")
metrics = dict(
    dataset=dict(users=int(pd.read_csv(DATA / "users.csv").shape[0]),
                 patients=int(pd.read_csv(DATA / "patients.csv").shape[0]),
                 encounters=int(pd.read_csv(DATA / "encounters.csv").shape[0]),
                 events=len(truth), anomalous_events=int(truth.is_anomaly.sum()),
                 anomalous_users=len(bad_users), scenarios=int(truth[truth.is_anomaly == 1].scenario.nunique()),
                 active_users=int(truth.user_id.nunique())),
    v1=v1, v2=v2,
)
(OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))

for name, m in (("v1", v1), ("v2", v2)):
    print(f"== {name}")
    print(" events:", m["event_level"])
    print(" users :", m["user_level"])
    print(" FP context:", m["false_positive_context"])
    print(pd.DataFrame(m["per_scenario"]).to_string(index=False))
    print(pd.DataFrame(m["per_rule"]).to_string(index=False))
