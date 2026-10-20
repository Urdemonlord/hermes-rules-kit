---
name: money-handling-backend-service
description: Use when building a backend that handles payments or money.
triggers:
  - build the backend for a POS / payment / checkout app
  - the client calls an API endpoint that does not exist yet
  - the app has a login screen but no auth server
  - adding QRIS or bank-notification auto-detection to a server
  - the intended api.<domain> hostname is already taken by another project
  - choosing or pinning npm versions for a new Node service
---

# Money-Handling Backend Service

Backends that move money have a different failure mode from ordinary services: a
wrong branch marks an order paid, and the shop loses real money. Every rule below
exists because of that.

## Golden rules (apply to every instance)

1. **The client never sends an amount.** The server computes the total from line
   items and prices it already knows. If the client can supply `amount`, a
   modified client pays Rp 1 for a Rp 500.000 order.
2. **Money is an integer, always.** Rupiah minor units as `Int`/`BigInt`. Never
   float — `0.1 + 0.2 !== 0.3` compounds until reports do not reconcile.
3. **Refuse to start on a missing or weak secret.** A default value for
   `JWT_SECRET` is how apps leak. Validate at boot and throw.
4. **No native dependencies on a low-RAM shared host.** `bcrypt`, `argon2`,
   `sqlite3` need a compiler and fail or thrash. Reach for `node:crypto`
   (scrypt, pbkdf2) and pure-JS packages.
5. **Verify every dependency version against the registry before pinning.** The
   `latest` tag is not a stability promise — see `references/dependency-recon.md`.
6. **Never claim it works until it compiles and the tests ran.** Writing a whole
   module without a compiler and reporting success is how you ship 16 errors.
7. **Never fabricate a payment credential.** When the merchant has not configured
their static QRIS payload, the server must **refuse** the QRIS order with a clear
error — not invent a QR from an NMID it guessed. A fabricated QR sends the customer's
money to nobody (or to whichever payload you invented), and the order can never be
settled. Lock this refusal with a test so nobody later "fixes" it into generating a
QR. Deriving a dynamic payload *from the merchant's real static payload* is a
different and legitimate operation — see `references/qris-dynamic-from-static.md`;
what is banned is inventing a payload with no real NMID behind it, whether it is a
pipe-delimited template or a hand-rolled EMV string whose source never existed.
8. **Never write a payment integration before you know where the notification
comes from.** "Which component posts to my webhook, and what credential did they
issue me?" has to have a named answer — PJP, MID, or the merchant's own console —
before any handler code is worth writing. If it does not, the correct deliverable is
that question, not a sketch of the endpoint. A handler written against a guessed
notification shape is fiction that compiles.
9. **A status guard is not a claim guard.** Every write that flips an order to a
   terminal paid state must assert BOTH that the order was still pending AND that
   the provider reference is not already bound to a *different* order — in one
   statement, in the data layer. Two prepared statements leave a gap for a replay or
   a racing webhook to slip through, and the result is one transfer crediting two
   orders: the most expensive bug in this whole class. Keep exactly one prepared
   statement per state transition; a second one named "the same write path" is
   already two write paths. Details and the SQL: `references/payment-signal-matching.md`.

10. **When the buyer refuses a unique amount, the answer is FIFO — and it is a
    business decision, not an implementation detail.** Minting the dynamic QR locally
    from the merchant's own static payload means the provider never receives an
    order id of yours, so with identical amounts arrival order is the only signal
    left. Get that acknowledged in writing before building the queue, then build it
    properly: oldest-waiting order takes the oldest payment, inside a batch and
    across batches. See `references/payment-signal-matching.md`.

11. **Ask which credential the buyer actually holds before designing the matching
    strategy.** Portal-login (email+password) versus official developer API (OAuth2
    client credentials) is not a preference — it decides whether the provider ever
    sees an order id of yours, which is the only thing that makes matching
    deterministic. Portal-only means polling, no inbound webhook, account-suspension
    exposure per the provider's ToS, and amount-matching forever. Design for that
    reality or name the gap; do not quietly build the webhook the buyer asked for
    and leave them with a poller at the end.

    Then match the *auth method*, not just the tier. A merchant portal may offer
    phone OTP, email+password, and a pasted browser cookie, and the buyer usually
    has only one of them — commonly OTP, which is exactly the path a paid SDK's
    README omits (it tells you to complete "Reset Password" first, something the
    buyer has no reason to have done). Do not design around password auth because
    the library documents password auth. See
    `references/payment-portal-auth.md`.

12. **Scope an absence claim to the search that backed it.** "This package has no
    OTP path" is checkable; "there is no OTP" is a refusal you will be quoted back
    at after the sibling repo turns out to have one. When you grep one package and
    find nothing, say which package, and grep the other repos the user has already
    linked before you conclude anything about the platform. Retracting a "that
    doesn't exist" costs more credibility than asking one more question.

13. **Persist every settlement the feed reports, matched or not, and make the
    unmatched ones attachable by hand.** A payment that finds no order is the
    normal late-payer case (TTL ran out mid-payment), and if reconciliation only
    *returns* unmatched rows they are gone the moment the next poll scrolls past —
    the customer's money arrived and the system has no memory of it. Write an
    audit row keyed by provider tx id, mark `matched_order_id` on success, and
    expose the null ones as an operator queue with a manual attach action. The
    manual attach must route through the same claim/mark-paid guards as the
    automated path — a hand-written status update is exactly the double-credit
    bug from rule 9 wearing a different hat. Note that this forces the paid guard
    to accept `EXPIRED`/`CANCELLED` (not just `PENDING`): manual attach exists
    *precisely* because the order already left the pending state. See
    `references/settlement-queue-fifo.md`.

14. **Do not re-report a spent transaction as unmatched on every poll.** After a
    payment is consumed, the claim insert on the next cycle is a no-op, so the
    match loop "fails" and reports it unmatched again — the log fills with
    correctly-paid transactions and the real late payers drown. Check whether the
    tx is already claimed before counting it as a mismatch.

15. **Every queue needs a terminal state other than the answer, and the queue
    filter must read it.** A review queue whose only exit is "attach to an order"
    cannot represent the most common real outcome: the money is real, it is in the
    account, and it was never panel revenue — a personal transfer, a GoFood order,
    a supplier invoice paid from the same balance. An operator told to "declare this
    personal spending" and given only an attach button will either file the money
    under a wrong order or leave the row in the queue forever.

    Add an explicit write-off marker column, filter it out of the queue and out of
    the unmatched total, and surface the written-off amount as its own stat so the
    reclassified money stays visible rather than vanishing. The marker must be read
    in **four** places, and the fourth is the one that gets missed: the reconcile
    loop's own in-memory unmatched list, which feeds the per-poll log line and is a
    separate code path from the queue query. Missing it leaves a dashboard reading
    zero next to a log repeating the old count every cycle — a stale signal is worse
    than no signal, because the operator can only resolve the contradiction by
    distrusting the panel. Grep every reader of the settled state, not the one query
    you can see. Three invariants the test must pin:

    - **The marker survives a re-poll.** The settlement feed re-reports the same
      `tx_id` every cycle, and the INSERT path does not touch the marker column, so
      a write-off silently undone by the next poll refills the dashboard forever.
      That is the whole reason the marker is a column rather than a note.
    - **A write-off is a decision, so it is audited and reversible, and a refused
      one logs nothing.** Rows that all read the same reason token are
      indistinguishable to the operator a week later; the audit detail must name
      the amount, and the undo needs its own route.
    - **Attach clears the marker, and write-off refuses an already-matched
      settlement.** Attaching says "this was our money", which contradicts the
      marker — leaving both set hides a genuinely settled row. Write-off applied to
      a matched settlement double-counts revenue as personal spending while the
      order stays `PAID`, so refuse it and name the remedy (detach first).

    Because the marker makes a destructive-looking operator action one keystroke
    away, require a typed confirmation in the UI rather than a bare button. Do not
    perform the write-offs on the rows yourself when the user asked for the feature:
    the operator owns that call, they can see the nominals, and the money is theirs —
    report the count and the total and leave the action to them.

    **Name the bucket for what it is, not for what it is not.** Before adding the
    action, read the existing labels. Anomaly words for this bucket — *unmatched*,
    *orphan*, *stray*, "money that did not match" — assert that something went
    wrong, which is false for money the operator themselves transferred into the
    account. That framing costs more than the feature: the operator re-audits a
    settled question every cycle and reads a correct dashboard as untrustworthy.
    Replace the headline, the column header, the button label, the count string and
    the reason value with the settled fact ("without a note"), keep the machine token
    in code and the `title` attribute, then grep the old word to prove the rename
    landed everywhere.

