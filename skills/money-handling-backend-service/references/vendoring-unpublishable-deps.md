# Vendoring a dependency that cannot be installed

Use when `package.json` carries a `file:` dependency pointing somewhere outside the
project — almost always at `/tmp`, which is how a session that had the source
cloned "just for now" becomes a production install path that a reboot deletes.

The failure is not slow and not noisy: the service stops starting, with a module
not found, and there is no fallback. One dependency in a payment panel must never
be held hostage to a directory that is not supposed to persist.

## Diagnose before choosing a fix

```bash
readlink -f node_modules/<pkg>                 # where does it really point
python3 -c "import json;d=json.load(open('package.json'));print(d['dependencies'])"
npm view <pkg> versions --json                # registry  (JSR-only pkgs 404 here)
git -C <src> rev-parse HEAD                    # is local HEAD on the remote?
git -C <src> ls-files dist | wc -l             # 0 => build output is gitignored
```

Three answers decide everything:

- **Not on npm.** Expected for JSR-published packages. `npm i <pkg>` was never an
  option; do not spend the session trying.
- **`dist/` (or `build/`, `lib/`) is gitignored upstream.** A fresh clone has no
  built output, so "just clone it again" does not work — it needs the project's
  build tool, which is usually not a dependency of yours. This is what makes
  vendoring the built artifact the correct answer rather than a shortcut.
- **Local HEAD equals `origin/<branch>`.** If it does not, the local checkout
  carries commits upstream never saw, and pinning a SHA records something nobody
  can reproduce.

## Vendor the built output, pinned

Copy what is actually loaded at runtime, plus a manifest npm can consume — not
the repo.

```python
# what to copy: the built entrypoints, and nothing else
shutil.copytree(SRC/'dist', DST/'dist')
shutil.copy2(SRC/'package.json', DST/'package.json')

# source maps are not loaded at runtime and dominate the size
for p in DST.rglob('*.map'):
    p.unlink()

pkg = json.loads((DST/'package.json').read_text())
pkg.pop('scripts', None); pkg.pop('devDependencies', None)
pkg['_vendored'] = {'from': <repo url>, 'commit': <sha>, 'version': <v>}
```

Point the dependency at it and regenerate the lockfile — a lockfile still holding
the old `file:` path makes `npm ci` demand the directory you are deleting:

```json
"@scope/pkg": "file:./vendor/<pkg>"
```
```bash
npm install --package-lock-only --no-audit --no-fund
grep -c "tmp/" package-lock.json     # must be 0
```

**Strip `scripts` from the vendored manifest.** npm runs a dependency's lifecycle
scripts on `file:` installs, so an inherited `"prepare": "tsup"` fails on a
machine that has no `tsup` — a build tool belonging to someone else's project,
reachable from yours.

Report the size and the pin in the commit message. 131KB of vendored output with a
SHA is a defensible artifact; a 56MB repository copy is not.

## Prove it by deleting the thing you just fixed

A vendor directory that was never reconstructed from scratch is not verified.

```bash
rm -rf /tmp/<src> node_modules
npm ci --no-audit --no-fund                 # must succeed with /tmp absent
md5sum node_modules/<pkg>/dist/index.js     # identical to the pre-vendor build
npm run check                               # full suite
```

Then confirm the live service, because "it installs" is not "it works": restart
the process and exercise the feature that depends on the package — for a payment
panel that means a real rendered artifact served through the public route, with a
byte count, not a health check alone.

## What not to capture

This is not a rule about npm being unreliable or about JSR being broken. The rule
is narrow: **a dependency resolved by path outside the project is not a
dependency, it is an unversioned local build with no restore path.** Point it at
the project or vendor it; do not leave it pointing at a temporary directory.