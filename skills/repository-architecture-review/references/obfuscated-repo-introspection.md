# Reading a repo whose key files are obfuscated

Reviewed repos in this class ship the interesting logic as `javascript-obfuscator`
output: string-table lookups (`_0x4fd4b5`), arithmetic-encoded offsets, RC4
decoders. Size is the tell — a 425 KB `login.js` next to a 32 KB `server.js`.

Static reading has a hard ceiling there. Identifier names survive
(`GOBIZ_REQUEST_OTP_URL`, `grant_type`, `otp_token`), so you learn the *shape*,
but a URL assembled from nine decoded string fragments is unrecoverable without
running the decoder. That is fine: **you do not need the source, you need the
request.**

## Rule

Recover behavior by **executing the code with the network dependency stubbed**,
then read the captured calls. Never report a guessed signature as verified, and
never conclude a capability is absent from one file.

## Recipe

**1. Find surviving identifiers.** These tell you the API surface even when the
values are encoded:

```bash
grep -rniE 'otp|verify|request_code' --include='*.ts' --include='*.js' src/
grep -oE 'GOBIZ_[A-Z_]+' login.js | sort -u      # exported constant names
```

**2. Install the dependency in the clone.** The probe resolves modules relative to
the target's own directory, not your scratch dir:

```bash
cd /path/to/clone && npm install
```

**3. Stub the HTTP client into `require.cache` before requiring the target.** Use a
`Proxy` so any method name (`get`/`post`/`put`/`request`/`create`) is caught —
obfuscators rename them, and a fixed key list silently captures nothing:

```js
const AXIOS = require.resolve('axios', { paths: ['/path/to/clone'] })
const captured = []
const fake = new Proxy({ defaults: { headers: { common: {} } },
                        interceptors: { request: { use() {} }, response: { use() {} } } }, {
  get(t, p) {
    if (p in t) return t[p]
    if (p === 'create') return () => fake
    if (['get','post','put','patch','delete','head','request'].includes(p))
      return (...args) => { captured.push({ fn: p, args })
                            return Promise.resolve({ status: 200, data: {}, headers: {} }) }
  },
})
require.cache[AXIOS] = { id: AXIOS, filename: AXIOS, loaded: true, exports: fake }
```

**4. Answer the prompts.** Stage one only advances to stage two if the stub returns
the field stage one was waiting for — read the error text to learn its name:

```js
if (url.includes('/login/request'))
  return Promise.resolve({ status: 200, data: { data: { otp_token: 'X', expires_in: 720 } }, headers: {} })
```

**5. Run under a PTY.** Piped stdin is not delivered to `readline.question`, so the
second prompt silently receives nothing and you capture one call instead of two:

```bash
(printf '081234567890\n'; sleep 3; printf '123456\n'; sleep 5) \
  | script -qec 'node probe.cjs' /dev/null
```

**6. Dump to a file, not stdout.** Overwriting `process.stdout.write` or console in
the probe swallows your own report — the classic symptom is a successful run with
an empty capture file.

**7. Probe non-interactive exports directly — no PTY needed.** Background/lifecycle
code is often just an exported async function. Require the module with the stub
installed, call it, read the capture:

```js
const sm = require('/path/to/clone/sessionManager')
report.exports = Object.keys(sm)                 // tells you the whole surface
const r = await sm.refreshSession()              // no prompt, no stdin
// -> report.callsAfterRefresh is the ground truth for the refresh grant
```

This is how a "set-and-forget / auto-refresh every 6 hours" README claim gets
settled: exercise the function and capture the request. An `isExpired(session)`
probe on a hand-built object is worth two lines and tells you whether the module
reads a stored `expires_at` or tries to decode the token.

**8. NEVER point a probe at the live credential file.** Exported writers
(`saveSession`, `refreshSession`) **rewrite the file**, and they do not necessarily
preserve its schema — a JWE-bearing `{token, refresh_token, merchant_id, savedAt}`
session came back as `{access_token, cookie, updated_at}`, dropping half the keys.
Point the probe at a copy, then prove the original is untouched:

```bash
cp ~/app/session.json /scratch/clone/.SESSION_FILE.json   # or whatever it reads
sha256sum ~/app/session.json   # before and after the probe run
```

Skipped because "it's just a probe", this is how a vendor's writer silently
reshapes the session your production panel reads and the next boot finds an
undefined token.

## Reading the result

Captured args are the ground truth. The stub's own response shape should be
minimal (`data: {}`) so the target's own error message reveals which field it
expected to find — that is how you learn `otp_token` before you can fake it.

Claims the capture supports: exact URL, exact JSON payload, header set, field
names, and which values the target transforms before sending (e.g. a leading zero
stripped from the phone number, a `+62` prefix split into a separate field).

Claims the capture does **not** support: anything the target did in a branch you
did not trigger, and any background refresh loop — an unread refresh timer is the
usual gap, so report it as unverified rather than inheriting the upstream README's
"set-and-forget". Step 7 closes that gap when the lifecycle work is a callable
export; when it is only a `setInterval`, say so rather than implying you read it.

## "Clone this repo exactly" means substitute, not copy

When the ask is to make your own system match a vendor repo, evaluate the
credential/auth path separately from the feature path — they have opposite
defaults.

- **Port, don't vendor, the obfuscated credential path.** Same rule as above,
  restated because the pressure is higher here: shipping 800 KB+ of unreadable
  code into a money-handling repo trades an audit gap for convenience. Port the
  captured request shapes into plain code you can read and test.
- **Audit the feature path against your own invariants and name the regressions.**
  A vendor's dedupe map in RAM loses every mark on restart where your DB claim
  table survives; an open `cors()` plus a key accepted from `?api_key=` writes the
  secret into browser history, Referer and access logs; an `app.all` handler that
  creates state on GET is a CSRF-driveable simple request; a public status
  endpoint that calls the upstream burns someone's token quota if its id leaks;
  `req._router.handle()` is an Express internal that dies on v5; zero test files
  means every claim is a README claim.
- **State the verdict explicitly.** Say which files you would substitute, which
  of your own pieces are stronger than theirs and therefore stay, and that the
  licence (check it — MIT permits verbatim, copyleft makes it a decision) does not
  settle the quality question. "Don't clone" without the named replacements is
  not an answer the user can act on.

## Pitfalls

- **Grep the whole tree before declaring a capability absent.** A feature can be
  missing from the SDK under review and present in a sibling repo the user already
  mentioned. Scope the absence precisely ("this package has no OTP path") and say
  which grep backed it; never round up to "the platform doesn't support it".
- **Do not port the obfuscated file.** Port the captured request shape into your
  own plain code. The upstream helper (`sessionManager.js`, 464 KB, RC4) stays out
  of your repo — unreadable code in the credential path is not a dependency, it is
  an audit gap.
- **Separate what you recovered from what you inferred.** The two captured requests
  are evidence; the refresh strategy behind the marketing claim is not. Write the
  unverified part as a comment naming it as unverified, so the next reader deletes
  the claim when they learn better rather than inheriting it.
