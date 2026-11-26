"""
Generate a fully synthetic EHR access-audit dataset for a fictional hospital
("Riverside General Hospital"). No real patients, staff, or organizations.

Outputs (data/):
  users.csv, patients.csv, encounters.csv, care_team.csv, access_log.csv
access_log.csv carries ground-truth labels (is_anomaly, scenario) that the
detection rules never read; they are used only to score the rules afterwards.
"""
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

SEED = 42
rng = random.Random(SEED)
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)

START = datetime(2026, 9, 1)
DAYS = 30
END = START + timedelta(days=DAYS)

FIRST = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery", "Quinn", "Drew",
         "Sam", "Cameron", "Reese", "Hayden", "Parker", "Rowan", "Skyler", "Emerson", "Finley", "Sage",
         "Linh", "Minh", "Mai", "Wei", "Priya", "Arjun", "Sofia", "Mateo", "Lucia", "Omar",
         "Amara", "Kofi", "Hana", "Yuki", "Elena", "Diego", "Nadia", "Tariq", "Ines", "Leo"]
LAST = ["Alvarez", "Brooks", "Chen", "Dawson", "Ellis", "Foster", "Garcia", "Hughes", "Ibarra", "Jensen",
        "Khan", "Lopez", "Morales", "Nguyen", "Okafor", "Patel", "Quinn", "Reyes", "Silva", "Tran",
        "Ueda", "Vargas", "Walsh", "Xu", "Young", "Zimmer", "Bennett", "Castillo", "Duarte", "Evans",
        "Fischer", "Gupta", "Hoang", "Ito", "Kim", "Le", "Mendez", "Novak", "Ortiz", "Pham",
        "Rossi", "Sato", "Torres", "Vo", "Weber", "Yamada", "Abbott", "Barnes", "Cruz", "Dang"]

CLINICAL = ["ED", "ICU", "Oncology", "Cardiology", "MedSurg"]


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def on_shift(hour, shift):
    if shift == "day":
        return 7 <= hour < 19
    if shift == "night":
        return hour >= 19 or hour < 7
    return 8 <= hour < 17  # office


# ---------------------------------------------------------------- workforce
users = []
uid = 1000


def add_user(role, dept, shift):
    global uid
    uid += 1
    users.append(dict(user_id=f"U{uid}", name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                      last_name=None, role=role, department=dept, shift=shift,
                      address_id=f"A{rng.randint(10000, 99999)}", status="active", term_date=None))
    users[-1]["last_name"] = users[-1]["name"].split()[1]


for d in CLINICAL:
    for i in range(8):
        add_user("Physician", d, "night" if d in ("ED", "ICU") and i < 2 else "day")
    for i in range(30):
        add_user("Nurse", d, "day" if i < 16 else "night")
for _ in range(15):
    add_user("Pharmacist", "Pharmacy", "day")
for _ in range(25):
    add_user("Registration", "Registration", "office")
for _ in range(20):
    add_user("Billing", "Billing", "office")
for _ in range(20):
    add_user("Lab Tech", "Lab", "day")
for _ in range(10):
    add_user("IT Analyst", "IT", "office")

for u in rng.sample(users, 6):  # six accounts terminated mid-month
    u["status"] = "terminated"
    u["term_date"] = ts(START + timedelta(days=rng.randint(8, 18), hours=17))

U = pd.DataFrame(users)
by_dept = {d: [u for u in users if u["department"] == d] for d in U.department.unique()}

# ---------------------------------------------------------------- patients
patients = []
pid = 500000


def add_patient(last=None, addr=None, vip=0, emp=None):
    global pid
    pid += 1
    last = last or rng.choice(LAST)
    patients.append(dict(patient_id=f"P{pid}", name=f"{rng.choice(FIRST)} {last}", last_name=last,
                         address_id=addr or f"A{rng.randint(10000, 99999)}", vip_flag=vip,
                         employee_user_id=emp))
    return patients[-1]


for _ in range(2400):
    add_patient()
for _ in range(25):  # VIP / public-figure records
    add_patient(vip=1)
emp_users = rng.sample([u for u in users if u["status"] == "active"], 30)
for u in emp_users:  # staff who are also patients (own record)
    add_patient(last=u["last_name"], addr=u["address_id"], emp=u["user_id"])
fam_users = rng.sample([u for u in users if u["status"] == "active" and u not in emp_users], 15)
family_of = {}
for u in fam_users:  # a family member living at the same address
    family_of[u["user_id"]] = add_patient(last=u["last_name"], addr=u["address_id"])

P = pd.DataFrame(patients)

# ---------------------------------------------------------------- encounters
encounters, care_team = [], []
eid = 1


