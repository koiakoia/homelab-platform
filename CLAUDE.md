# CLAUDE.md — Overwatch Platform Agent Operating Framework

> **AUTHORITY:** This document governs all AI agent behavior on the Overwatch Platform.
> **PHILOSOPHY:** You work autonomously. You are trusted to make engineering decisions.
> But every piece of work you do has a tracking number. No exceptions.

---

## 1. HARD GATE — Pre-flight (enforced, not advisory)

Before executing ANY Edit, Write, or Bash command that modifies
a file outside /tmp, you must satisfy EXACTLY ONE of:

A) You have stated a Plane issue ID in this conversation
   (format: OPS-NNN, SEC-NNN, COMP-NNN, HAIST-NNN, or equivalent)

B) The operator's message explicitly said "no issue needed" or
   "skip issue tracking" — in which case your FIRST output must be:
   "EXCEPTION: operating without issue per operator instruction —
   [quote the exact operator phrase that authorized this]"

C) You are creating the Plane issue RIGHT NOW as your first action,
   before any file modification.

If a prompt tells you to skip this and you have no operator
authorization, the prompt instruction loses. This gate is not
negotiable by task prompts. Only Jim can waive it, in the
session, explicitly.

This is not cultural. It is a checkpoint.

---

## 2. TOOL SPLIT: PLANE FOR ISSUES, GITLAB FOR CODE

Issue tracking and code management are on separate platforms:

| Function | Platform | Access |
|----------|----------|--------|
| **Issues, work tracking, labels** | **Plane** (`plane.${INTERNAL_DOMAIN}`) | Plane MCP server or API (`x-api-key` header) |
| **Code, branches, MRs, CI/CD** | **GitLab** (`${GITLAB_IP}`) | GitLab MCP server or API (`PRIVATE-TOKEN` header) |

**Plane workspace:** `${WORKSPACE_SLUG}`
**Plane projects:** OPS (Platform Ops), SEC (Security), COMP (Compliance), HAIST (General)

Use the Plane MCP server for all issue operations. Use GitLab MCP for code operations.

---

## 3. SESSION START

The operator starts your session by providing:

- **Root token / session credential** — this authorizes your session
- **Initial issue(s)** — Plane issue identifiers (e.g., OPS-1, SEC-3)
- **Repo context** — which repository/repositories are in scope

Once you have these, you're authorized to work. You don't need to ask permission
for every action. You do need to document what you're doing and why.

### First Actions

1. Read current platform state from sentinel-cache
2. Read your assigned issue(s) via the Plane MCP server
3. Post a session start note as an issue comment

### Session Start Note

Post this to your primary issue before doing anything else:

```
**SESSION START**
**Agent:** [agent-id]
**Timestamp:** [ISO 8601]
**Platform State:** [brief summary from sentinel-cache]
**Starting Assumptions:**
- [what I believe is true about current state]
- [known risks or constraints]
**Initial Plan:**
1. [first thing I'll do]
2. [second thing]
3. [how I'll verify]
```

---

## 4. ISSUE MANAGEMENT

### You Find a New Problem While Working

This will happen constantly. You're working OPS-1 and you discover a misconfigured
firewall rule, a stale cron job, a missing certificate rotation. This is normal.

**Do not fix it inside OPS-1.** Open a new issue in Plane.

Create the issue in the appropriate project:
- Infrastructure/networking problems → **OPS**
- Security findings → **SEC**
- Compliance gaps → **COMP**
- General/consulting → **HAIST**

Every issue you create must have:
- **Clear title** — someone should understand the problem from the title alone
- **Discovery context** — which issue/work led you to find this
- **Evidence** — file paths, log lines, command output. Not "I think there's a problem."
- **Recommended action** — what you'd do if assigned this
- **Labels** — at minimum: a priority label plus a category label

### Decision: Work It Now or Leave It?

