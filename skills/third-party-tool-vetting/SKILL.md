---
name: third-party-tool-vetting
description: Use when vetting an unfamiliar tool, CLI, SaaS link.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [security, supply-chain, vetting, recon, install]
    related_skills: [blackbox-web-security-assessment, untrusted-code-sandboxing, vps-project-deployment-isolation]
---

# Vetting a Third-Party Tool Before Adoption

## When to Use

User pastes a link/name of an unfamiliar product, CLI, SaaS, or package — often quoted from a comment,
DM, or ad — and asks to check it, analyze it, or install it. The ask is an **adoption decision**: is the
vendor real, is the artifact safe to run on this host, what do I actually get. It is NOT a pentest:
no authorization gate applies; everything is public read-only recon plus a local install.

Recurring for Meow Labs (founder gets tool links constantly). Deliver a verdict, not a research dump.

## Output shape the user expects

1. **One-line verdict first** (real product / unclear / risk), then evidence.
2. Buckets, labeled explicitly: **verified** (with the command output that proved it) / **unverified**
   (say what would prove it) / **risk** / **blocker**.
3. Close with 2–4 concrete options and one recommendation. If login/activation blocks progress, say
   exactly which command finishes it and hand the user the interactive part (device code, invite).
4. Indonesian casual for Arya; keep commands, endpoints, error strings, versions verbatim.

## Phase 1 — Find the entity behind the domain (never the domain age alone)

The domain age is a fact about registration, not about trust. Ask instead: **which real entity owns this,
and does its footprint match the pitch?** Chain of evidence, in order:

- DNS + whois + TLS cert dates → registration date, registrar, NS, hosting.
- The **artifact's own metadata** is the strongest link: an npm `maintainers[].email` domain, a package
  `repository.url`, an installer host. Those names are what you then verify.
- Verify that entity independently: GitHub org (`created_at`, repo count, stars, sibling repos in the same
  product line), funding/company registries, founder names, a main OSS repo with real history.
- Statement fitness: does the marketing claim match what the artifact shows (endpoints, templates, quotas
  from `--help`)? Mismatch is a finding; a match raises confidence.

See `references/artifact-recon-commands.md` for the exact command battery.

## Phase 2 — Read the artifact before executing it

`npx <pkg>@latest` and `curl … | sh` execute third-party code on the host. Before running either:

1. Pull registry metadata and read the **`scripts`** block: `preinstall`/`postinstall`/`prepare` run code at
   install time; their absence means resolution alone executes nothing. Also read `bin`, `deps`, `engines`.
2. Download the tarball, `tar tzf` it, and read the entry point plus every network-touching module:
   telemetry, credentials/token storage, auth, subprocess spawning.
3. Grep the package for every outbound host: `grep -rhoE 'https?://[a-zA-Z0-9./_-]+' pkg | sort | uniq -c | sort -rn`.
   Hosts unrelated to the vendor are the thing to explain.
4. For a shell installer, **read the whole script first** — check that it verifies a checksum, where it
   installs, and whether it needs root.

Report what the artifact does with the user's data: telemetry fields (and the opt-out env vars), any local
identifier or username transmitted, where credentials are written and with what file mode.

## Phase 3 — Map the real product surface from public artifacts

Cheaper and more accurate than the marketing page:

- Try the API's own spec: `GET <api-host>/v1/openapi.json` (also `/openapi.json`, `/api-docs`). A public spec
  gives the whole endpoint list, and an unauthenticated data endpoint is only discovered this way.
- Fetch the SPA bundle and grep it: the `…/js/app.js` path from the homepage HTML, then
  `` grep -oE '`?/v1[a-zA-Z0-9/_.:${}-]*' `` and `` grep -oE 'https://[a-z0-9.-]+' `` — the second finds
  sibling hosts the pitch never mentions (`dashboard.`, `api.`, `docs.`). Probe them.
- CLI `--help`/`help` output usually states the real product limits (instance size, quota, defaults). Quote it.
- Probe discovered endpoints unauthenticated, one status code per endpoint. A uniform
  `401 {"error":{"code":"unauthenticated"}}` is a good sign; missing auth on a data route is a finding.

## Phase 4 — Install safely on a shared host