16. **A same-amount queue needs a hard cap, checked inside the same transaction as
    the INSERT.** In exact mode the client picks the amount, so `POST /orders` is an
    unbounded producer for a queue only a payer can drain — orders nobody intends to
    pay sit at the front and every real order queues behind them. Cap **per amount**
    (`MAX_PENDING_PER_AMOUNT`, 5 is a sane default for personal use); a cap on total
    pending just takes the popular price offline. A `SELECT COUNT(*)` before the
    insert is a race: N concurrent requests all read the same count and all pass.
    Take the writer lock first and let the loser fail.

    State plainly what the cap is and is not: **it bounds pile-up, it does not
    disambiguate.** With five orders open at one amount, a payment cannot be
    attributed to a payer — oldest-first is a policy you chose, not an identity the
    provider gave you. Never present the cap as anti-fraud or as ambiguity
    resolution.

17. **Rate-limit the upstream poll, not just re-entrancy.** A `running` flag stops a
    second poll stacking on a slow first one; it does nothing against ten sequential
    manual triggers a minute. Every poll spends rate-limit budget against a merchant
    account, and exhausting that budget degrades precisely the visibility the poller
    was built for. Put the cooldown **inside** the single function that talks
    upstream so the interval timer and the manual endpoint share one decision point,
    and return the remaining wait to the caller so the UI can say "wait Ns" instead
    of appearing to have done nothing.

18. **Decide the exposure question before anyone asks for a hostname.** A panel
    holding a live merchant session is not an ordinary internal tool: the session file
    is a bearer credential for real money, and a public domain plus a bearer header in
    the browser's `localStorage` means any XSS exfiltrates it. The private-first
    default — bind `127.0.0.1`, keep the secret out of the browser — is the blueprint
    you already agreed, and it survives because it is the boring option. Do not
    re-litigate it because exposing the panel is more convenient; do the private thing
    and name the hostname as a plan, not a change.

    When exposure IS approved later, the shape is nginx `auth_basic` plus
    `proxy_set_header x-panel-token` — the proxy **overwrites** the header, so the
    secret never reaches the browser at all. Basic auth alone is not the control:
    it has no lockout, so pair it with a fail2ban jail on the vhost's 401s (an
    nginx `limit_req` only throttles volume, not repeated wrong passwords), and it
    does not restrict which orders an authenticated operator may touch — backend
    authorization is still required.

    **An approved exposure is a decision to execute, not one to keep re-arguing.**
    State the consequence once, in the same breath as the approval, then build it
    properly. The operator owns the call; your job is to make the thing they
    approved as safe as it can be and to say plainly what remains unfixed. Do not
    re-open the private/public question after they have answered it, and do not
    treat a later "did you deploy it yet?" as a reversal — answer with the verified
    state (DNS, process, cert, auth gate) rather than re-raising the objection.

    Two facts to state up front rather than at the end: a cap or an auth gate does
    **not** fix FIFO ambiguity (rule 15), and rotating a secret that was pasted in
    chat is part of the job, not a follow-up.

19. **A generated artifact's lifetime is tied to order state — gate it on the
    server, not in the client.** A QR, barcode, or receipt image is valid only
    while the order is payable. Refuse to render it once the order settles,
    expires, or is cancelled, from the **endpoint that produces it** — a client
    `if (status !== 'PENDING')` is a rendering nicety anyone can re-patch, and the
    payload sits in the page. Two states must be distinguishable in the response:
    "not payable" and "expired" are different failures and deserve different codes.

    Three failure modes present as the identical user report *"it disappears on
    its own"*, and TTL is the wrong place to look first:

    - the list query does not SELECT the payload column, so refresh renders an
      empty cell while the row is fine;
    - "no payload" and "payload not fetched" collapse into one UI token — return
      an explicit `qris_has`-style flag so the client can tell them apart;
    - a countdown helper returning `null` for settled orders makes `null <= 0`
      evaluate true, printing "0 minutes left" on a paid order.

    Ship the list with a flag, not the payload — a base64 blob per row is what
    makes a panel time out on a phone — and re-render on demand from a per-order
    endpoint. **Delete the artifact from the UI; keep the payload in the database**
    (it is audit evidence for a dispute). Translate status enums to plain language
    at render time and keep the raw value in a `title` attribute: whoever
    reconciles payments is a shopkeeper, not a reader of your schema. Details and
    the three verified status codes:
    `references/generated-artifact-display.md`.

20. **A secret file's mode is part of the credential.** `chmod 600` the token/env
    files at creation time, not when the audit reminds you. A `644`/`664` env file on a
    shared host is readable by every local account, which converts "only services that
    hold the merchant session" into "every account on the box". Check with
    `stat -c '%a %n' session.json .env` in the same pass that verifies the secret is
    outside the static docroot. Also keep it gitignored and out of any docroot the
    webserver serves.

21. **Clock-skew tolerance is one exported constant, applied at every boundary
    that can reject a payment.** The payer's phone and the merchant's server
    disagree on the time, so a tolerance window belongs around every time
    comparison. The trap is that tolerance is normally written where it is
    *checked* (`t <= expires_at + SKEW`) and silently omitted where the row is
    *selected* (`WHERE expires_at > now`). The query then discards the order
    before the tolerant check can ever see it, so that branch is dead code that
    reads like protection.

    Export the number from the module that owns the table and use it in all
    three places: the queue query, the transaction-time check, and the expiry
    sweep. The sweep is the one people miss — retiring an order at
    `expires_at <= now` while the queue still hands it out for another minute
    means the order leaves the claimable set before its own lifetime is over.
    State the resulting effective lifetime (TTL + skew) so nobody has to derive it.

    **Do not put the correction in a default parameter.** `pendingFor(amount,
    now = Date.now() - SKEW_MS)` looks like the fix and is inert whenever every
    caller passes `now` — which is every caller. Fix the argument at the call site
    and make the parameter required, so the next caller cannot silently
    reintroduce it. Where the constant must be applied inside a query it is a
    caller-side subtraction (`pendingFor(amount, now - SKEW_MS)`); say exactly
    that in the function comment, or the tolerant version reads as an
    optimisation nobody asked for.

22. **Show the column that helps the operator, not the one that mirrors the provider's
    schema.** An unmatched-settlement queue naturally renders the feed's own `status`
    field, which is provider bookkeeping (`settlement`, `paid`, …) and tells the shop
    nothing about what to do. Every such table ends up one column of noise. Choose the
    field whose value changes the next action — the unmatched reason — and translate it
    to plain language at render time, keeping the raw token for anything that matches
    on it.

    Two reasons must stay distinct: "no order ever existed at this amount" means
    something is wrong upstream (a stale QR, a wrong account), while "an order existed
    and its TTL ran out mid-payment" is the normal late payer and the case the queue
    exists to serve. Collapsing them makes the routine case look like an incident.

    Then shorten the job past diagnosis — rank the candidate orders instead of making
    the operator search the list (see `references/settlement-queue-fifo.md`). The reason
    says *why*; the shortlist says *which one*. A suggestion fills the attach field, it
    does not attach by itself.

