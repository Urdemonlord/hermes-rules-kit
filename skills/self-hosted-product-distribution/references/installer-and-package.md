# Installer and package recipes

Concrete shapes for the rules in `SKILL.md`. Node + Express + `node:sqlite` is
the worked example; the structure transfers to any Node service with a SQLite
file, a session credential, and an HMAC secret.

## Proving distributability before writing an installer

The question is "can this install without the registry?", and the answer lives in
the lockfile, not in whether a `vendor/` directory exists:

```bash
node -e "
const l = require('./package-lock.json').packages;
const reg = Object.keys(l).filter(k => k && (l[k].resolved || '').startsWith('https://registry'));
console.log('lock entries:', Object.keys(l).length, ' from registry:', reg.length);
"
npm ls <vendored-pkg> --depth=0        # '-> ./vendor/...' is offline; a version number is not
grep -RIn --exclude-dir=node_modules --exclude-dir=.git '<vendored-pkg>' src package.json
```

A `file:` dependency in `package.json` plus a non-URL `resolved` in the lockfile
is the offline case. One registry dependency among three is enough to make the
package internet-dependent; count them, don't eyeball the list.

## Headless vs interactive auth — check, don't assume

Read the vendored SDK's own code before designing the installer around a login
flow. The type declarations and the shipped bundle can disagree:

```bash
grep -oE "login_type[^,;}]{0,40}|grant_type[^,;}]{0,30}" vendor/<pkg>/dist/index.js | sort -u
grep -nE "email|password|otp|cookie" vendor/<pkg>/dist/index.d.ts | head
grep -rn 'authMethod\|email:\|password:' src/            # what your own code accepts
```

If the SDK hardcodes password login and the app already accepts
`email + password`, the installer is fully non-interactive and the OTP path
becomes the documented exception. When the app implements an OTP flow directly
against the vendor API, say so explicitly — the SDK lacking it does not mean the
integration lacks it.

## Staging the build outside the live tree

`npm ci` removes `node_modules` before installing, so a packaging script run in
the project directory can take a running service's dependencies away:

```bash
rm -rf /tmp/pkg && mkdir -p /tmp/pkg
git add -A                                  # or the unstaged installer never lands in the probe
git ls-files -z | tar --null -T - -cf - | tar -xf - -C /tmp/pkg
cp install.sh build-pkg.sh /tmp/pkg/        # new files the index does not have yet
cd /tmp/pkg && ./build-pkg.sh
```

## The secret file

```bash
ENV_FILE="$DIR/.env"
ENV_TMP="$(mktemp "$DIR/.env.XXXXXX")"
trap 'rm -f "$ENV_TMP"' EXIT
(
  umask 077                                 # subshell: does not leak into a sourcing caller
  cat > "$ENV_TMP" <<ENVEOF
GOPAY_EMAIL=$EMAIL
SERVER_KEY=$(gen_secret)
PANEL_TOKEN=$(gen_secret)
HOST=127.0.0.1
PORT=$PANEL_PORT
DB_PATH=$DIR/panel.db                       # absolute, or a second install opens an empty DB
TOKEN_FILE=$DIR/session.json
ENVEOF
)
mv -f "$ENV_TMP" "$ENV_FILE"                # same filesystem => atomic
trap - EXIT
```

Preserving existing secrets on re-run, in Python because `sed` with an arbitrary
secret value invites quoting bugs:

```bash
KEY1=PANEL_TOKEN KEY2=SERVER_KEY python3 - "$ENV_TMP" "$ENV_FILE" <<'PY'
import os, sys, pathlib
tmp, old = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
keys = (os.environ['KEY1'], os.environ['KEY2'])
prev = {}
for line in old.read_text().split('\n'):
    for k in keys:
        if line.startswith(k + '='):
            prev[k] = line.split('=', 1)[1]
out = []
for line in tmp.read_text().split('\n'):
    for k in keys:
        if line.startswith(k + '='):
            if k in prev:
                line = f"{k}={prev[k]}"
            del prev[k]
            break
    out.append(line)
tmp.write_text('\n'.join(out))
PY
```

## A leak gate that does not flag itself

Build the scan list from fragments, so the literal never appears in the shipped
source:

```bash
LEAKS=(\"$(printf '%s%s' ID10264699225 G24)\" \"$(printf '%s%s' G97387263 5)\")
for leak in \"${LEAKS[@]}\"; do
  hits=\"\$(grep -rlF -- \"$leak\" \"$PKGDIR\" 2>/dev/null || true)\"
  [ -n \"$hits\" ] && die \"REFUSING TO SHIP: $leak in \$(printf '%s\\n' \"$hits\" | sed \"s|$PKGDIR/|        |\")\"
done
```

Anchor on the real values. A shape-based pattern (`G[0-9]{9}`,
`ID[0-9]{12,}`) flags synthetic fixtures too and every release then refuses to
build on honest data.

Prove it catches a real leak before trusting it:

```bash
sed -i 's/<synthetic-id>/<real-id>/' <some-shipped-test>.mjs
./build-pkg.sh          # must refuse, and name that file
git checkout -- <file>  # or restore from the clean copy
```

## Recomputing a checksum in a fixture

A pasted payload can be structurally invalid and still parse, so every
parse-shaped assertion passes on garbage. Recompute the derived value:

```js
const crc16 = (s) => {                 // QR/EMV CRC-16/CCITT-FALSE
  let c = 0xffff
  for (const b of Buffer.from(s, 'utf8')) {
    c ^= b << 8
    for (let i = 0; i < 8; i++) c = (c & 0x8000) ? ((c << 1) ^ 0x1021) & 0xffff : (c << 1) & 0xffff
  }
  return c.toString(16).toUpperCase().padStart(4, '0')
}
const body = FIELDS.map(([t, v]) => t + String(v.length).padStart(2, '0') + v).join('')
export const STATIC_QRIS = body + '6304' + crc16(body)
```

Verify the payload actually constrains the code under test: build a dynamic QR
from it, confirm the checksum validates and the amount tag appears. A fixture the
builder never rejects proves nothing about the builder.

## Permission ordering in the packaging script

`find -exec chmod` after a targeted `chmod 755` wins, because it runs later:

```bash
chmod 755 \"$PKGDIR/install.sh\" \"$PKGDIR/build-pkg.sh\"
find \"$PKGDIR\" -type f -exec chmod u=rw,go=r {} +      # <-- strips the +x
```

Normalise first, target last, and leave dependency trees alone — they carry
legitimate executable content (`.bin/` shims) that a blanket walk breaks:

```bash
find \"$PKGDIR\" -type f -exec chmod u=rw,go=r {} +
find \"$PKGDIR\" -type d -exec chmod u+rwx,go+rx {} +
chmod 755 \"$PKGDIR/install.sh\" \"$PKGDIR/build-pkg.sh\"   # AFTER the walks
find \"$PKGDIR/node_modules\" -type f -perm /u+x -exec chmod a+r {} +
```

The only reliable check is to run the extracted tarball:

```bash
tar tzf dist/<pkg>.tar.gz | grep -E 'install.sh|\\.bin/'
tar xzf dist/<pkg>.tar.gz -C /tmp/buyer && cd /tmp/buyer/<pkg> && ./install.sh --help
```

## systemd unit from a template

```ini
[Service]
WorkingDirectory=$DIR
ExecStart=$(command -v node) src/server.js
Restart=on-failure
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$DIR          # the app writes only here; pair with ProtectSystem
MemoryMax=1G
```

Write the unit, print the `systemctl daemon-reload && systemctl enable --now`
line, and do not run it: enabling the service is the buyer's consent step, and
booting it for them can start polling an account they did not intend to use.

## The install check (extract → install → boot → restart → clean up)

The only evidence that speaks to the buyer's first ten minutes. Extract the real
tarball rather than testing the source tree, so packaging defects are in scope.

```bash
#!/usr/bin/env bash
set -uo pipefail
cd \"$(dirname \"$0\")\"
TMP=\"$(mktemp -d)\"

# Track every server this starts. Killing only the last recorded pid leaks an
# orphan that still holds the port; the NEXT run is then served by it and reads
# 404, which looks exactly like \"the panel does not boot\".
PIDS=()
cleanup() {
  for p in \"${PIDS[@]:-}\"; do [ -n \"$p\" ] && kill \"$p\" 2>/dev/null; done
  sleep 1
  for p in \"${PIDS[@]:-}\"; do [ -n \"$p\" ] && kill -9 \"$p\" 2>/dev/null; done
  rm -rf \"$TMP\"
}
trap cleanup EXIT

pass=0; fail=0
ok()  { printf '  \\033[32mok\\033[0m   %s\\n' \"$1\"; pass=$((pass+1)); }
bad() { printf '  \\033[31mFAIL\\033[0m %s\\n' \"$1\"; fail=$((fail+1)); }
check(){ if [ \"$1\" = \"$2\" ]; then ok \"$3\"; else bad \"$3 (got '$1', want '$2')\"; fi; }

mkdir -p \"$TMP\" && cd \"$TMP\"
tar xzf \"$(dirname \"$0\")\"/../dist/<pkg>.tar.gz
cd <pkg>

./install.sh --email user@example.com --password 'S3cret!' --dir \"$TMP/install\" --no-service >/dev/null 2>&1
check \"$?\" \"0\" \"installer exits 0 on success\"

I=\"$TMP/install\"
check \"$(stat -c %a \"$I/.env\")\" \"600\" \".env is not world-readable\"
check \"$(grep -c '^PANEL_TOKEN=..\\{60,\\}' \"$I/.env\")\" \"1\" \"PANEL_TOKEN is generated\"
check \"$(grep '^DB_PATH=' \"$I/.env\" | cut -d= -f2)\" \"$I/panel.db\" \"DB_PATH is absolute\"
check \"$([ -f \"$I/src/server.js\" ] && echo yes)\" \"yes\" \"the source is actually copied in\"
check \"$([ -e \"$I/.env.qris\" ] && echo leaked || echo clean)\" \"clean\" \"dev credentials not shipped\"
```