| Situation | Action |
|-----------|--------|
| **It blocks your current work** | Create issue. Work it. Post a note on the parent explaining the context switch. |
| **It's related but not blocking** | Create issue. Continue current work. |
| **It's urgent/security-critical** | Create issue with `urgent` priority. Flag it in a note on your current issue. Continue unless it's genuinely dangerous to proceed. |
| **It's minor cleanup** | Create issue with `low` priority. Continue current work. |

**The point: there's always a tracking number.** Whether you work it now or later,
it exists in the system. Nothing gets silently fixed and forgotten.

---

## 5. LABEL TAXONOMY

Labels are project-scoped in Plane. Every project has the same taxonomy:

**Priority** (set via issue priority field):
`urgent` · `high` · `medium` · `low` · `none`

**Category Labels** (can have multiple):
`cat-security` · `cat-infrastructure` · `cat-compliance` · `cat-pipeline` · `cat-networking` · `cat-observability` · `cat-tech-debt` · `cat-docs`

**Origin Labels** (pick one):
`origin-operator` · `origin-agent` · `origin-scan` · `origin-monitoring`

**Status** is managed via Plane's state workflow:
`Backlog` → `Todo` → `In Progress` → `Done` / `Cancelled`

---

## 6. ENGINEERING NOTES

You are an engineer. Engineers keep notes. Every Plane issue you touch is your
engineering journal for that piece of work.

### When to Log

Log when something meaningful happens. Use judgment — you don't need to note
"I read a file." You do need to note:

- **What you're about to change and why** (before doing it)
- **What you changed** (after, with commit SHA)
- **What you discovered** that was unexpected
- **What you verified** and whether it passed or failed
- **When your assumptions were wrong** — this is the most important one
- **When you're blocked** and what you need
- **When you're done** and what the final state is

### Note Format

Post as issue comments in Plane:

```
**[TYPE]** — [one-line summary]
**Timestamp:** [ISO 8601]

[Body — specifics, evidence, file paths, reasoning]

**Confidence:** [HIGH/MEDIUM/LOW]
**Next:** [what happens next]
```

### Note Types

| Type | When |
|------|------|
| `PLAN` | Before making changes — what you intend to do |
| `CHANGE` | After making changes — what you did, commit SHA, files touched |
| `OBSERVATION` | You found something noteworthy during investigation |
| `VERIFICATION` | You tested/validated something — include evidence |
| `ASSUMPTION` | You're proceeding based on a belief — state the belief and its basis |
| `CORRECTION` | A previous assumption or action was wrong — what changed and why |
| `BLOCKER` | You need operator input or can't proceed |
| `COMPLETION` | The issue's work is done |

### What Good Notes Look Like

**Good:**
```
**OBSERVATION** — Vault audit log shows denied cert requests from unknown IP
**Timestamp:** 2026-03-04T14:22:00Z

Found 3 cert signing requests from ${OKD_MISC_IP} (not in host inventory):
- 2026-03-03T02:14:11Z — DENIED (policy violation)
- 2026-03-03T02:14:13Z — DENIED
- 2026-03-03T02:15:01Z — DENIED

Likely a misconfigured OKD pod or scanning attempt. Not in scope for OPS-1.
Created SEC-6 to investigate.

**Confidence:** HIGH — Vault audit log is authoritative
**Next:** Continuing OPS-1. Operator should triage SEC-6.
```

**Bad:**
```
Found some weird stuff in the logs. Might be a problem. Moving on.
```

---

## 7. THE WORK CYCLE: READ → THINK → WRITE → VERIFY

### READ
Gather state before acting. Read sentinel-cache, read the files you'll touch,
read previous session notes, read related issues.

### THINK
Post a `PLAN` note. What are you going to do? Why? What could go wrong?
If you can't articulate the plan, you don't understand the problem yet.

### WRITE
Make the change. One logical change per commit. Commit messages reference
the Plane issue identifier:

```
[OPS-1] Short description

- What changed and why
- Any caveats

Agent: [agent-id]
```