23. **Rank a match set by the evidence, and make the ranking the tested contract.**
    When several rows can match, "which one" must come from a stated rule, not from
    whatever the iteration yields. Candidates whose validity window actually contained
    the transaction outrank ones that merely share an amount; then order by closeness in
    time. For the credit path insertion order is the agreed FIFO policy, but for a
    *recommendation* it is not an answer.

    The ranking is only real if a test pins it, and that test must contain the case
    separating "correct" from "plausible": two rows at one amount, one expired and one
    payable, asserting the payable one ranks first. Also assert that a non-matching
    amount returns an empty list rather than an error — for real data the most common
    correct answer is "nothing matches", and an endpoint that fails there is worse than
    one that suggests nothing.

24. **Any action that moves money into a state you cannot leave is a permanent
    operator hazard — build its undo before you ship it.** A hand-made attach that
    flips an unpaid note to `PAID` with no way back turns one mis-click on a
    Rp 25.000 row into permanent data corruption, and the operator will find out
    during the reconciliation they trusted. Audit it, make the release action
    explicit, and give it its own route rather than a `DELETE` on the attach path —
    the release is rarer than the mistake it fixes, so it must never be reachable
    by the same gesture.

    The undo is **not** a symmetric replay of the attach, in three specific ways:

    - **Return the order to the state its clock implies, not to the state it left
      from.** Restoring `PENDING` on a note whose TTL has run out resurrects a QR
      for a window that already closed and lets the settle loop claim real money
      against a note the customer was told had expired. `PENDING` while still
      payable, `EXPIRED` once it is not — decided by `expires_at`, not by a
      constant.
    - **Restore the reason too.** An order returns to the review queue, and a
      queue row that left without its reason cannot be reviewed.
    - **Guard on `changes`, not on absence of an exception.** An `UPDATE ... WHERE
      status = 'PAID'` that matches nothing because a concurrent writer moved the
      row still "succeeds"; returning `ok: true` there is a silent no-op that tells
      the operator their mistake is fixed when it is not. Check the row count.

    Most importantly, **only a match an operator made by hand may be released.** A
    match the settle loop produced holds real money, and reversing it is a refund
    the panel has no way to perform — so the undo must refuse, loudly. That makes
    the question "was this match hand-made?" load-bearing, and it is **answerable
    only from the audit trail**: `customer_ref`, `tx_id`, and status look identical
    on both paths, so inferring it from the order row either refuses legitimate
    undos or, worse, lets automatic matches through — which is the exact opposite
    of the guard's intent. Define the predicate **once** and let both the release
    guard and the dashboard button that offers it read it, then assert in the test
    that the button appears on a hand-made match and not on an automatic one —
    otherwise the panel offers a button that always fails, or hides the fix.
    Details: `references/audit-trail-and-operator-attribution.md`.

25. **A health endpoint that reports only on itself will report `ok` while the
    service is doing nothing.** A dead upstream session is silent: the poll keeps
    throwing into a swallowed catch, nothing moves, and every row still looks
    freshly served. A hardcoded `ok: true` turns that into a green light. Make
    `/healthz` answer from the *upstream's* state and return non-200 when
    reconciliation has actually stopped, while keeping `ok` meaning "the panel is
    up" — two different claims, and a monitoring check needs the one that is true.

    Two sub-rules that the naive state machine gets wrong:

    - **Order the states by how much they cost you.** A failed poll is worse than
      an expired session, so it must win the precedence check, even though the
      expired session is the more "interesting" condition.
    - **A fresh process and a never-once-successful process look identical.** Before
      the first poll returns, "no errors" and "working" are the same shape. A
      separate `verified` flag — false until the first success — is what
      distinguishes them; a status field alone cannot. Without it you ship a panel
      that announces health during the window where it is least likely to be
      healthy, and the failure is invisible precisely because it looks fine.

    Log the first three failures with reasons, then go quiet, and reset the
    counter on the first success so recovery leaves evidence. Unbounded per-cycle
    error logging is how a real outage gets buried under 1.400 identical lines a
    day, and it also guarantees nobody reads them. Surfacing this to a human needs
    the same honesty: a badge that renders the operator-facing reason, and a
    retry button that **surfaces its own rate-limit cooldown** rather than
    appearing to have done nothing. Details:
    `references/upstream-credential-health.md`.

26. **A dependency resolved by path outside the project is not a dependency.** A
    `"file:../../../../tmp/sdk"` entry in `package.json` — usually left behind by
    a session that cloned a source tree "just for now" — is an unversioned local
    build with no restore path. The service does not degrade, it stops starting,
    and there is no fallback: one reboot or tmp reaper is a full outage of a
    payment panel.

    Find it mechanically before trusting any deploy story:

    ```bash
    grep -nE '"file:|\.\./|/tmp' package.json
    readlink -f node_modules/<pkg>          # a path here means a symlink install
    ```

    Fix in this order: publish it properly if the registry has it; otherwise
    vendor the built output into the repo with the upstream SHA pinned in the
    manifest, stripped of source maps, dev dependencies and lifecycle scripts (npm
    runs those on `file:` installs, so an inherited `prepare: tsup` fails on a box
    that has no tsup). Regenerate the lockfile — one still holding the old `file:`
    path makes `npm ci` demand the directory you are deleting.

    **Then prove it by deleting the thing you just fixed**: `rm -rf` the source
    directory and `node_modules`, run `npm ci` from scratch, compare the built
    file's checksum against the pre-vendor copy, and run the suite. An install
    path that was never reconstructed has not been verified. Finish by restarting
    the service and exercising the dependent feature through its public route, not
    by re-reading the dependency tree. Recipe:
    `references/vendoring-unpublishable-deps.md`.

27. **A delivery table that is deleted on failure is a ledger, not a queue — and
    claiming a row must be one statement.** "Send, and on any failure delete the
    claim so a later cycle retries it" describes a retry that does not exist
    unless something re-invokes the send. When the send happens once per event
    from a single call site (a poll tick that noticed the payment), nothing ever
    comes back: the row is deleted, the event is gone, and the subscriber that was
    down for one minute never hears about a payment that was already taken. The
    comment is the tell — read it as a claim, then grep the callers.

    So the row **is** the queue item, and it survives failure: `attempts`,
    `next_attempt_at`, `last_error` on the same row. Retry with backoff, and stop
    at a ceiling — but **stop, do not delete**. A dead delivery left in the table
    with its last error is what the dashboard renders and the operator acts on;
    dropping it makes the money movement unauditable.

    Three rules that are not obvious:

    - **Claim atomically, never select-then-update.** Reading the due rows and then
      updating them is a check-then-act race, and the two pumps a real service has
      (an immediate kick from the request/poll path, plus the periodic retry tick)
      will overlap on exactly the row with `next_attempt_at = 0`. The subscriber
      then receives the same payment twice — proven here, not theorised: `hits: 2`,
      `attempts: 1`. Write the new due date in the same UPDATE that selects:
      `UPDATE … SET next_attempt_at = ?now + HOLD WHERE (keys) IN (SELECT … due
      … LIMIT n) RETURNING …`. The second pump's `WHERE` then matches nothing.
      Make `HOLD` comfortably longer than one attempt's timeout, so an expiry
      mid-flight can only cause a retry that is *early*, never a duplicate.
    - **`INSERT OR IGNORE` must not reset the schedule.** Re-queuing the same
      `(sub, order, event)` on a later fire hits the ignore branch and keeps the
      stored `attempts`/`next_attempt_at` — that is correct, and worth a comment,
      because an `ON CONFLICT DO UPDATE SET next_attempt_at = 0` "to be safe"
      would make a re-fired event retry forever at full speed.
    - **Retry 4xx too.** A 403 is usually a secret that was rotated or an endpoint
      that moved; a subscriber fixed mid-backoff must still receive what it missed.
      Give up on the ceiling, not on the status class.

    The test must run a **real socket** returning 503-then-200: a stubbed `fetch`
    cannot exercise the 10s abort, and "connection dropped" is a different failure
    path from a status code and needs its own case. Details, the schema, and the
    teardown race that fakes a webhook bug:
    `references/webhook-delivery-queue.md`.