Assert the secrets survive a re-run, because swapping them breaks every receiver
the buyer already configured:

```bash
T1=$(grep '^PANEL_TOKEN=' \"$I/.env\" | cut -d= -f2)
./install.sh --email user@example.com --password new --dir \"$I\" --no-service >/dev/null 2>&1
T2=$(grep '^PANEL_TOKEN=' \"$I/.env\" | cut -d= -f2)
check \"$([ \"$T1\" = \"$T2\" ] && echo same)\" \"same\" \"PANEL_TOKEN survives an upgrade\"
```

Boot the installed panel with an unusable merchant credential — the whole point
of a non-interactive installer is that setup is still in progress:

```bash
sed -i 's/^PORT=.*/PORT=4899/' \"$I/.env\"
setsid node \"$I/src/server.js\" > \"$TMP/boot.log\" 2>&1 &
PIDS+=(\"$!\")
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1; curl -sf -m 2 http://127.0.0.1:4899/healthz >/dev/null 2>&1 && break
done
check \"$(curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:4899/)\" \"200\" \"serves its UI\"
check \"$(stat -c %a \"$I/panel.db\")\" \"600\" \"the data file is private (it holds secrets)\"
```

Restart persistence, waiting for the port to actually be released — `kill` is
async, and a replacement started too early fails to bind and exits 1 into a log
nobody reads:

```bash
kill \"${PIDS[0]}\" 2>/dev/null
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -sf -m 1 http://127.0.0.1:4899/healthz >/dev/null 2>&1 || break
  sleep 1
done
setsid node \"$I/src/server.js\" >> \"$TMP/boot.log\" 2>&1 &
PIDS+=(\"$!\")
```

Then prove the check can fail — remove the payload copy and confirm the artefact
and boot assertions go red — and restore it.

**Run it three times in a row before believing it.** One green run is
indistinguishable from a working installer whose orphan processes were cleaned up
by hand, and orphan reuse fails deterministically on run two onward.

## Upgrading an install that came from the tarball

The re-run above is the cheap half: same directory, same depth, source and
destination at the same level. The buyer's upgrade has neither property — the
source is a freshly extracted tarball and the destination is a directory someone
installed weeks ago.

```bash
# second artifact, simulating the next release
tar xzf "$NEXT_TARBALL" -C "$TMP/next"
( cd "$TMP/next/<pkg>" && ./install.sh --email … --dir "$I" --no-service )
```

Install from the extracted artifact **twice** before you call the path covered.
The defect class below only appears on the run where the destination already
holds what the source is about to write.

### `cp` cannot replace a symlinked dependency

`node_modules/@scope/pkg -> ../../vendor/pkg` is how an offline package satisfies
a dependency the registry does not carry. Copying the payload with `cp -r`
follows the link on the source side and then refuses the destination:

```
cp: cannot overwrite non-directory '<DIR>/node_modules/@scope/pkg'
    with directory '<SRC>/node_modules/@scope/pkg'
```

Neither of the two obvious repairs is correct, and both exit 0 or look close
enough to ship:

| attempt | result | why it is wrong |
| --- | --- | --- |
| `rm -rf "$DIR/node_modules"; cp -r …` | exit 0, panel runs | the symlink is now a **real directory** — vendor duplicated, upstream updates stop propagating |
| `rm -rf …; cp -a …` | link preserved | a **relative** target is depth-dependent (`../../vendor/` vs `../../../vendor/`), so it dangles |

Use a tar stream instead — it reproduces links as links, and the extraction depth
never enters into it:

```bash
for item in package.json package-lock.json src public vendor node_modules; do
  [ -e "$SRC/$item" ] || die "package is incomplete: $item"
done
tar -C "$SRC" -cf - package.json package-lock.json src public vendor node_modules \
  | tar -C "$DIR" -xf -
```

An over-extract replaces files in place, so a pre-clean is unnecessary and a
`rm -rf` there only creates the window where a failure leaves the buyer with
nothing. Snapshot the database **before** the extract, and write the version
marker **only after** it returns — an aborted copy that leaves the old marker in
place reports a healthy panel it no longer matches.

Assert the shape, never the exit code:

```bash
[ -L "$I/node_modules/@scope/pkg" ]            || bad "install downgraded the vendored link to a copy"
[ -e "$I/node_modules/@scope/pkg/" ]            || bad "the vendored link dangles"
( cd "$I" && node -e "require('@scope/pkg')" )  || bad "the vendored package does not resolve"
```

The third assertion is the one that survives a future edit: the first two
describe the current failure, the third describes the contract.