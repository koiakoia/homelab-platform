# Agent State — {REPO_NAME}
**Written by:** {ROLE} — session ending {TIMESTAMP}
**Plane issue:** {ISSUE_ID} — {ISSUE_URL}
**Branch:** {BRANCH_NAME}

## What was completed this session
(list with commit hashes — no assertions without hashes)

## What is IN PROGRESS but not done
(list with exact reason why not done)

## What is BLOCKED
(list with exact blocker — not "needs more work", the specific thing)

## Files modified
(exact paths, not globs)

## What next agent should do FIRST
(one sentence, specific, actionable)

## Compliance state at session end
Run: `python3 -c "import json; d=json.load(open('$HOME/sentinel-cache/config-cache/nist-compliance-latest.json')); checks=d['checks']; p=sum(1 for c in checks if c['status']=='PASS'); f=sum(1 for c in checks if c['status']=='FAIL'); w=sum(1 for c in checks if c['status']=='WARN'); print(f'{p} pass, {f} fail, {w} warn of {len(checks)} ({d[\"timestamp\"]}')"`
Result: {PASS_COUNT} pass, {FAIL_COUNT} fail, {WARN_COUNT} warn
Timestamp of check: {CHECK_TIMESTAMP}
Verified: {YES/NO — did you actually run this}