28. **A list filter that does not reach the totals produces a number that answers a
    question nobody asked.** Reconciliation windows ("last month", "Rp 50.000 and
    up") are how an operator queries money, so the moment a filter exists the
    headline total must come from the same window as the rows under it. Filtering
    `rows` and leaving `stats` global is worse than having no filter at all: the
    unfiltered total is still a true number, it just silently contradicts the list
    printed beneath it, and the operator has no way to tell which one the panel is
    claiming.

    Three sub-rules, each from a bug this class actually ships:

    - **One filter fragment, reused, not copied.** Build the `WHERE` clause once and
      interpolate it into every statement. Two statements that drift apart is the
      defect, not the duplication.
    - **Assert the statement's *arity*, not only its values.** A shared template
      lands on statements with **different placeholder counts** — the list queries
      carry a `LIMIT`, the aggregate does not. Passing the list's five values to
      the aggregate's four placeholders does not return wrong rows; it throws
      `column index out of range` on every single request. A suite asserting only
      on returned values passes against code that cannot serve one request at all,
      because no assertion reached the call. Add `assert.doesNotThrow` around every
      public entry point for each filter shape.
    - **Compare instants, not text.** `ORDER BY transaction_time` and
      `WHERE transaction_time LIKE '2026-10%'` happen to be correct while every
      row shares one offset; the first row in `Z`, or another `+07:00`, sorts to
      the wrong end and strays outside the window with no error. Use
      `unixepoch(col)` (or an equivalent), and put a genuinely different-offset row
      in the fixture so the case is exercised. Rows with no parseable instant must
      sort **last, never dropped** — and when an amount filter is present they still
      pass it, because the amount is known even when the date is not.

    Inclusive at midnight, UTC on both ends: an operator asking "through the 3rd"
    means the 3rd, and a bare `YYYY-MM-DD` parsing as midnight UTC is what makes
    the two ends agree about what day means.

    **Refuse unreadable bounds; never ignore them.** A typo'd `from=` that silently
    returns everything is indistinguishable from a filter that worked. `400` on an
    unparseable bound, on `from > to`, and on a negative amount.

29. **A scope table is only as good as the path the guard actually reads — and the
    guard's path is not the path your test wrote.** A panel behind a single shared
    admin secret hands every caller the operator surface: the settlement ledger,
    the write-off queue, the audit trail. Per-caller keys narrow that, and the
    narrowing mechanism is a table keyed on `(method, route shape)` returning the
    granted scope or `undefined` for anything unlisted. Default-deny is the point —
    it converts "remember to add a guard when you add a route" into a property you
    can assert, so a route added next quarter is unreachable rather than quietly
    exposed.

    Three traps that leave the table correct, its unit suite green, and the live
    surface wrong. All three were live bugs here.

    - **Middleware strips mount prefixes.** Inside `app.use('/api/v1')` the path a
      guard reads is `/orders/ORD-1`, not `/api/v1/orders/ORD-1`. Every request 403s
      while the table test passes, because the test was handed the pretty full-path
      string the running server never produces. Compose the key from the mount plus
      the sub-path (`req.baseUrl + req.path`). You find this only by booting the
      service — no unit test of the table can, because the table is not where the
      path is computed.
    - **Collapsing a trailing segment to `:id` is not free.** A helper that rewrites
      the last segment turns `/orders` into `/orders/:id` as well, breaking the
      collection route that was working. Assert the collection route *and* the
      parameterized route, and inject the collapse to prove the assertion bites in
      both directions.
    - **Test the *composition*, not just the table.** `grantFor('GET', '/api/v1' +
      '/orders')` is green; the live bug is `grantFor('GET', '/orders')`. Pin the
      composition the guard performs, so a future mount change cannot silently
      re-break it.

    **Write the refusal test first, not the creation test.** A suite that asserts
    "the right key can read orders" passes against a guard that grants everything,
    which is the failure that costs money. Assert the operator-only routes return
    no grant, assert a revoked key stops working at once, assert a missing key is
    refused. Revocation has two separate ways to silently not revoke: the lookup
    omits the revoked column from its `SELECT` so the check reads `undefined` and
    passes, and the update is `WHERE id = ?` with no narrowing, so a second revoke
    still matches the row and still reports success. Both make revocation *invert*
    — the key you just killed keeps working — which is the quiet version of this bug
    class.

    **A non-ambient credential is CSRF-exempt by construction, but the exemption
    needs its own test.** A bearer key in a header, not a cookie, cannot be attached
    cross-site by a browser, so exempting that prefix from the CSRF layer is
    correct — but "correct" here means the exempt middleware is ordered *before* the
    CSRF middleware. Move it after and every write 403s while unit tests stay green.
    Prove it with a request that carries no `Origin` header at all and expect success
    on the API route, `403` on the admin route.

    Exclude by prefix match against the framework's own routing table, not by
    comparing a string the client can influence.

    **Label the rate limit's tier honestly.** An in-process counter resets on every
    deploy or crash, so a leaked key plus a restart is a fresh budget; say so in the
    code and the handover rather than implying a distributed guarantee. Prove the
    limit under a **burst in one shell loop**, not N sequential requests — the
    transition point and the `Retry-After` value are the evidence, the configured
    constant is not.

    A non-ambient key is also the right credential to hand an integration while the
    panel's own admin secret stays out of the browser — but mint a key only for a
    consumer that exists, and revoke smoke-test keys when the smoke test ends
    rather than leaving a live credential nobody is using. Recipe:
    `references/api-key-authorization-surface.md`.

30. **Once the cap exists, refuse to create the ambiguous pair — one active order per
    customer per amount.** Rule 16 bounds the pile-up; it does not remove the
    ambiguity, because the amount is still the only signal the provider returns. The
    remaining lever is refusing the *duplicate buyer* rather than guessing between
    two of their orders.

    Why polling frequency is not a lever: the dynamic QR is the merchant's static
    payload with the amount tag rewritten, so two orders at the same amount produce
    **byte-identical payloads**, and the settlement feed carries no order reference
    at all (`merchant_id` is NULL on every row observed). Sampling an identical
    value faster yields the same value — do not propose a wait-and-retry as the
    answer. Prove it with a test that asserts two same-amount orders produce
    identical QR payloads, and keep that assertion: it is the fact that makes every
    "just poll faster" suggestion wrong.

    So guard on `(customer_ref, amount)`, checked **inside the same `BEGIN
    IMMEDIATE`** that enforces rule 16 — take the writer lock first, then count both
    predicates, or the race comes straight back. A `SELECT` before the insert is a
    race, exactly as in rule 16.

    **Refuse with 409, not 429.** A second order for the same customer and amount can
    never succeed by retrying, so a retry hint is a lie about the caller's own
    request; reserve 429 for the per-amount cap, which does drain.

    Two honest limits to state rather than paper over:

    - **Anonymous orders stay ambiguous by construction.** `customer_ref` is
      optional, so the panel itself can still produce five same-amount orders with
      no way to attribute a payment. That path is manual (write-off/attach) and
      cannot be *enforced* without the data. Say so instead of implying the guard
      covers it.
    - **Document the constraint in the integration docs.** Without "one active order
      per customer per amount", the first integrator hits 409 with no idea why and
      works around it by inventing a unique-amount scheme the provider never
      promised to honour.

    **A test must pin both halves.** Assert what *cannot* be fixed (the second
    buyer's order stays `PENDING`, not silently credited) and what must not break (a
    replayed transaction for the same order does not credit a second one). A change
    to the matcher later cannot then "resolve" the first case into crediting buyer
    two without failing the suite.

30b. **A returned reason changes the truthiness contract — grep callers for
    truthiness, not for the return value.** Replacing a bare `null` with a result
    object (`{id, …}` or `{blocked, reason}`) gives the caller something to log,
    which is why it is worth doing. But every downstream `filter(Boolean)` /
    `if (!result)` now counts a *refusal* as a success, because the refusal object
    is truthy. Name the success field in collection filters (`filter(r => r?.id)`),
    and when a second invariant lands in front of the same path, expect the
    pre-existing suite to go red naming the *old* invariant — the test is stale, not
    the code. Update it to assert the new rule and add a case for it; never satisfy
    the failure by loosening the guard.

    Corollary worth knowing before you debug: a fixture that used to test the cap
    (`cap0…capN` plus one `over`) stops testing it once the customer guard sits in
    front, because `over` trips the customer rule first and the cap is no longer
    exercised at all. Assert each invariant separately.

    And confirm every mutation landed before trusting its result — a patch with an
    empty or ambiguous `old_string` can report success without writing, so a
    red-to-green injection can leave the bug in place. Grep the file to prove the
    edit is on disk; anchor re-injections on a unique following statement, never
    on `''`.

31. **Three guards on any automated fulfillment path — all three are load-bearing,
    and a code comment saying "waiting for the user" is what tells you the third is
    missing.**

    - **Declare the claim before calling the send, not after.** Rule 27 covers the
      retry pump; this is the *forward* path. If the order is only marked
      `processing` once the send has returned, then an operator pressing retry
      twice — or a lazy cron working the same queue — walks two requests through
      the same unclaimed row and pays twice. The claim has to be the first write,
      and the send reachable only by whichever request won it.
    - **A route that can trigger a real transfer needs auth, and "it re-reads the
      order and checks the status" is not auth.** A status guard answers *whether
      this order is payable*; it does not answer *whether this caller may spend the
      shop's money*. A public endpoint taking an order id or invoice code and firing
      an outbound transfer is an attacker-accelerated spend path — they cannot steal
      the funds, but they choose when it leaves and can drain the sending account on
      demand. Wrap it in the same admin/cron gate the neighbouring admin routes
      already use: a protected sibling route is proof the gate exists and was simply
      omitted here.
    - **Every state you write needs a reader, or the queue leaks.** A state named for
      an external party's pending action (`pending_acceptance`,
      `awaiting_confirmation`) is not a resting state: if nothing ever re-reads the
      upstream side to settle it, the row sits there forever and the "in progress"
      count only grows. Either a poller resolves it against the provider, or the
      state should not exist. Same test for a retry-counter column — one nothing
      increments is a migration, not a mechanism.

    Corollary when you audit an existing fulfillment path: a function that returns
    `success: true` because it *sent an offer* has not delivered anything. Name that
    distinction in the report — a return value describing the send is not evidence
    of the fulfillment, and the doc comment claiming "waiting for the user" is the
    tell that no code resolves it.