def add_encounter(patient, dept=None):
    global eid
    dept = dept or rng.choices(CLINICAL, weights=[30, 12, 18, 15, 25])[0]
    start = START + timedelta(minutes=rng.randint(0, (DAYS - 2) * 24 * 60))
    if dept == "ED":
        etype, dur = "Emergency", timedelta(hours=rng.uniform(3, 12))
    elif dept in ("Oncology", "Cardiology") and rng.random() < 0.6:
        etype, dur = "Outpatient", timedelta(hours=rng.uniform(1, 3))
    else:
        etype, dur = "Inpatient", timedelta(days=rng.uniform(1, 6))
    end = min(start + dur, END)
    e = dict(encounter_id=f"E{eid:05d}", patient_id=patient["patient_id"], department=dept,
             encounter_type=etype, start_time=ts(start), end_time=ts(end), _s=start, _e=end)
    eid += 1
    encounters.append(e)
    staff = [u for u in by_dept[dept] if u["status"] == "active" or u["term_date"] > e["start_time"]]
    team = [rng.choice([u for u in staff if u["role"] == "Physician"])]
    team += rng.sample([u for u in staff if u["role"] == "Nurse"], rng.randint(2, 4))
    for m in team:
        care_team.append(dict(encounter_id=e["encounter_id"], user_id=m["user_id"]))
    return e, team


enc_patients = rng.sample(patients, 2300)
# two family-linked staff legitimately treat their relative (benign edge case)
for u in fam_users[:2]:
    enc_patients.append(family_of[u["user_id"]])

events = []


def log(user, patient_id, when, action=None, btg=0, scenario=None, context=""):
    events.append(dict(user_id=user["user_id"], patient_id=patient_id, access_time=ts(when),
                       action=action or rng.choices(
                           ["View Chart", "View Notes", "View Results", "Edit Order", "Print"],
                           weights=[45, 25, 20, 8, 2])[0],
                       break_the_glass=btg, is_anomaly=int(scenario is not None),
                       scenario=scenario or "normal", context=context))


def time_on_shift(user, lo, hi, tries=25):
    for _ in range(tries):
        t = lo + timedelta(seconds=rng.uniform(0, max((hi - lo).total_seconds(), 60)))
        if on_shift(t.hour, user["shift"]):
            return t
    return None


for p in enc_patients:
    e, team = add_encounter(p)
    if p in [family_of[u["user_id"]] for u in fam_users[:2]]:
        rel = next(u for u in fam_users[:2] if family_of[u["user_id"]] is p)
        care_team.append(dict(encounter_id=e["encounter_id"], user_id=rel["user_id"]))
        team.append(rel)
    s, en = e["_s"], e["_e"]
    reg = rng.choice(by_dept["Registration"])
    t = time_on_shift(reg, s - timedelta(hours=1), s + timedelta(hours=4))
    if t:
        log(reg, p["patient_id"], t)
    for m in team:
        for _ in range(rng.randint(2, 6)):
            t = time_on_shift(m, s, en)
            if t:
                log(m, p["patient_id"], t)
    for role_dept, n in (("Lab", rng.randint(1, 3)), ("Pharmacy", rng.randint(0, 2))):
        for _ in range(n):
            w = rng.choice(by_dept[role_dept])
            t = time_on_shift(w, s, en)
            if t:
                log(w, p["patient_id"], t)
    if rng.random() < 0.7:
        b = rng.choice(by_dept["Billing"])
        t = time_on_shift(b, en + timedelta(days=1), en + timedelta(days=9))
        if t and t < END:
            log(b, p["patient_id"], t)

# legitimate break-the-glass: covering ED/ICU staff on emergent patients
emergent = [e for e in encounters if e["department"] in ("ED", "ICU")]
for _ in range(60):
    e = rng.choice(emergent)
    u = rng.choice([x for x in by_dept[e["department"]] if x["role"] in ("Nurse", "Physician")])
    t = time_on_shift(u, e["_s"], e["_e"])
    if t:
        log(u, e["patient_id"], t, btg=1)

# benign noise: float nurses covering another unit without BTG (realistic false-positive bait)
for _ in range(40):
    e = rng.choice([x for x in encounters if x["encounter_type"] == "Inpatient"])
    u = rng.choice([x for x in by_dept["MedSurg"] if x["role"] == "Nurse"])
    t = time_on_shift(u, e["_s"], e["_e"])
    if t:
        log(u, e["patient_id"], t, context="Float coverage, assignment not recorded")

# ---------------------------------------------------------------- injected misuse (ground truth)
active = [u for u in users if u["status"] == "active"]
no_enc = [p for p in patients if p not in enc_patients and p["vip_flag"] == 0
          and p["employee_user_id"] is None and p not in family_of.values()]


