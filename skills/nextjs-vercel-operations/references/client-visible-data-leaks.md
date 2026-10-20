# Hiding model / provider identity from end users

Use when the requirement is "a user must not be able to tell which model, or which upstream
API, this app uses." Applies to any app that proxies to an LLM behind its own domain.

## Principle: audit what reaches the browser, not what is in the source

The source may name the provider in a hundred places; what matters is the set of bytes a user
can obtain. Enumerate every channel *before* editing anything:

1. **Client bundle** — strings inlined at build time (`NEXT_PUBLIC_*`) and any literal that
   lands in `.next/static/**`. Grep the *built output* for provider tokens, model IDs, and
   upstream hostnames — not the source tree.
2. **API response bodies** — every field of every route's success *and* error JSON.
3. **Error paths** — every `catch` that returns `{ error: msg }` (see below).
4. **Source maps** — a shipped `.map` hands over the original source.
5. **Direct backend reads from the client** — a client-side SDK reading a collection/table can
   expose fields the API carefully hid; check the DB rules, not just the route.
6. **Repo visibility** — decide this first: a private repo means the threat model is
   runtime-only and no source-level work is needed. `GET /api.github.com/repos/<owner>/<repo>`
   returning `404` for an authenticated call = private.

## The canonical leak: response metadata echoes the real model

A proxy usually returns `usage` (and sometimes `model`) in the completion response, naming the
actual upstream model. Any route that forwards the provider's response object leaks it to
DevTools → Network → Response.

**Rule: return only the fields the client consumes.** Strip `usage` / `model` / provider IDs
from the response; keep them in server-side logs. Audit *every* route that returns a provider
object, not just the generation route — continuations and side routes leak too.

## Every `{ error: msg }` is a leak channel

Raw upstream and runtime error text carries env var names, provider names, upstream URLs,
filesystem paths, and shell commands. Enumerate ALL of them, then route through one gate:

```bash
# find every raw-error return across the API surface
grep -rn "error: msg\|error: error\|error: e\.message\|String(error)" app/api
```

Centralize rather than sanitize site-by-site: one function (e.g. `toClientErrorMessage(e)`)
that maps known failure classes to fixed user-facing copy and falls back to a generic line for
everything else. One function to test, one place a new route must call.

Sanitize the **client** side too. A UI `analyzeError` / `catch` that renders the server's
string will happily print whatever the server sent — map to fixed copy there as well.

## The error-message tension — resolve it this way

"Show the server's specific message" (so failures are diagnosable) and "never leak internals"
are both correct. Resolution: the server sends **specific but sanitized** copy — distinct
messages per failure class (unreachable / overloaded / rejected / insufficient credits) that
name no env var, provider, model, or URL. The client surfaces that copy. Neither the raw
provider string nor a single generic line is acceptable.

## What cannot be hidden — state it, do not pretend

- **Sibling domains.** If the API origin shares a brand with the app domain, the origin is
  guessable. A separate proxy hostname is the only real fix.
- **Response shape and timing.** Reasoning vs non-reasoning, latency profile.
- **An authenticated user probing repeatedly.** Mitigate with rate limits, not secrecy.

Say these out loud when reporting, so the user does not believe the problem is fully closed.

## Verification

1. **Leak harness.** Feed N real upstream error shapes — connection refused, overload,
   invalid key, budget exceeded, and a message that itself contains the model name — through
   *both* the client-facing mapper and the route path. Assert none of the forbidden tokens
   appear in any output. Include odd inputs (`null`, `{}`, a 5000-char string) so a mapper that
   only handles `Error` does not pass by accident.
2. **Bundle scan.** `grep -o` the built `.next/static/**` for each provider token / model ID /
   upstream host. A brand string that is the user's own domain or email is **not** a leak —
   read the surrounding context before flagging it.
3. **Scan the shipped bundle, not a stale local one.** Local and prod chunk hashes differ
   (build-time env inlining), so resolve the real chunk from the prod webpack runtime — see the
   deploy-verification pitfalls in SKILL.md.

## Companion finding: credentials committed to tracked files

An audit of "what can a user learn" should also grep for credential patterns in *tracked*
files (docs and READMEs are the usual offenders):

```bash
grep -rnE "(api[_-]?key|secret|token|password)[[:space:]]*[:=][[:space:]]*['\"][A-Za-z0-9_-]{16,}" --include='*.md' .
git ls-files | xargs grep -l "<candidate>"   # confirm it is TRACKED, not merely on disk
```

A secret in git history is not removed by deleting the file — it must be **rotated**. Report it
as its own item with the rotation options and let the user decide; do not silently rewrite
history.

### Scan the whole block, not just the key you were told about

An "example `.env`" in a doc is a prime spot for several live secrets at once. When asked to remove
one key, read the surrounding block and redact **every** real value in it — a second credential one
line away (another provider's key in the same sample) is easy to miss and just as exposed. Do the
whole pass in a scripted replace so the real values never appear in the diff you print; verify by
re-scanning the file for each pattern afterwards and reporting `no secrets left`.

### Classify the scan hits before reporting them

A pattern scan for credentials over tracked files returns benign matches. Check each one and say
which it is instead of reporting a count:

- **Public by design** — a Firebase **Web** API key (or similar browser-embedded client key) is
  served to the browser on purpose; its safety comes from backend rules, not from secrecy. Not a leak.
- **Placeholder** — a value like `\n...` or `your-key-here` inside a doc. Not a leak.
- **Live secret** — a real-looking value in a tracked file. Rotate.

State the classification per hit, and confirm `.env` is git-ignored (`git check-ignore -v .env`)
so the real environment file is out of the repo.