## Procedure

### 1. Recon before writing a single line

- **Read the client's expected contract first.** Open the client's API layer and
  note the exact paths, field names, and casing it already sends/expects
  (`sale_id`, `no_transaksi`, `qr_payload`). The backend must match the client
  you have, not the one you would have designed.
- **Treat that contract as frozen.** A mobile client is already installed on
  users' phones and cannot be updated with your server. Do not add a global path
  prefix (`/v1`), rename a route, or change a field's casing "for tidiness" —
  every installed app stops working at once, and the fix is a new app release,
  not a server change. Add new versions as ADDITIONAL paths later; never move the
  ones that shipped.
- **Verify the contract mechanically, in both directions — having read it is not
  enough.** Grep the client's serializer annotations (`@SerialName("access_token")`)
  and grep your own response objects, then compare the two lists field by field.
  Writing the server from memory after reading the client is how a login response
  ships as `accessToken` while the client reads `access_token`: login fails for
  every user, no test notices, and the app just bounces back to the login screen.
  Check request bodies too — a DTO that accepts `refreshToken` while the client
  posts `refresh_token` silently breaks session refresh the same way.
- **Find out who already owns the target hostname and port.** A subdomain you
  assume is free may be serving another project (this host has `api.<domain>`
  taken by an unrelated service). Check DNS, the nginx config, and `ss -lntp`
  before a client constant is baked in — see `vps-project-deployment-isolation`.
  A client already shipped pointing at that foreign host is a live credential
  leak: it posts users' logins to someone else's service. Repoint it and bump
  `versionCode`, or installed copies never receive the fix. If you cannot create
  the new subdomain yet, serve the API under a path (`/api/`) on a domain that
  already resolves and has a certificate, and strip the prefix in the proxy so
  the in-app paths stay unchanged.
- **Registry-check every dependency.** Recipe and the three traps it catches:
  `references/dependency-recon.md`.
- **Check which ports and container names are already in use** before writing
  `docker-compose.yml` (`ss -lntp`, `docker ps`). A shared host may already run a
  database on the default port — bind yours to a different one on `127.0.0.1`
  only, and put a `memory:` limit on the container so it cannot starve the
  neighbours.

### 2. Pin exact versions, then install with a memory cap

Write the `package.json` with **exact** versions (no `^`) so a rebuild months later
resolves identically. Install under a hard cap so you cannot OOM a shared host:

```bash
NODE_OPTIONS='--max-old-space-size=768' npm install --no-audit --no-fund
free -m | head -2        # confirm you did not starve the other projects
```

### 3. Write the pure core first, and unit-test it before any wiring

The decisions that cost money — totals, tax rounding, whether a payment
notification matches an order — belong in **pure functions with no database, clock,
or network access**. Every input is an argument, so every scenario is testable:

- `core/money.ts` — totals, tax, rounding direction
- `core/signal-matcher.ts` — which order does this payment belong to
  (`references/payment-signal-matching.md`)
- `core/amount-allocator.ts`, `core/order-number.ts`

Only then wire them into controllers/services. A matcher tangled with Prisma
queries cannot be tested, and it is the code most expensive to get wrong.

### 4. Verify with the compiler, then BOOT it — in that order

```bash
npx tsc --noEmit          # the first honest test of code you wrote blind
npm test                  # then the suite
node dist/main.js &       # then actually start it
curl -s http://127.0.0.1:<port>/health   # and hit a real endpoint
```

Run these **before** reporting progress. Fix the errors, then report.

**A clean compile is not a working service.** TypeScript cannot see dependency
injection, and it cannot see framework route syntax — both fail only at boot. A
service that compiles, passes its tests, and then refuses to start is a normal
outcome, not a rare one. Boot it and read the log before you call it done; the
concrete wiring traps are in `references/nestjs-wiring-and-runtime.md`.

### 5. Rounding has a direction — pick it deliberately and write it down

- Tax / percentage discounts round **down**: the buyer is never charged a rupiah
  the rule did not produce.
- A unique-amount bump rounds **up**: never make the bill smaller than the goods.

State the direction in the code comment. A silent `Math.round` invites a later
"fix" that flips it.

## Pitfalls

### ⚠️ You CAN mint a dynamic QRIS payload locally — the PJP is only needed for the *notification*

