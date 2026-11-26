"""
Ground truth, labelled by hand.

src/hunt.py pulls every event that *might* belong to one of the five behaviours, using
loose keyword searches. Each candidate is then labelled here (case-insensitive text match), by a person reading the
command line, before any scoring happens. Every candidate must match exactly one label
rule, or the script stops, so nothing is scored without being looked at.

Labels
  in_scope     a real attack action the rule family is meant to catch
  duplicate    the same action seen twice (cmd.exe /c wrapper, or net.exe -> net1.exe);
               not counted as a separate action, and a hit on it is not a false positive
  out_of_scope real activity, but a different technique or a benign command

The unit of scoring is one unique action: (log file, exact command line).
Usage: python src/label.py
Output: labels/ground_truth.csv
"""
import pathlib, sys
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETS = {"dev": ROOT / "results" / "dev", "heldout": ROOT / "results" / "heldout"}

# (dataset, family, file contains, command line contains, label, reason)
# family: D1 PowerShell, D2 account, D3 scheduled task, D4 recovery, D5 Defender
RULES = [
    # ---------- dev set: EVTX-ATTACK-SAMPLES ----------
    ("dev", "D1", "appcmd", " -enc ", "in_scope", "PowerShell with -EncodedCommand"),
    ("dev", "D1", "EDRTestingScript", "powershell  -c \"(New-Object Net.WebClient).DownloadFile", "in_scope", "download cradle"),
    ("dev", "D1", "EDRTestingScript", "powershell  -c \"Start-BitsTransfer", "in_scope", "payload download with BITS"),
    ("dev", "D1", "EDRTestingScript", "cmd  /c powershell", "duplicate", "cmd.exe wrapper of the PowerShell line"),
    ("dev", "D1", "susp_explorer_exec", "wscript.exe\" /E:vbs", "in_scope", "VBScript launching PowerShell IEX from Base64"),
    ("dev", "D1", "zipfldr_routethecall", "wscript.exe\" /E:vbs", "in_scope", "VBScript launching PowerShell IEX from Base64"),
    ("dev", "D1", "psexec_smb_meterpreter", "powershell.exe  -nop -w hidden", "in_scope", "Meterpreter stager, hidden window"),
    ("dev", "D1", "psexec_smb_meterpreter", "-w hidden -c &([scriptblock]", "in_scope", "Meterpreter stage, Gzip + Base64 in memory"),
    ("dev", "D1", "psexec_smb_meterpreter", "cmd.exe /b /c start", "duplicate", "cmd.exe wrapper of the PowerShell line"),
    ("dev", "D1", "AtomicRedTeam01", "PromptForCredential", "out_of_scope", "fake credential prompt (T1056.002), not hidden or encoded"),
    ("dev", "D1", "", "start-process notepad", "out_of_scope", "plain PowerShell command"),
    ("dev", "D1", "seimpersonate", "PrintSpoofer.exe", "out_of_scope", "privilege escalation tool that opens a shell"),
    ("dev", "D1", "", "-s -NoLogo -NoProfile", "out_of_scope", "PowerShell remoting host process"),
    ("dev", "D1", "WScriptBypassUAC", "echo Dim objShell", "out_of_scope", "UAC bypass writing a VBScript"),
    ("dev", "D1", "", "@BARE_POWERSHELL", "out_of_scope", "interactive PowerShell with no arguments to judge"),
    ("dev", "D2", "", "net  use", "out_of_scope", "share connection"),
    ("dev", "D2", "", "net  view", "out_of_scope", "discovery"),
    ("dev", "D2", "", "start CDPSvc", "out_of_scope", "service start"),
    ("dev", "D2", "LM_typical_IIS_webshell", "net", "out_of_scope", "user enumeration, no /add"),
    ("dev", "D3", "", "@CMD_WRAPPER", "duplicate", "cmd.exe wrapper of the schtasks line"),
    ("dev", "D3", "", "/create", "in_scope", "scheduled task created"),
    ("dev", "D3", "", "at  13:20", "in_scope", "task scheduled with the legacy at.exe"),
    ("dev", "D3", "", "/run ", "out_of_scope", "runs an existing task; creation is the persistence step"),
    ("dev", "D3", "", "/delete ", "out_of_scope", "deletes a task"),
    ("dev", "D3", "", "schtasks /run", "out_of_scope", "runs an existing task"),
    ("dev", "D4", "", "vssadmin.exe  delete shadows", "in_scope", "shadow copies deleted"),
    ("dev", "D4", "", "wbadmin.exe  delete catalog", "in_scope", "backup catalog deleted"),
    ("dev", "D4", "", "bootstatuspolicy ignoreallfailures", "in_scope", "boot-failure recovery turned off"),
    ("dev", "D4", "", "recoveryenabled no", "in_scope", "Windows recovery turned off"),
    ("dev", "D4", "", "/c \"vssadmin.exe delete", "duplicate", "cmd.exe wrapper of the vssadmin line"),
    ("dev", "D4", "", "create shadow", "out_of_scope", "shadow copy created to steal NTDS.dit (T1003.003)"),
    ("dev", "D4", "", "copy \\\\?\\GLOBALROOT", "out_of_scope", "file copied out of a shadow copy"),
    ("dev", "D4", "sysmon_exec_from_vss_persistence", "", "out_of_scope", "runs malware from a shadow copy (defense evasion)"),
    ("dev", "D4", "vshadow", "", "out_of_scope", "vshadow used to launch a program (LOLBin)"),
    # ---------- held-out set: EVTX-to-MITRE-Attack ----------
    ("heldout", "D1", "", "powershell.exe  -nop -w hidden", "in_scope", "Meterpreter stager, hidden window"),
    ("heldout", "D1", "", "-w hidden -c &([scriptblock]", "in_scope", "Meterpreter stage, Gzip + Base64 in memory"),
    ("heldout", "D1", "", "cmd.exe /b /c start", "duplicate", "cmd.exe wrapper of the PowerShell line"),
    ("heldout", "D1", "WMImplant", "Get-C`ommand", "in_scope", "obfuscated Invoke-Expression"),
    ("heldout", "D1", "CrackMap", "powershell.exe  -exec bypass -noni -nop -w 1", "in_scope", "CrackMapExec, hidden window (-w 1), obfuscated"),
    ("heldout", "D1", "CrackMap", "cmd.exe /Q /c powershell", "duplicate", "cmd.exe wrapper of the PowerShell line"),
    ("heldout", "D1", "Tchopper", "", "out_of_scope", "payload rebuilt from service names; PowerShell itself is plain"),
    ("heldout", "D1", "Mini_Plasma", "sysmon_controller.ps1", "out_of_scope", "admin script from a software share (benign)"),
    ("heldout", "D1", "LSASSY", "MiniDump", "out_of_scope", "LSASS memory dump (T1003.001)"),
    ("heldout", "D1", "Clear event log", "", "out_of_scope", "event log cleared (T1070.001)"),
    ("heldout", "D1", "Defender critical features", "Set-MpPreference", "out_of_scope", "Defender change, scored under D5"),
    ("heldout", "D5", "Defender critical features", "Set-MpPreference", "in_scope", "Defender protection turned off"),
    ("heldout", "D5", "Defender critical features", "install-manifest", "out_of_scope", "event manifest install"),
    ("heldout", "D5", "Defender service deactivation", "WinDefend start= disabled", "in_scope", "Defender service disabled"),
    ("heldout", "D2", "User creation", "net  user toto3", "in_scope", "local account created"),
    ("heldout", "D2", "User creation", "net1  user toto3", "duplicate", "net.exe starts net1.exe for the same action"),
    ("heldout", "D2", "", "net", "out_of_scope", "discovery, share or service command, no account created"),
    ("heldout", "D3", "", "/create", "in_scope", "scheduled task created"),
    ("heldout", "D3", "", "at  13:20", "in_scope", "task scheduled with the legacy at.exe"),
    ("heldout", "D3", "", "/query", "out_of_scope", "task discovery"),
    ("heldout", "D4", "", "shadowcopy delete", "in_scope", "shadow copies deleted with WMIC"),
    ("heldout", "D4", "", "wbadmin  delete backup", "in_scope", "backups deleted"),
    ("heldout", "D4", "", "diskshadow.exe  /s", "out_of_scope", "diskshadow script; its contents are not in the log, so intent cannot be judged"),
]
FAMILY = {"T1059.001": "D1", "T1136.001": "D2", "T1053.005": "D3", "T1490 ": "D4", "T1562.001": "D5"}


