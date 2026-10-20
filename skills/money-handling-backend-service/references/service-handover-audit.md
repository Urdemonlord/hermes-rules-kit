# Auditing a live money service before advising what to continue

Trigger: the user asks "what's left to finish on project X" about a service that is
already running against real money. The vault note is a hypothesis; the box is the
evidence. Most of the value is in the fact that the two disagree.

## Order of work

1. Locate the real directory (name drift — verify, don't trust the alias).
2. Read the project's own vault note for intent and known traps.
3. Run the battery below. Do not rank anything from the note alone.
4. Report `verified` / `unverified` / `blocked` per claim, then rank.
5. Write back to the vault note anything that the battery contradicts.

## The battery

```bash
# 1. Process manager state (liveness, restarts — a high ↺ count is a story)
pm2 list   # or systemctl --user status <unit>

# 2. The health endpoint says whether it is DOING anything, not just alive.
#    Copy the JSON verbatim in the report.
curl -s localhost:<port>/healthz | python3 -m json.tool

# 3. The ledger. Read the money tables directly — this is the real state.
python3 - <<'EOF'
import sqlite3; db = sqlite3.connect('panel.db'); db.row_factory = sqlite3.Row
for r in db.execute("select id, amount, status from orders order by rowid"): print(dict(r))
for r in db.execute("select tx_id, amount, matched_order_id from settlements"): print(dict(r))
print('subs', db.execute("select count(*) from subs").fetchone()[0])
EOF

# 4. Credential expiry — a countdown, not a binary
python3 -c "import json;s=json.load(open('session.json'));print(s['expires_at'])"

# 5. Auth gate proved from OUTSIDE the host
curl -s -o /dev/null -w '%{http_code}\n' https://panel.example/     # expect 401

# 6. The anti-brute-force guard proved by ITS OWN counters
sudo fail2ban-client status <jail>       # Currently failed > 0 + a real File list = armed

# 7. Test suite as it stands today
npm run check

# 8. Version control — non-negotiable on a money service
git -C <project> rev-parse --is-inside-work-tree || echo "NOT A REPO"
git -C <project> check-ignore -v .env session.json panel.db panel.db-wal
ls -la <project> | grep '='                # '=' in a filename => leaked token
```

## How to read each result

| Result | What it actually proves |
|---|---|
| Process alive, healthy endpoint `ok:true` | **Nothing about the money path.** Rule 24: a poller can be running and matching nothing. |
| An order `PAID` **with** a row in the claim/settlement table | End-to-end proof from real provider data. This closes the item the note called unverified — say so explicitly, it changes the ranking. |
| `subs` count `0` | Outbound integration is complete plumbing with no consumer. Not "nearly done" — done and unused. |
| `unmatched_reason` non-null rows summing to a real figure | The single most actionable number in the audit: money the operator has not accounted for yet. Attach or write off before new features. |
| Health endpoint exposes `hours_to_expiry` and a `verified` flag | The credential-death path is designed. Check whether the *operator-visible* surface actually gates on it. |
| `curl` returns 401 on the public URL | The gate is real. |
| fail2ban jail active but `File list: No file is currently monitored` | Decorative. Every attempt is unhandled — this is a finding, not a config detail. |
| Test suite green | Only what the suite covers. Ask what real-money path it never drove. |
| `not a git repository` | Highest-priority finding on a money service, regardless of feature list. |

## Ranking rules

1. **Integrity before features.** Version control, unreconciled cash, and a secret
   with a reachable expiry outrank every new capability.
2. **Cheap and irreversible-risk-reducing first.** A `.gitignore`-verified first
   commit costs minutes and is the only item whose absence can destroy the ledger.
3. **Plumbing with no consumer is a strategy question, not a task.** When the
   hardening work is finished and the caller does not exist, the honest output names
   the missing caller and asks whether the integration should exist at all — and
   whether a provider offering a real payment API (unique order ids, no
   amount-matching) should replace the amount-matching design entirely. Quantify
   that trade in the operator's terms: recurring manual credential work vs the
   reconciliation machinery's permanent complexity.
4. **Flag the cliff, do not just report the countdown.** "Token expires in 16h with
   no refresh path" is a report; "every expiry needs a human pasting a live cookie
   into a file by hand, which is itself a credential exposure" is the finding.
5. **Say what you did NOT verify.** If the real-payment path has never been driven
   in this session, do not inherit someone else's claim that it works.

## Output shape

- Lead with the verified-current-state facts, with commands' actual output.
- Then the ordered list of what to continue, each with why-it-unblocks and a
  one-line command where one exists.
- Close with the single question the operator must answer (usually a strategic
  fork), and offer to start item N.

## When your own work is half done, report the halves as separate items

A "done" summary that mixes shipped code with unapplied data produces the exact
follow-up you do not want: *"maksudnya gimana?"* It costs a round trip and it is
usually a sign that the summary was written as a narrative instead of as state.

Split it explicitly and label each half:

```
Done:    the code path (files, tests green, deployed, endpoint returns 200)
Not done: the data (N rows still at their old value; M actions unperformed)
```

The same applies to a commit boundary: "2 commits" and "the second commit is not
made yet" are different facts, and a report that says "committed" without naming
which state was captured sends the operator believing the newest work is durable.

**Name the count you actually found, not the one that sounds right.** A queue of
eight rows against the operator's "seven" is a one-row discrepancy in a real
ledger, and it is exactly the row that may be their money misfiled. Report the
discrepancy, the numbers on both sides, and what would distinguish them.

**When you decline to perform a destructive-looking action, say what it is in one
line and stop.** "8 settlements Rp790.000 are now marked personal; the operator
performs the click" is complete. Re-deriving why the operator might disagree with
the classification, restating the amounts, and offering a third time is padding —
and each restatement makes the next "ya" more likely to be a reflex rather than
a decision.

## How to verify "the feature is done" when the feature has a UI