Correct this belief if you hold it: "only the PJP can issue a dynamic QR, so this is
impossible in code" is wrong, and it costs a session because the user then finds a
library that does exactly that. A dynamic QRIS payload is the merchant's own static
payload with three edits — flip tag `01` from `11` to `12`, inject tag `54` with the
amount, recompute CRC16-CCITT over `payload + "6304"`. Any wallet will scan it and
pre-fill the amount. Full algorithm plus a `zxingcpp` decode recipe:
`references/qris-dynamic-from-static.md`.

What the PJP (or an unofficial portal poller) is actually needed for is the **other
half**: knowing the money arrived. Minting a dynamic QR does not create a
notification channel. Those are separable decisions and conflating them produces
either a dead-end refusal or, worse, a panel that generates beautiful QR codes and
never confirms a payment.

So answer both halves, in this order:

1. **Can we generate an amount-bearing dynamic QR from the static payload we already
   hold?** Yes — local TLV surgery. Do not refuse this.
2. **Where does the paid notification come from, and with what credential?** That
   still needs a named answer before any webhook handler is worth writing.

What each half means in practice:

- A **static** payload (NMID + merchant name, no amount tag) makes the customer type
  the amount themselves, and the merchant cannot tell two same-amount orders apart.
- A **dynamic** payload (tag `01` = `12`, tag `54` = amount) makes the wallet pre-fill
  the amount. It does **not** carry an order id, so matching is still by amount —
  `references/payment-signal-matching.md`.

**Static still means no notification of its own**, whichever way the payload was
built. Nothing about a QR emits a callback; a poller against a merchant console or a
PJP webhook does. Mint the dynamic QR locally and you still owe the notification half.

The migration to *automatic* confirmation is an account/signup task, not a coding
task. Say so plainly instead of producing a handler that cannot work.

Full format, the fake-payload trap, and the audit checklist: `references/qris-static-vs-dynamic.md`.

### ⚠️ Prisma `BigInt` does not survive `JSON.stringify`

`JSON.stringify({ a: 1n })` throws `Do not know how to serialize a BigInt`, and
Prisma returns `BigInt` columns as `BigInt`. The client expects a JSON number.
Convert at every exit path — one helper, used everywhere:

```ts
export function toJsonAmount(value: bigint | number): number {
  const n = typeof value === "bigint" ? Number(value) : value;
  if (!Number.isSafeInteger(n)) throw new Error("Nominal melebihi batas aman JSON.");
  return n;
}
```

### ⚠️ npm now blocks lifecycle scripts by default

A fresh `npm install` prints `N packages have install scripts not yet covered by
allowScripts` and **silently skips them**. For Prisma that means `prisma generate`
never ran and `@prisma/client` is absent — the failure surfaces much later as a
missing module. Approve the scripts (`npm approve-scripts <pkg>`) or run
`npx prisma generate` explicitly, then re-check.

### ⚠️ Login must not reveal which emails exist

Answering faster for an unknown email than a known one leaks the account list.
Hash a dummy value on the miss path so both branches take the same time:

```ts
export async function dummyVerify(): Promise<void> {
  await scryptAsync("dummy", Buffer.alloc(16, 1), 64, { ...PARAMS, maxmem: MAX_MEM });
}
```

Compare password hashes with `crypto.timingSafeEqual`, never `===`.

### ⚠️ Same rejection for "no such order" and "not yours"

If the API says `Order tidak ditemukan` for one case and `bukan milik Anda` for the
other, an attacker learns which order IDs exist. Return one message and one status
for both. Do not put the real reason in the response body; put it in the audit log.

### ⚠️ Testing the server against itself proves nothing about the client

`curl` against your own API, and a test suite that asserts on your own response
objects, both pass while the app is completely unable to log in. The only test that
catches a contract mismatch is one that reads the names the **client** expects and
asserts they exist in the response. Until a real client has called the endpoint, say
"the endpoint works" — never "the app works".

**Make that test read the client source and gate it so it cannot pass silently.**
Parse the client's serializer annotations (`@SerialName("access_token")`) out of the
client tree at test time and assert each name appears in your response — so the check
re-runs on every change instead of being verified once at design time.

- **A skipped test is a false green.** When the client source is not found the suite
  must FAIL, not `describe.skip`. Wire an env var (e.g. `WAJIB_KONTRAK_KOTLIN=1`) that
  turns a missing client tree into an error, and set it in CI. Otherwise every run
  that did not actually find the client is green — the same blind spot that let the
  casing bug ship.
- **The CI path filter must include the client tree.** A change to only the client (a
  renamed field) has to trigger the backend contract job. Filtering on `apps/api/**`
  alone means the backend never re-verifies when the client moves.
- **Prove the guard works by reintroducing the bug.** Temporarily restore the wrong
  casing, confirm the suite FAILS with the mismatched keys in its output, then revert.
  A contract test that has never failed has not been shown to test anything.
- **A typed response interface is a second guard.** Declaring the result interface with
  `access_token`/`refresh_token` makes `tsc` reject a camelCase literal outright —
  free, and it fires before the runtime test does.
- **Check request bodies in the same sweep.** A DTO accepting `refreshToken` while the
  client posts `refresh_token` breaks session refresh with no error message; assert
  the accepted names against the client's request class, not just the response.

### ⚠️ An integration test must provision its own config — never inherit the dev's `.env`

A test that passes only because the developer's `.env` happens to define a required
setting is green locally and red in CI, where that variable does not exist. The
failure then masquerades as a product bug — a `400` on `sales/create` — while the
real defect is the test's hidden dependency on the ambient environment. Set every
required setting inside the test (`process.env.X = ...` in `beforeAll`, before the
module is compiled), then confirm against a hostile environment: empty database,
`--ci`, variable unset. Recipe and the CI-logging change that makes the cause
visible: `references/nestjs-wiring-and-runtime.md`.

### ⚠️ DI failures and route-syntax failures are invisible to the compiler

Two whole classes of error pass `tsc` and every unit test, then stop the service
from starting. Boot it and read the log. Details and fixes:
`references/nestjs-wiring-and-runtime.md`.

- **A provider needed by a service in another module must be `@Global()` (or that
  module must import it).** `Nest can't resolve dependencies of the SalesService
  (PrismaService, ?)` is the symptom. Making config/prisma modules `@Global()`
  removes the entire class of mistake.
- **Express 5 (NestJS 12) rejects `forRoutes("*")`.** It throws
  `Missing parameter name at index 1`. Use `forRoutes("{*splat}")`. Verify route
  patterns against `path-to-regexp` directly rather than assuming old syntax.

### ⚠️ Prisma rejects `\u{...}` escapes in schema defaults

`@default("\u{1F6D2}")` fails schema validation (`Invalid unicode escape
sequence`). Prisma accepts only four-digit `\uXXXX`; write emoji as a surrogate
pair (`"\uD83D\uDED2"`).

### ⚠️ Money endpoints need idempotency and ownership, not just auth

- Every endpoint that moves money takes an `Idempotency-Key`; a double-tap or a
  retried request must not create two orders.
- Auth alone is not enough: check the order's `merchantId` against the token's on
  **every** read and write, including receipts and manual confirm.

### ⚠️ Match FIFO by insertion row, not by the order id

When you reconcile a feed against a queue of same-amount pending orders, the
tie-break is the whole correctness of the feature. `ORDER BY created_at, id` looks
deterministic and is not: modern order ids are random hex, so two orders created in
the same millisecond are ordered by hash — effectively arbitrary. Two customers pay
the same amount seconds apart and the later one is credited first.

```sql
-- id is random: this tie-break is a coin flip inside a millisecond
ORDER BY created_at ASC, id ASC
-- rowid is monotonic: this is real insertion order
ORDER BY created_at ASC, rowid ASC
```