- Install into a contained, reversible path (`~/.local/bin`, or the tool's own `*_INSTALL_DIR` env var).
  Never `/usr/local/bin` or root-owned locations without a reason.
- **Verify the checksum yourself** against the publisher's `SHA256SUMS` — and state the limit honestly:
  a checksum served by the same host as the binary detects a corrupt or partial deploy, not a malicious
  publisher. Do not call it independent verification.
- Weigh host footprint BEFORE installing: a thin remote-control client (SSH to someone else's machine) costs
  nothing locally; anything that builds, runs containers, or compiles workloads does not belong on the shared
  production VPS. Say which one this is.
- Record the install path and the single command that removes it.

## Phase 5 — Headless authentication for CLI tools

A browser loopback OAuth flow (RFC 8252 / PKCE with a `127.0.0.1/<port>` callback) **cannot complete on a
headless server**: the browser must be on the same machine as the callback. Do not run it and wait.

- Read `login --help` first for `--device`, `--no-browser`, `--provider`, `--invite-code`, or an API-key env var.
- Device-code flow: run it as a **background** process logging to a file, read the code from the log, hand the
  code and URL to the user, and only poll after they confirm. The process keeps polling meanwhile.
- After sign-in succeeds, check for a gate the vendor did not advertise (invite/waitlist/quota) and report it as
  a blocker with the exact command that clears it — `login --invite-code <CODE>` style.

## Marketplace and distribution pitches

A different ask: the sender wants the user to **publish** an artifact (skill, plugin, template, package)
on their marketplace. There is nothing to install, so the adoption decision is distribution-and-effort,
and the guardrail is how much work the pitch is allowed to cost.

1. **Verify the traffic on the vendor's own pages, not in the email.** Landing page, `/sell`, `/learn`,
   and `/about` routinely quote different numbers. Three disagreeing figures on one domain means the
   headline is unverified — say so and quote the spread.
2. **Turn "creators earn" into arithmetic from their own published best-sellers**: price × installs ×
   creator share. A marketplace whose showcased winner earned a few hundred dollars lifetime is
   pre-market; treat it as reach and backlink, not revenue.
3. **Read the mechanics that set effort**: fee split, exclusivity, payout rail, review turnaround, and
   the delivery format (uploaded zip vs run-through-MCP). Free listing changes the calculus — near-zero
   cost means near-zero work is justified.
4. **Gate the effort on verified distribution.** ~30 minutes of packaging is fine speculatively;
   porting/repackaging multiple artifacts is not, until the channel shows real buyers.
5. **Audit publication readiness before packaging.** A stale or self-contradicting repo makes the first
   impression the last one; consistency review comes before formatting. See `repository-architecture-review`.
6. **Do not let the pitch's wording define the scope.** "Repackage for 20+ agents" usually reduces to
   shipping the one portable core, not every file the user owns.

## Pitfalls

- **Repeating a marketplace's headline reach as fact.** Cross-check the vendor's own pages first; a
  single number from the pitch email is a marketing claim, not traffic data.
- **Doing heavyweight repackaging for an unproven channel.** The cost of listing is near zero, so the
  rational effort cap is near zero too; prove demand before porting content.
- **Never repeat a scam-score site's verdict as your own.** Aggregators score on domain age and similar
  heuristics, so every newly launched product is flagged high-risk. Check the owner's footprint instead, and
  when the score is contradicted, name the heuristic that produced it.
- **A private/404 source repo is a trust boundary, not proof of fraud.** Open-core products commonly keep the
  client closed. Report "closed binary, no independent build verification, trust the vendor" — a risk with a
  stated mechanism, not an accusation.
- **`404` on the marketing host says nothing about the API host.** The app route space and the docs/API host are
  separate; probe the documented host and paths before concluding an API is closed.
- **A JS-rendered site answers with the same status AND the same byte count for every route.** When `/`, `/pricing`,
  `/docs` all return `200` at an identical small size, you have the SPA shell: page existence is UNVERIFIED, and
  any pricing/plan claim must be marked unverified rather than quoted from a third-party article.
- **Checksums and signatures that travel with the artifact are integrity, not authenticity.** Verify them anyway
  (they catch real deploy breakage) but never describe them as independent verification.
- **A server-side secrets vault widens the blast radius.** When the product stores the user's API keys and injects
  them into every instance, name it as a structural reason not to put production credentials in it.
- **Loopback and device-code flows are different animals.** Don't burn a turn running a browser flow to see what
  it prints on a host with no browser: read `--help` and pick the device flow.
- **State what a probe did NOT prove.** A live API, a working CLI, a verified checksum and a matching vendor
  identity still leave "is the product any good" open — keep the verdict scoped to what was measured.

## References

- `references/artifact-recon-commands.md` — copy-paste command battery: entity/DNS/whois/TLS, npm registry and
  tarball inspection, SPA bundle and OpenAPI surface discovery, installer + checksum verification, background
  device-code login.
