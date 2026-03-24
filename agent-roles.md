# Overwatch Agent Roles
**Created:** 2026-03-18 bootstrap session
**Authority:** Jim Haist

---

## Role: PLANNER
**One instance only. Runs when Jim provides strategic intent.**

Responsibilities:
- Reads current Plane backlog
- Reads AGENT-STATE.md from all three repos
- Reads latest compliance check output (JSON, not text — use `jq` on nist-compliance-latest.json)
- **Reads check-strength.yaml** before creating any compliance-related issue
- Breaks intent into Plane issues with explicit acceptance criteria
- Each issue MUST have: title, description, acceptance_criteria (machine-verifiable),
  blocked_by (list), modifies_files (list of exact paths)
- **If the only automated check for a control is weak/trivial** (per check-strength.yaml),
  the acceptance criteria must explicitly say so: "NOTE: automated check for {control} is
  {weak|trivial} — acceptance requires manual verification or check improvement first"
- Does NOT modify infrastructure
- Does NOT modify compliance documents
- Writes session output to ~/overwatch/PLANNER-STATE.md

### Anti-Theater Constraint
The PLANNER must not create issues that claim compliance improvements for controls
where the only check is trivially true (e.g., AC-3 checking ClusterRole count, SI-4
checking default Wazuh rule count). If a control needs real compliance work, the issue
must FIRST improve the check, THEN fix the control. Two issues, in order.

---

## Role: WORKER
**One instance per Plane issue. Scoped strictly to that issue.**

Responsibilities:
- Reads assigned Plane issue
- Creates branch: `worker/issue-{ID}-{short-title}`
- Works ONLY on files listed in `modifies_files`
- **If a file is not in modifies_files and needs to change, STOPS and creates a child issue**
- Writes AGENT-STATE.md at session end (see template)
- Opens GitLab MR when work is complete
- Posts MR link as Plane issue comment with "ready for Judge"
- Does NOT close the Plane issue (Judge closes it)
- Does NOT update compliance documents (COMPLIANCE-SCRIBE role only)
- Does NOT modify nist-compliance-check.sh (read-only for all agents)

---

## Role: JUDGE
**Automated. Runs after every MR merge via post-merge hook.**

Responsibilities:
- Runs nist-compliance-check.sh (or reads JSON output from latest cron run)
- Compares result to result at MR open time (stored in MR description)
- Posts result as Plane issue comment
- If acceptance_criteria from the issue are met: closes issue, labels "verified-complete"
- If not met: reopens issue, labels "failed-verification", posts what failed
- Does NOT suggest fixes. Reports state only.
- Parses JSON output via jq, NOT grep on text (grep double-counts multi-match lines)

### Judge Counting Rule
```bash
# CORRECT — parse JSON
jq '[.checks[] | select(.status=="PASS")] | length' nist-compliance-latest.json
# WRONG — grep counts lines, not statuses
grep -c "PASS" output.txt  # DO NOT USE
```

---

## Role: COMPLIANCE-SCRIBE
**One instance only. Only role that writes to SSP/SAR/gap-analysis.**

Responsibilities:
- Runs ONLY after Judge has verified an issue complete
- Updates exactly the controls affected by the verified work
- Branch: `scribe/post-issue-{ID}`
- Commit message must reference the issue ID and Judge verification timestamp
- Cannot mark a control "implemented" if compliance check for that control
  shows FAIL or WARN
- Cannot mark a control "implemented" if the check doesn't test that control
  (must use "partial" or "attested-only" status instead)

### Scribe vs Reconciliation Agent
- **SCRIBE** handles issue-specific artifact updates: "issue X fixed AC-2, update AC-2's SSP entry"
- **Reconciliation agent** (runs daily after compliance cron) handles bulk sync:
  current-state.md, score-history.md, kill zombie metrics, catch regressions
- **SCRIBE defers** to reconciliation agent for current-state.md and score-history.md
  (single-writer rule for those files)

---

## ARTIFACT OWNERSHIP (hard rules, enforced in CLAUDE.md)

| Artifact | Owner | All Others |
|----------|-------|-----------|
| SSP files (system-security-plan.json, sentinel-ssp/*.md) | COMPLIANCE-SCRIBE only | READ-ONLY |
| gap-analysis.md | COMPLIANCE-SCRIBE only | READ-ONLY |
| SAR, POAM documents | COMPLIANCE-SCRIBE only | READ-ONLY |
| nist-compliance-check.sh | **NO AGENT** — Jim only | READ-ONLY |
| check-strength.yaml | **NO AGENT** — Jim only | READ-ONLY |
| CLAUDE.md (any repo) | **NO AGENT** — Jim approval required | READ-ONLY |
| current-state.md, score-history.md | Reconciliation agent only | READ-ONLY |
| AGENT-STATE.md | The agent holding that session | Others READ-ONLY |

---

## VERIFIED PLATFORM STATE (from bootstrap 2026-03-18)

| Item | Value | Source |
|------|-------|--------|
| Repos | All 3 on GitLab (${GITLAB_IP}), NOT Forgejo | `git remote -v` |
| CLAUDE.md | Exists in all 3 repos | `ls` verified |
| Plane API | Alive at plane.${INTERNAL_DOMAIN} (401 without key) | `curl` verified |
| Plane projects | OPS, SEC, COMP, HAIST | API verified |
| Plane workspace | ${WORKSPACE_SLUG} | API verified |
| Plane API key | In Vault at `secret/plane/api-key` | Vault read verified |
| Compliance (cached) | 120/125 PASS, 0 FAIL, 5 WARN (96%) as of 2026-03-15 | JSON parsed |
| Compliance script | ~/sentinel-iac/scripts/nist-compliance-check.sh (runs on iac-control, not workstation) | ls verified |
| Vault CLI | NOT on workstation — use curl to Vault API via Pangolin | `which vault` verified |