Sort the incoming batch by transaction time too, or FIFO only holds across polls and
breaks inside the batch that happens to contain both payments.

### ⚠️ Pick ONE money unit, and derive it from the client you actually use

The unit is **a property of the client library, not of the provider.** Two clients
for the same GoBiz feed disagree, so any rule of the form "GoBiz returns minor
units" is wrong somewhere:

| client | what it returns |
|--------|-----------------|
| `paygateme` Go feed (`toWholeRupiah`) | rupiah, divided down |
| `xirf/gobiz-merchant-sdk` (`getTransactions`) | rupiah — `rawGross >= 100000 ? round(rawGross/100) : rawGross` |

If your database stores rupiah while the client hands back minor units, nothing
errors; matching simply stops finding anything and the panel sits quietly showing
every order pending forever. The fix is not a guessed constant — it is: read the
client's normalisation line, then normalise on ingest, state the unit in the column
comment and in the API field name, and add one assertion to the self-check that
settles a non-round amount. Treat a passing suite that never exercised a non-round
amount as untested.

### ⚠️ A failing test may be pinning the bug — check which boundary it chose

When a test for a fix fails, the two candidates are "the code is wrong" and "the
test encodes the wrong invariant". The cheap discriminator is the boundary the
test picked. `ttlMs: -1` asserting `EXPIRED` encodes "an order that expired one
millisecond ago is dead" — a claim about a degenerate point rather than about the
feature. Realistic boundaries test behaviour: past the window (retired), plus the
case the fix creates (inside the window, still claimable).

Keep **both** assertions when you update the first. The second is the regression
test for the fix and is the one that fails if the tolerance is removed again; the
millisecond version only locks the old bug in place where it cannot be found.

### ⚠️ Verify a third-party SDK's real exports before writing its wrapper

Writing an integration module against a signature guessed from hosted docs produces
code that imports cleanly and fails on first call — or worse, is reported as done.
Install the package first, then read its actual surface, and only then write the
wrapper:

```bash
node -e "import('<pkg>').then(m=>console.log(Object.keys(m)))"
```

Keep the SDK confined to one adapter module so a signature that turns out wrong is a
single-file fix, and state in the summary which parts were verified against source
versus assumed from documentation. If the package never installed, say the
integration is unwired — do not report the surrounding build as complete.

**Then read for behaviour the docs do not advertise.** A signature check finds
`createDynamicPayment`; only the source tells you it *unconditionally* appends a
unique code with no flag to disable. When a convenience function bakes in behaviour
you cannot turn off, look for the lower-level primitive the same library exports
(the same package shipped `buildDynamicQris`, which does plain amount surgery) before
concluding the requirement is impossible. Absence of a flag is not absence of a path.

**Do not stack your own timer on a library that already throttles.** Passing
`force: true` to defeat the client's randomised cache window, on top of your own
interval, produces a request cadence more aggressive than the library author
intended — and an aggressive cadence is exactly what gets a merchant account
rate-limited. Likewise: never call the client's `startPoller`/`watch` helpers if you
run your own loop, or you ship two pollers against one credential. Pick one owner of
the cadence and keep the library's bounds.

Details, the verified contract table, and the checksum-variant probe:
`references/payment-sdk-runtime-contract.md`.

### ⚠️ An empty env var is not a blocker until you find its consumer

A handover note that says "`SERVER_KEY` is still empty — outgoing webhooks have no
HMAC" reads as a finding and sends the next session off inventing a key. Before
naming an unset variable as the blocker, grep what actually reads it:

```bash
grep -rn "<VAR>\|<exportedName>()" src/ | grep -v "config.js:"
```

If the only hits are the `env` load and an exported accessor nobody calls, the var
is dead config: the signing path derives its key from a per-subscriber column
instead, and the real hazard is the unused export, not the missing value. Filling it
in "for completeness" adds a second apparent source of truth for a secret nobody
verifies against. Fix the note — and prefer deleting the dead accessor over
generating a value nothing consumes.

The general form: **every "X is missing so Y is insecure" claim must survive one
grep for X's consumer.** The same discipline as scoping an absence claim to its
search (rule 12) applied in the opposite direction — do not manufacture a gap from
a variable nothing reads.

### ⚠️ Re-checking a checksum: strip it before re-appending the tag

A self-check that computes `crc(body + "6304")` against a payload that already ends
in `6304<crc>` is hashing the old checksum in and comparing against itself. Strip
the trailing 4 hex chars first, re-append the marker, then compute — otherwise the
verification fails for reasons that have nothing to do with the code under test, and
you burn a session chasing a non-bug.

When a checksum does not validate, **enumerate variants before concluding the payload
is corrupt** (CCITT-FALSE / XMODEM / KERMIT / MODBUS differ in init and reflection).
Report the mismatch as `unverified` with the variant table — it is equally consistent
with a one-byte decode error on your side, and guessing "the library is wrong" sends
you rewriting correct code.

### ⚠️ A failing test is twice as likely to be a wrong assertion as a wrong fix

When a test for new behaviour goes red, the candidates are "the code is wrong" and
"the test asserts a state I never actually established". Cheap discriminator: read
back the preceding lines of the test and name the state each one leaves behind,
before touching the implementation.

The three shapes that produce a red test where the code is right:

- **Asserting on a state you changed a step earlier.** Undo a marker, then assert
  the marker's *absence* is refused — but the row is now not marked, so write-off
  correctly succeeds and the assertion expecting `false` fails. Fix the assertion,
  not the guard.
- **Skipping a precondition the function checks.** `attachToOrder` guards on the
  order amount equalling the settlement amount; a fixture that creates a
  conveniently small order fails the attach for a reason that has nothing to do
  with the feature under test. Read the function's guards and satisfy each one.
- **Naming an unrelated error string.** `ok: false` with the *right* error is a
  pass; asserting the reason string makes the test brittle against a wording
  change without catching anything real.

Assert on state transitions and on `ok`, never on wording. And when a test does go
red, read it as a claim about your own model before a claim about the code.

### ⚠️ Proving a guard works requires breaking it — and the injected break must be the bug, not a stub

Reintroduce the defect, confirm the suite fails with the intended message naming
the invariant, then revert. Two ways this turns into theatre:

- **Inverting a guard in a way the original code still tolerates.** Restoring
  `res.data`-only parsing while the line still has a `res?.access_token` fallback
  changes nothing, the test stays green, and you record a red-to-green that never
  happened. Break the *decision* the code makes, not a fragment of the line it
  reads.
- **Stubs that mirror the shape you assumed rather than the one the provider
  sends.** A stub returning `{data: {...}}` makes a flat-response parser look like
  it works, and the bug survives into production where the real response is flat.
  Reconstruct the stub from a captured response, and when the two disagree, the
  capture wins.