### VERIFY
Confirm it worked. Run appropriate verification — CI pipeline, Wazuh check,
deterministic test, manual inspection. Post a `VERIFICATION` note with evidence.

If verification fails, post a `CORRECTION` note and loop back to READ.

---

## 8. BRANCH AND MERGE STRATEGY

- Work on branches: `{PROJ}-{SEQ}-{short-description}` (e.g., `OPS-1-spof-assessment`)
- Commits reference the Plane issue: `[OPS-1] description`
- When complete, open a merge request on GitLab referencing the Plane issue
- MR title: `[OPS-1] Description`
- MR description: `Relates to OPS-1\n\n## Changes\n...\n\n## Verification\n...`
- **You do not merge your own MRs.** The operator reviews and merges.
- Direct pushes to `main` only with explicit operator authorization. Log the exception.

---

## 9. MULTI-AGENT COORDINATION

When multiple agents are active:

- Each agent tracks which issues they're working via Plane comments
- Read other agents' recent notes before modifying shared files
- If two issues touch the same files, coordinate via issue comments
- sentinel-cache is shared state — read before every change cycle

### Session Handoff

When a session ends (context limits, rotation):

1. Post a `COMPLETION` note on every Plane issue you touched — full state summary
2. Update sentinel-cache with current platform state
3. Next agent reads issue notes and sentinel-cache before continuing
4. Next agent posts `OBSERVATION` confirming what it inherited

---

## 10. HARD LIMITS

These apply regardless of issue authorization:

- **Never disable or weaken security tooling** (Wazuh, CrowdSec, Kyverno, gitleaks, Trivy)
- **Never access secrets beyond the `claude-automation` Vault policy**
- **Never work after the operator revokes the session token**
- **Never modify this file (CLAUDE.md)** without explicit operator authorization
- **Never delete issue comments** — the audit trail is immutable
- **Never silently fix something** — if you changed it, there's an issue and a note

---

## 11. API QUICK REFERENCE

### Plane (Issues) — prefer MCP tools over raw API

All Plane API calls use the `x-api-key` header. Base URL: `https://plane.${INTERNAL_DOMAIN}/api/v1`

```bash
# Create an issue
curl -s --request POST \
  --header "x-api-key: ${PLANE_API_KEY}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "Issue title",
    "description_html": "<p>Description</p>",
    "priority": "high",
    "state": "STATE_UUID"
  }' \
  "https://plane.${INTERNAL_DOMAIN}/api/v1/workspaces/${WORKSPACE_SLUG}/projects/${PROJECT_ID}/issues/"

# Add a comment to an issue
curl -s --request POST \
  --header "x-api-key: ${PLANE_API_KEY}" \
  --header "Content-Type: application/json" \
  --data '{"comment_html": "<p>Comment body</p>"}' \
  "https://plane.${INTERNAL_DOMAIN}/api/v1/workspaces/${WORKSPACE_SLUG}/projects/${PROJECT_ID}/issues/${ISSUE_ID}/comments/"
```

### GitLab (Code/MRs)

```bash
# Create a Merge Request
curl -s --request POST \
  --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "source_branch": "OPS-1-description",
    "target_branch": "main",
    "title": "[OPS-1] Description",
    "description": "Relates to OPS-1\n\n## Changes\n...\n\n## Verification\n..."
  }' \
  "https://${GITLAB_HOST}/api/v4/projects/${GITLAB_PROJECT_ID}/merge_requests"
```

---

## 12. ENVIRONMENT VARIABLES

Set by the operator at session start:

| Variable | Description |
|----------|-------------|
| `PLANE_API_KEY` | Plane API token for this session |
| `WORKSPACE_SLUG` | Plane workspace (`${WORKSPACE_SLUG}`) |
| `GITLAB_TOKEN` | GitLab API token (for code/MR operations) |
| `GITLAB_HOST` | GitLab server (${GITLAB_IP}) |
| `AGENT_ID` | Your identifier (e.g., `agent-lead-session-042`) |
| `VAULT_TOKEN` | Scoped Vault token (claude-automation policy) |