def rand_time(user=None, after_hours=False):
    d = START + timedelta(days=rng.randint(0, DAYS - 1))
    if after_hours:
        return d + timedelta(hours=rng.uniform(1, 4.5))
    if user is not None:
        return time_on_shift(user, d, d + timedelta(days=1)) or d + timedelta(hours=12)
    return d + timedelta(hours=rng.uniform(0, 24))


vips = [p for p in patients if p["vip_flag"] == 1]
vip_actors = rng.sample([u for u in active if u["role"] in ("Nurse", "Registration", "Lab Tech")], 8)
for u in vip_actors:
    target = rng.choice(vips)
    for _ in range(rng.randint(1, 4)):
        log(u, target["patient_id"], rand_time(u), scenario="VIP snooping")

for u in rng.sample(fam_users[2:], 6):
    for _ in range(rng.randint(1, 3)):
        log(u, family_of[u["user_id"]]["patient_id"], rand_time(u), scenario="Family record snooping")

emp_patients = [p for p in patients if p["employee_user_id"]]
for u in rng.sample([x for x in active if x not in emp_users], 6):
    targets = [p for p in emp_patients
               if U.set_index("user_id").loc[p["employee_user_id"], "department"] != u["department"]]
    for p in rng.sample(targets, rng.randint(1, 3)):
        log(u, p["patient_id"], rand_time(u), scenario="Coworker snooping")

btg_actors = rng.sample([u for u in active if u["department"] in ("Oncology", "Cardiology", "Registration",
                                                                   "Billing", "Lab")], 6)
for u in btg_actors:
    for _ in range(rng.randint(1, 2)):
        log(u, rng.choice(no_enc)["patient_id"], rand_time(u), btg=1, scenario="Break-the-glass misuse")

for u in rng.sample([x for x in active if x["role"] in ("Registration", "Nurse")], 2):
    t0 = rand_time(u)
    for p in rng.sample(no_enc, rng.randint(50, 80)):
        t0 += timedelta(seconds=rng.randint(40, 180))
        log(u, p["patient_id"], t0, action="View Chart", scenario="Bulk record browsing")

for u in rng.sample([x for x in users if x["status"] == "terminated"], 2):
    td = datetime.strptime(u["term_date"], "%Y-%m-%d %H:%M:%S")
    for _ in range(rng.randint(5, 15)):
        t = td + timedelta(days=rng.uniform(0.5, (END - td).days - 0.5))
        log(u, rng.choice(patients)["patient_id"], t, scenario="Access after termination")

for u in rng.sample([x for x in active if x["shift"] in ("day", "office") and x not in vip_actors], 4):
    for _ in range(rng.randint(2, 5)):
        log(u, rng.choice(no_enc)["patient_id"], rand_time(after_hours=True), scenario="After-hours access")


# ---------------------------------------------------------------- realism: benign activity that trips rules
enc_by_patient = {}
for e in encounters:
    enc_by_patient.setdefault(e["patient_id"], []).append(e)
pmap = {p["patient_id"]: p for p in patients}
team_of = {}
for c in care_team:
    team_of.setdefault(c["encounter_id"], set()).add(c["user_id"])

# B1 specialist consults on VIP / staff patients without being on the care team
consult_orders, work_queue, extra_shifts = [], [], []
consult_targets = [e for e in encounters if (pmap[e["patient_id"]]["vip_flag"] == 1
                   or pmap[e["patient_id"]]["employee_user_id"]) and e["encounter_type"] == "Inpatient"]
for e in rng.sample(consult_targets, min(6, len(consult_targets))):
    doc = rng.choice([u for u in users if u["role"] == "Physician" and u["department"] != e["department"]
                      and u["shift"] == "day" and u["status"] == "active"])
    t = time_on_shift(doc, e["_s"], e["_e"])
    if t:
        consult_orders.append(dict(patient_id=e["patient_id"], encounter_id=e["encounter_id"],
                                   consultant_user_id=doc["user_id"], order_time=ts(t - timedelta(hours=2))))
        log(doc, e["patient_id"], t, action="View Notes", context="Specialist consult, not on care team")

# B2 retrospective quality audit: one billing analyst reviews 25 older charts in a day
old = [e for e in encounters if e["_e"] < START + timedelta(days=9)]
auditor = rng.choice(by_dept["Billing"])
t0 = START + timedelta(days=27, hours=9)
for e in rng.sample(old, 25):
    t0 += timedelta(minutes=rng.randint(6, 14))
    work_queue.append(dict(user_id=auditor["user_id"], patient_id=e["patient_id"], queue="Quality audit",
                           valid_from=ts(START + timedelta(days=27)), valid_to=ts(START + timedelta(days=29))))
    log(auditor, e["patient_id"], t0, action="View Chart", context="Approved retrospective quality audit")