- **A fixture that makes the assertion unfalsifiable.** This is the worst of the
  three, because the test is green and the red-to-green you perform confirms
  nothing. Two ways it happens: the fixture never produces the artifact at all
  (an order created with `qris: null` cannot render a QR no matter what the
  endpoint does), or the required config is a placeholder that fails for an
  unrelated reason (`QRIS_STRING=test` is rejected by the parser, so the render
  "fails" whether or not the guard under test exists). Break the guard, and the
  suite stays green.

  The tell is an injected break that produces **no** assertion failure. Treat that
  silence as a red flag about the test, not as a passing control. Two defenses,
  both cheap:

  - **Assert the precondition explicitly.** Before asserting the QR is withheld,
    assert it *is* served while the order is live. Same for any gate: prove the
    happy path renders the artifact, then prove the guard removes it.
  - **Make the test refuse to run on a placeholder.** Read the real value from the
    project's config at test time and `assert.ok(value && value.length > N,
    'required config missing')` at the top. A test that cannot start without real
    input cannot be green for the wrong reason.

  The general form: **a test that passes while the feature is unreachable is
  worse than no test**, because it converts an unverified claim into an apparent
  proof and buys the appearance of coverage for the one control that mattered.

### ⚠️ A payment service holding live money must be in version control — check before advising anything else

`git rev-parse --is-inside-work-tree` returning "not a git repository" on a
production panel holding a merchant credential and a live money DB is a
correctness finding, not a style note: one `rm -rf`, one bad edit, or one careless
`git clean -xdf` destroys the only copy, and the reconciliation queue it holds is
the shop's money ledger. No functional feature outranks it.

`.gitignore` the secrets before the first commit (`.env`, the session file, the DB
and its `-wal`/`-shm` sidecars, `node_modules`) — a first commit that sweeps the DB
in is a worse outcome than no commit, because the ledger is now in remote history
forever. Verify what the ignore actually excludes rather than assuming:

```bash
git -C <project> check-ignore -v .env session.json panel.db panel.db-wal
git -C <project> status --porcelain | grep -E '\.env|session\.json|\.db' && echo "SECRET WILL BE COMMITTED"
```

**Then read every file the first commit would sweep in — a `.gitignore` you wrote
from the file names you already knew does not find the file you forgot existed.**
Merchant integrations keep a *second* env file (`.env.qris`, `.env.production`) next
to the main one, and it is not automatically covered by a `.env` pattern. Those hold
the NMID and merchant ID: not a bearer token, but the live identity of a real
merchant account, and once pushed it is in history forever. Enumerate what git will
actually stage, and `cat` anything that smells like config before letting it in:

```bash
git -C <project> add -A && git -C <project> status --short
git -C <project> diff --cached --name-only | grep -E '^\.env|\.secret|creds' && echo "READ THESE"
```

Add the file to `.gitignore` and `git rm --cached` it — the file stays on disk,
untracked. Committing secrets and then gitignoring them leaves them in history;
`rm --cached` after the fact is the only thing that keeps the *next* commit clean.

**Then audit the secret file *names*, not just their modes.** A token leaked into a
filename (from a mangled shell redirect that wrote a command fragment as a path)
survives every `chmod 600` and is readable in any `ls` on the box, and the name is
what leaks, not the contents. When sweeping a service directory, look at the names:

```bash
ls -la <project> | grep '='          # '=' in a filename => suspect
```

Also note that a credential file under `/tmp` is not durable storage — it disappears
on reboot and on any periodic tmp cleaner, which silently invalidates the only copy
of a credential that has no refresh path. Never write a vault note or a handover
doc pointing at a `/tmp` path as *the* place a live credential lives; point at the
0600 file inside the project, or state plainly that the value exists only in the
operator's hands and must be re-issued.

### ⚠️ "What should I continue on project X" is an audit, not a recall

When the user asks what to carry forward on an existing service, the notes are a
hypothesis and the running system is the evidence — the most common answer is that
the work they think is unverified has already been proven, and the thing they believe
is done has a live hole. Run the battery before ranking anything, and report
`verified / unverified / blocked` explicitly so the ranking rests on proof.

**Do not merge "the code is done" and "the data is done" into one status.** They are
separate halves with separate proofs, and a summary that blurs them earns a
"maksudnya gimana?" round trip that costs more than the split would have. State each
half on its own line, and name the commit boundary explicitly — "2 commits, the
second not yet made" is a fact, "committed" is not.

Concretely, the checks that changed the recommendation in practice were: the live
health endpoint (not the process list — a poll worker can be alive and doing
nothing), the orders and settlements tables read directly (a `PAID` order with a
`claims` row is end-to-end proof; a `subs` table with zero rows means the whole
outbound path has no consumer), the credential file's expiry field, the auth gate
proved from outside (`curl` the public URL and expect `401`), the guard that is
supposed to stop brute force proved by its own counters (a fail2ban jail reporting
`Currently failed` > 0 is armed; one reporting `No file is currently monitored` is
decorative), and the test suite run as it stands.

Then rank by *unblocks the most*, and say plainly when a feature is already
load-bearing infrastructure with no user behind it — a webhook fan-out with a full
HMAC/dedupe implementation and zero subscribers is finished plumbing waiting for a
consumer, which changes what "finish this project" means. Recipe and the
interpretation table: `references/service-handover-audit.md`.

## References

- `references/qris-dynamic-from-static.md` — mint an amount-bearing dynamic QR from
  the static payload you already have; plus the notification-channel decision and the
  things to audit in any third-party gateway repo before deploying it.
- `references/dependency-recon.md` — registry checks that catch RC-tagged
  `latest`, ESM-only packages, and native-build dependencies before install.
- `references/payment-signal-matching.md` — matching a bank/QRIS notification to
  an order safely: unique amounts, replay keys, refusing ambiguity.
- `references/payment-sdk-runtime-contract.md` — verifying a payment SDK's real
  exports and runtime behaviour before writing a wrapper: amount normalisation,
  status casing, hidden built-in pollers, and probing the pure function.
- `references/settlement-queue-fifo.md` — the mode where the buyer forbids unique
  amounts: FIFO queue, durable claims, the two-invariants-in-one-statement guard,
  and how to prove which order a provider field actually identifies.
- `references/queue-writeoff.md` — closing a queue entry that is real money but not
  panel revenue: the marker column, the three filters that must all read it, why
  attach clears it and write-off refuses a matched row, and the migration test
  that a fresh in-memory DB cannot fail.
- `references/nestjs-wiring-and-runtime.md` — the failures that appear only when the
  service boots: DI visibility, Express 5 route syntax, and how to verify
  database constraints without raising a false alarm.
- `references/payment-portal-auth.md` — authenticating against a merchant dashboard
  with no official API: choosing phone OTP vs password vs pasted cookie based on
  what the buyer actually holds, one-shot login CLI to a 0600 token file, and
  verifying (not inheriting) the upstream auto-refresh claim.
- `references/panel-exposure-private-first.md` — deciding whether an operator panel
  holding a live merchant session goes public: the private-first default, what nginx
  `auth_basic` + injected header actually buys you, why basic auth is neither CSRF
  protection nor authorization, the FIFO ambiguity a gate does not fix, and the deploy
  traps (variable scoping, htpasswd group causing 500, a fail2ban jail that never read
  its log, CDN edge IPs getting banned, a mangled `.env` line that renames the
  database file and its WAL sidecars).
- `references/generated-artifact-display.md` — showing a QR/barcode/receipt in an
  operator panel: the server-side settle gate, the list-flag-vs-payload split, the
  two-absent-values trap behind "the QR disappears", and how to prove the expiry
  branch without faking it.
- `references/audit-trail-and-operator-attribution.md` — what a payment panel must
  log that its transaction table cannot: an append-only operator-action table, the
  unmatched-settlement reason vocabulary, why `remoteAddress` is not an identity,
  and how the trail becomes the only source of truth for "was this match made by
  hand" — the predicate that gates the release of a hand-made attach.
- `references/vendoring-unpublishable-deps.md` — rescuing a dependency installed by
  path outside the project: diagnosing a JSR-only package with gitignored build
  output, vendoring the built artifact with the upstream SHA pinned, stripping
  lifecycle scripts that `file:` installs run, and proving it by deleting the
  source directory before `npm ci`.
- `references/upstream-credential-health.md` — making a dead merchant session
  visible instead of silent: the health state machine, the `verified` flag that
  separates "restarted" from "never worked", log throttling, and the operator badge
  plus cooldown-aware retry button.
- `references/service-handover-audit.md` — auditing a live money service before
  advising what to continue: the evidence battery, how to read each result, and how
  to rank findings into a short ordered list.