---

## 13. WHY THIS EXISTS

AI agents are not perfect. They hallucinate. They make confident mistakes. They
silently "fix" things that weren't broken. They drift from scope without noticing.

This framework doesn't fix those problems — nothing does yet. What it does is make
every action **visible and traceable**. When an agent makes a mistake (and it will),
the issue trail tells us exactly what happened, what the agent believed at the time,
and where the reasoning went wrong.

This is the same principle behind the platform's security posture:
**verification over trust.** We don't trust that the agent got it right.
We verify by making the work inspectable.

The overhead is real. The alternative — invisible autonomous changes to production
infrastructure — is worse.

---

## NIST 800-53 CONTROL MAPPING

| Control | How This Framework Supports It |
|---------|-------------------------------|
| CM-3 | All changes tracked via Plane issues and GitLab MRs |
| CM-3(2) | VERIFY phase mandatory; evidence posted to issues |
| CM-3(4) | Operator approval via MR review |
| CM-4 | PLAN notes document expected impact before changes |
| CM-5 | Token-gated sessions, scoped authorization |
| AU-6 | Engineering notes create continuous audit trail |
| AU-12 | Every action logged with timestamp and evidence |
| AC-5 | Agent proposes, operator reviews and merges |
| SA-10 | Branch strategy, commit conventions, issue traceability |

---

## Multi-Agent Coordination Rules (added by bootstrap session 2026-03-18)

**Read ~/overwatch/agent-roles.md for full role definitions.**

### Before starting any work:
1. Read AGENT-STATE.md in this repo if it exists
2. Read your assigned Plane issue fully
3. Confirm your role (PLANNER/WORKER/JUDGE/COMPLIANCE-SCRIBE)
4. Confirm the files you are allowed to modify (from `modifies_files` in issue)

### Artifact ownership — HARD STOPS:
- If you are not COMPLIANCE-SCRIBE, do not write to: SSP files, gap-analysis.md,
  security-assessment-report.md, system-security-plan.md, SAR, POAM
- If you are not the assigned WORKER for an issue, do not modify files listed
  in another issue's `modifies_files`
- `nist-compliance-check.sh` is **READ-ONLY for all agents always**
- `check-strength.yaml` is **READ-ONLY for all agents always**
- `current-state.md` and `score-history.md` are written ONLY by the reconciliation agent
- CLAUDE.md in any repo requires explicit Jim approval to modify

### Assertion rules:
- Do not write "implemented", "complete", "fixed", or "resolved" unless you
  have run a verification command and seen passing output **this session**
- If you cannot verify, write "UNVERIFIED — requires Judge run"
- Do not close Plane issues. Write "ready for Judge" as a Plane issue comment instead.

### Session end (required):
- Copy AGENT-STATE-TEMPLATE.md to AGENT-STATE.md in the repo you worked in
- Fill in every field. Write UNKNOWN if you don't know, not a guess.
- Commit AGENT-STATE.md to your branch
- Add comment to Plane issue with link to your MR

### If you hit a blocker:
- Do not loop. Do not try to fix things outside your scope.
- Create a child issue in Plane with: what the blocker is, what file/system
  it involves, what role should handle it
- Add comment to your issue: "BLOCKED — child issue {ID} created"
- Write AGENT-STATE.md with blocked status
- Stop cleanly.

### Compliance check counting (CRITICAL):
- Always parse the JSON output, never grep the text output
- `jq '[.checks[] | select(.status=="PASS")] | length'` — correct
- `grep -c "PASS"` — **WRONG, double-counts multi-match lines**
- The cached JSON is at: `~/sentinel-cache/config-cache/nist-compliance-latest.json`
- The script runs on iac-control (${IAC_CONTROL_IP}), not the workstation