# B3 day-shift MedSurg nurses picking up an evening shift on another unit
for _ in range(10):
    e = rng.choice([x for x in encounters if x["department"] == "ICU" and x["encounter_type"] == "Inpatient"
                    and (x["_e"] - x["_s"]) > timedelta(days=1)])
    u = rng.choice([x for x in by_dept["MedSurg"] if x["role"] == "Nurse" and x["shift"] == "day"
                    and x["status"] == "active"])
    d = e["_s"] + timedelta(hours=24)
    t = d.replace(hour=rng.randint(20, 22), minute=rng.randint(0, 59))
    if e["_s"] < t < e["_e"]:
        extra_shifts.append(dict(user_id=u["user_id"], unit="ICU", shift_start=ts(t.replace(hour=19, minute=0)),
                                 shift_end=ts(t.replace(hour=23, minute=59))))
        log(u, e["patient_id"], t, context="Picked up an extra evening shift on another unit")

# B4 billing staff reworking denied claims late in the evening
for _ in range(8):
    e = rng.choice(old)
    b = rng.choice(by_dept["Billing"])
    t = (START + timedelta(days=rng.randint(24, 29))).replace(hour=20, minute=rng.randint(30, 59))
    work_queue.append(dict(user_id=b["user_id"], patient_id=e["patient_id"], queue="Claim denials",
                           valid_from=ts(t - timedelta(days=3)), valid_to=ts(t + timedelta(days=3))))
    log(b, e["patient_id"], t, context="Claim denial rework after hours")

# ---------------------------------------------------------------- realism: subtle misuse that evades simple rules
# H1 low-and-slow browsing: 1-2 unrelated charts a day, during shift, never VIP
slow = rng.choice([u for u in active if u["role"] == "Nurse" and u["shift"] == "day"
                   and u not in vip_actors])
for day in rng.sample(range(DAYS), 12):
    for _ in range(rng.randint(1, 2)):
        d = START + timedelta(days=day)
        log(slow, rng.choice(no_enc)["patient_id"], d + timedelta(hours=rng.uniform(9, 17)),
            scenario="Low-and-slow browsing")

# H2 care-team member repeatedly opening a VIP chart far beyond care needs
vip_encs = [e for e in encounters if pmap[e["patient_id"]]["vip_flag"] == 1 and e["encounter_type"] == "Inpatient"]
e = rng.choice(vip_encs)
nurse = next(u for u in users if u["user_id"] in team_of[e["encounter_id"]] and u["role"] == "Nurse")
for _ in range(8):
    t = time_on_shift(nurse, e["_s"], e["_e"])
    if t:
        log(nurse, e["patient_id"], t, action="View Notes", scenario="Excessive access by care-team member")

# H3 ED nurse uses break-the-glass on a coworker's active ED visit out of curiosity
cw = rng.choice([p for p in patients if p["employee_user_id"]])
e, _ = add_encounter(cw, "ED")
ed_nurse = rng.choice([u for u in by_dept["ED"] if u["role"] == "Nurse" and u["status"] == "active"
                       and u["user_id"] not in team_of.get(e["encounter_id"], set())
                       and u["user_id"] != cw["employee_user_id"]])
for _ in range(2):
    t = time_on_shift(ed_nurse, e["_s"], e["_e"])
    if t:
        log(ed_nurse, cw["patient_id"], t, btg=1, scenario="Curiosity break-the-glass on coworker")

# ---------------------------------------------------------------- write
A = pd.DataFrame(events)
A = A[A.access_time < ts(END)]
term = U.set_index("user_id")["term_date"]
# legitimate activity never comes from a closed account
A = A[~((A.scenario == "normal") & A.user_id.map(term).notna() & (A.access_time > A.user_id.map(term)))]
A = A.sort_values("access_time").reset_index(drop=True)
A.insert(0, "event_id", [f"EV{i:06d}" for i in range(1, len(A) + 1)])

E = pd.DataFrame(encounters)
pd.DataFrame(consult_orders).to_csv(OUT / "consult_orders.csv", index=False)
pd.DataFrame(work_queue).to_csv(OUT / "work_queue.csv", index=False)
pd.DataFrame(extra_shifts).drop_duplicates().to_csv(OUT / "extra_shifts.csv", index=False)
U.to_csv(OUT / "users.csv", index=False)
P.to_csv(OUT / "patients.csv", index=False)
E.drop(columns=["_s", "_e"]).to_csv(OUT / "encounters.csv", index=False)
pd.DataFrame(care_team).drop_duplicates().to_csv(OUT / "care_team.csv", index=False)
A.to_csv(OUT / "access_log.csv", index=False)

print(f"users={len(U)} patients={len(P)} encounters={len(E)} events={len(A)} "
      f"anomalous_events={A.is_anomaly.sum()} anomalous_users={A[A.is_anomaly == 1].user_id.nunique()}")
print(A[A.is_anomaly == 1].scenario.value_counts().to_string())
