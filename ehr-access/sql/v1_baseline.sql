-- EHR Access Monitoring v1 (baseline): detection rules (SQLite)
-- Rules read only users, patients, encounters, care_team and the raw audit
-- fields of access_log. Ground-truth columns are never used here.

-- 1. Does each access have a legitimate care or business relationship?
DROP TABLE IF EXISTS access_context;
CREATE TABLE access_context AS
SELECT
  a.event_id, a.user_id, a.patient_id, a.access_time, a.action, a.break_the_glass,
  u.role, u.department, u.shift, u.status, u.term_date,
  u.last_name AS user_last_name, u.address_id AS user_address,
  p.last_name AS patient_last_name, p.address_id AS patient_address,
  p.vip_flag, p.employee_user_id,
  CAST(strftime('%H', a.access_time) AS INTEGER) AS hour,
  CASE WHEN
    -- on the care team, from 12h before admission to 48h after discharge
    EXISTS (SELECT 1 FROM care_team ct JOIN encounters e ON e.encounter_id = ct.encounter_id
            WHERE ct.user_id = a.user_id AND e.patient_id = a.patient_id
              AND a.access_time BETWEEN datetime(e.start_time, '-12 hours')
                                    AND datetime(e.end_time, '+48 hours'))
    -- lab and pharmacy: any patient with an active encounter
    OR (u.role IN ('Lab Tech', 'Pharmacist') AND EXISTS (
            SELECT 1 FROM encounters e WHERE e.patient_id = a.patient_id
              AND a.access_time BETWEEN e.start_time AND datetime(e.end_time, '+12 hours')))
    -- registration: around the start of an encounter
    OR (u.role = 'Registration' AND EXISTS (
            SELECT 1 FROM encounters e WHERE e.patient_id = a.patient_id
              AND a.access_time BETWEEN datetime(e.start_time, '-6 hours')
                                    AND datetime(e.start_time, '+12 hours')))
    -- billing: within 14 days after discharge
    OR (u.role = 'Billing' AND EXISTS (
            SELECT 1 FROM encounters e WHERE e.patient_id = a.patient_id
              AND a.access_time BETWEEN e.end_time AND datetime(e.end_time, '+14 days')))
    -- break-the-glass by ED/ICU staff on an active emergent encounter in their own unit
    OR (a.break_the_glass = 1 AND EXISTS (
            SELECT 1 FROM encounters e WHERE e.patient_id = a.patient_id
              AND e.department = u.department AND e.department IN ('ED', 'ICU')
              AND a.access_time BETWEEN e.start_time AND e.end_time))
  THEN 1 ELSE 0 END AS has_relationship
FROM access_log a
JOIN users u ON u.user_id = a.user_id
JOIN patients p ON p.patient_id = a.patient_id;

-- 2. Rule hits (one row per event per rule)
DROP TABLE IF EXISTS rule_hits;
CREATE TABLE rule_hits (event_id TEXT, user_id TEXT, rule_id TEXT);

-- R1 VIP record accessed with no relationship
INSERT INTO rule_hits SELECT event_id, user_id, 'R1' FROM access_context
WHERE vip_flag = 1 AND has_relationship = 0;

-- R2 Family record: same last name and home address, no relationship
INSERT INTO rule_hits SELECT event_id, user_id, 'R2' FROM access_context
WHERE user_last_name = patient_last_name AND user_address = patient_address
  AND (employee_user_id IS NULL OR employee_user_id <> user_id)
  AND has_relationship = 0;

-- R3 Coworker record: patient is another employee, no relationship
INSERT INTO rule_hits SELECT event_id, user_id, 'R3' FROM access_context
WHERE employee_user_id IS NOT NULL AND employee_user_id <> user_id
  AND has_relationship = 0;

-- R4 Break-the-glass with no emergent justification
INSERT INTO rule_hits SELECT event_id, user_id, 'R4' FROM access_context
WHERE break_the_glass = 1 AND has_relationship = 0;

-- R5 Volume: 15+ distinct unrelated patients by one user in one calendar day
INSERT INTO rule_hits
SELECT c.event_id, c.user_id, 'R5' FROM access_context c
JOIN (SELECT user_id, date(access_time) AS d FROM access_context
      WHERE has_relationship = 0
      GROUP BY user_id, date(access_time)
      HAVING COUNT(DISTINCT patient_id) >= 15) v
  ON v.user_id = c.user_id AND v.d = date(c.access_time)
WHERE c.has_relationship = 0;

-- R6 Account used after termination date
INSERT INTO rule_hits SELECT event_id, user_id, 'R6' FROM access_context
WHERE status = 'terminated' AND access_time > term_date;

-- R7 Off-shift access to an unrelated record
INSERT INTO rule_hits SELECT event_id, user_id, 'R7' FROM access_context
WHERE has_relationship = 0 AND (
  (shift = 'day'    AND (hour < 7 OR hour >= 19)) OR
  (shift = 'night'  AND hour >= 7 AND hour < 19)  OR
  (shift = 'office' AND (hour < 6 OR hour >= 20)));

-- 3. User risk score: rule weight once per rule triggered + 2 points per flagged event (capped at 20 events)
DROP TABLE IF EXISTS rule_weights;
CREATE TABLE rule_weights (rule_id TEXT, weight INTEGER, name TEXT);
INSERT INTO rule_weights VALUES
 ('R1', 30, 'VIP record, no relationship'),
 ('R2', 35, 'Family record, no relationship'),
 ('R3', 25, 'Coworker record, no relationship'),
 ('R4', 30, 'Break-the-glass without justification'),
 ('R5', 40, 'High volume of unrelated records'),
 ('R6', 50, 'Account used after termination'),
 ('R7', 10, 'Off-shift unrelated access');

DROP VIEW IF EXISTS user_risk;
CREATE VIEW user_risk AS
WITH per_rule AS (SELECT DISTINCT user_id, rule_id FROM rule_hits),
     ev AS (SELECT user_id, COUNT(DISTINCT event_id) AS flagged_events FROM rule_hits GROUP BY user_id)
SELECT u.user_id, u.role, u.department,
       GROUP_CONCAT(pr.rule_id, ', ') AS rules,
       ev.flagged_events,
       SUM(w.weight) + 2 * MIN(ev.flagged_events, 20) AS risk_score
FROM per_rule pr
JOIN rule_weights w ON w.rule_id = pr.rule_id
JOIN ev ON ev.user_id = pr.user_id
JOIN users u ON u.user_id = pr.user_id
GROUP BY u.user_id
ORDER BY risk_score DESC;