def family_of(tech):
    return next(v for k, v in FAMILY.items() if tech.startswith(k.strip()))


def match(rule, row):
    ds, fam, f_sub, c_sub = rule[:4]
    if ds != row.dataset or fam != row.family or f_sub not in row.evtx_file:
        return False
    cmd = str(row.CommandLine)
    if c_sub == "@BARE_POWERSHELL":
        return row.image_name == "powershell.exe" and ("-" not in cmd.split("powershell", 1)[-1].lower().replace(".exe", "").strip(' "'))
    if c_sub == "@CMD_WRAPPER":
        return row.image_name == "cmd.exe" and "/create" in cmd.lower()
    return c_sub.lower() in cmd.lower()


frames = []
for ds, out in SETS.items():
    c = pd.read_csv(out / "hunt_candidates.csv")
    c["dataset"] = ds
    c["family"] = c.technique.map(family_of)
    frames.append(c)
cand = pd.concat(frames, ignore_index=True)

labels, unmatched = [], []
for _, row in cand.iterrows():
    # wrapper/duplicate rules are tried first: a wrapper's command line contains its child's
    hit = next((r for r in sorted(RULES, key=lambda r: r[4] != "duplicate") if match(r, row)), None)
    if hit is None:
        unmatched.append(row)
        continue
    labels.append(dict(dataset=row.dataset, family=row.family, evtx_file=row.evtx_file,
                       image_name=row.image_name, CommandLine=row.CommandLine, label=hit[4], reason=hit[5]))
if unmatched:
    for r in unmatched:
        print("UNLABELLED:", r.dataset, r.family, r.evtx_file, r.image_name, str(r.CommandLine)[:120], file=sys.stderr)
    sys.exit(1)

lab = pd.DataFrame(labels).drop_duplicates(["dataset", "family", "evtx_file", "CommandLine"])
(ROOT / "labels").mkdir(exist_ok=True)
lab.to_csv(ROOT / "labels" / "ground_truth.csv", index=False)
print(lab.groupby(["dataset", "family", "label"]).size().unstack(fill_value=0))
