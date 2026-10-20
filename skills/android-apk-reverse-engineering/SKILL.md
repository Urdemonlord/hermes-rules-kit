---
name: android-apk-reverse-engineering
description: Use when reverse-engineering an Android APK.
---

# Android APK Reverse Engineering

Static-first workflow for APK analysis: architecture, API/endpoints, auth, security audit.
Every claim must come from the artifact, not from assumption.

## 1. Fingerprint before anything else
```
aapt dump badging app.apk            # package, version, sdk, permissions
unzip -l app.apk | awk '{print $4}' | sed 's|/.*||' | sort -u   # top-level layout
apksigner verify --print-certs -v app.apk
```
Decide the framework FIRST, because it changes the whole plan:
- `lib/*/libflutter.so` + `assets/flutter_assets` -> Flutter (Dart AOT; use reFlutter/blutter)
- `assets/index.android.bundle` -> React Native / Expo (see section 3)
- `lib/*/libunity.so` -> Unity (use Il2CppDumper)
- only `classes*.dex` -> native Kotlin/Java (jadx is the main tool)

Split APKs (Play) may ship only the base APK with NO `lib/` dir. That is normal; check the manifest's `splits` metadata.

## 2. jadx: invoke as a CLASS, never `-jar`
`java -jar jadx-all.jar` launches the GUI and dies with `HeadlessException` on a server.
```
java -Xmx1400m -cp jadx/lib/jadx-1.5.6-all.jar jadx.cli.JadxCLI -d out --no-res --threads-count 2 app.apk
```
- jadx can appear STUCK: it prints `progress: N of M` then sits while saving files (`JadxDecompiler.save` sleeps between writes). Verify real progress by counting `.java` files over time, and check `jstack` (a `TIMED_WAITING` in `JadxDecompiler.save` means it is writing, not hung).
- For a large app, jadx may take hours. If the app package dir contains only `R.java` + `BuildConfig.java`, there is NO custom Java code - stop jadx, the rest is third-party libraries.

## 2b. Multi-dex APKs: decompile PER DEX, never as one APK
A single jadx run over the whole APK OOMs well before it finishes. Verified on a 63 MB / 6-dex APK: `-Xmx1200m` on the full APK died at 4577 of 14688 classes (31%) with `java.lang.OutOfMemoryError`. Heap is allocated for ALL dex at once, so the peak does not shrink with `-Xmx` alone - and raising `-Xmx` further can OOM-kill whatever else shares the box.

Split first, then one jadx per dex at a modest heap. Each dex peaks independently, so this always fits:
```
mkdir -p dexwork && cd dexwork
unzip -q -o app.apk 'classes*.dex'
for d in classes*.dex; do
  java -Xmx900m -cp ~/jadx/lib/jadx-1.5.6-all.jar jadx.cli.JadxCLI \
    -d "out/$d" --no-res --threads-count 1 "$d" 2>&1 | tail -2
done
```
Same 6-dex APK at `-Xmx900m`, 1 thread: 21203 `.java` files, all six dex OK, no OOM. Grep across `out/*/sources`, not `out/sources`.

Per-dex output splits the app's own package across directories (a 6-dex build put `com.ometv.tv.*` in one dir and `com.chat.api.*` in another). Find the real package by extracting type descriptors from dex, not by guessing:
```
python3 -c "import re,sys; [print(m) for f in sys.argv[1:] for m in re.findall(rb'L[A-Za-z0-9_/\$]*yourpkg[A-Za-z0-9_/\$]*;', open(f,'rb').read())]" classes*.dex
```

On a 3.6 GB shared host (VPS with other services) treat `-Xmx` above ~900m as unsafe and run jadx in a tracked background process, not a foreground loop.

## 3. React Native / Expo: the JS bundle IS the app
Business logic lives in `assets/index.android.bundle`, usually NOT encrypted even when DEX is protected.

Check the format first:
```
head -c 8 bundle | xxd      # c61f bc03 = Hermes bytecode; else it is plain JS (just beautify it)
python3 -c "d=open('bundle','rb').read(); print(int.from_bytes(d[8:12],'little'))"   # HBC version
```
Hermes version support (verify with `python3 -c "from hermes_dec.parsers.hbc_file_parser import LATEST_BYTECODE_VERSION as v; print(v)"`):
- `hbctool` and old `hermes-dec` reject recent versions (e.g. v98 = Expo SDK 56 / RN 0.8x).
- **hermes-dec >= 0.1.7 supports v97-99.** Decompile with:
```
python3 -m hermes_dec.decompilation.hbc_decompiler assets/index.android.bundle out.js
```
- Output is register-based (`r7 = 'Bearer ';`), not idiomatic JS; original names are minified away. Strings, control flow, endpoints and logic are still fully readable. Reconstructing idiomatic JS may be impractical - say so honestly.
- Faster string harvest if you only need API surface: the Hermes **string storage** blob is length-prefixed. Read from `stringStorageOffset` (compute from the header, or brute-force candidate offsets) and decode each entry (1-byte len + utf8; 0x80 flag = utf-16; 0xFF escape = u32 len).

Also read `assets/app.config` (Expo) - it often leaks `owner`, `projectId`, `slug`, and plugin config.

## 4. PairIP (Google Play app-signing protection)
Signs: `android:name="com.pairip.application.Application"` in the manifest, `com.pairip.licensecheck.*` classes.
Effect: the app's own DEX classes are encrypted and jadx will not produce them (e.g. `MainActivity.java` is missing). This is expected; pivot to the JS bundle. Do not claim the app "has no code" - say the entry point is encrypted.

## 5. Harvesting API surface from a minified bundle
The string table is often one concatenated blob, so naive `grep` gives merged junk. Search with context instead:
```
grep -oaE '.{0,40}/api/[A-Za-z0-9_/${}.:-]{0,70}' bundle | sort -u
grep -oaE "'/(?:api/)?[a-z][a-zA-Z0-9-]*(?:/[a-zA-Z0-9_.:-]+)+'" bundle | sort -u   # in decompiled JS
```
Then read around the hits with line numbers. Look for: base URL, axios/fetch setup, interceptors, `Authorization`/`Bearer`/`x-access-token` headers, storage keys, and 401 handling.

## 5b. Tracing HTTP methods (do not infer from hook names)
Hook names (`useCreate*` vs `useXxx`) are a guess. In Hermes/RN bytecode the real method is a property access right before the call:
```
r9 = r7.default; r8 = r9.post;      # method captured into a register
r7 = r8.bind(r9)('/auth/login', body);
r5 = '/auth/logout'; r7 = r8.bind(r9)(r5, r7);   # endpoint hoisted into a register first
```
Write a script that, for every string literal matching `'/<known-prefix>/...'`, scans up to ~10 lines back for `= rN.(get|post|put|patch|delete);`; if not found, find the `.bind(...)(reg` call and follow the bound register's method. Endpoints are frequently hoisted, so the method can sit far from the path string.

**False-positive traps** (grep hits that are NOT requests) - check the surrounding call before reporting:
- `url.includes('/x')` inside an axios response interceptor = a 401-exception list, not a request.
- `router.push('/history')` = navigation.
- A returned `baseURL + '/path/' + id` string = a download URL, not an axios call.
- A `queryKey` like `['analytics-summary']` is not the endpoint; the real path is in the adjacent `queryFn`.

Then cross-verify: extract every path in your report and assert each literal exists in the bundle, and extract every API-ish literal and assert each appears in the report. Report the count. This catches both invented endpoints and missed ones.

## 6. Security checklist (report findings with file:line evidence)
- Hardcoded secrets: `AIza[0-9A-Za-z_-]{35}`, `sk-...`, `AKIA...`, `BEGIN ... PRIVATE KEY`, payment-gateway server keys.
- Token storage: `AsyncStorage` (plaintext) vs `expo-secure-store`/Keystore. AsyncStorage is a finding.
- `android:allowBackup="true"` (data exfiltrable via `adb backup`), `android:debuggable="true"`.
- Missing `usesCleartextTraffic`/networkSecurityConfig (HTTPS enforced) = good; state it.
- `exported="true"` components without a permission guard.
  **In compiled manifest, `android:exported` is a NUMERIC value**, not the word `true`: `aapt dump xmltree` shows `(type 0x12)0xffffffff` for true and `(type 0x12)0x0` for false. `grep 'exported.*true'` returns 0 even when components are exported - parse the numeric values instead. And when you finally read them, do not wave them off as "all SDK": enumerate and separate SDK components from the app's OWN exported components (`com.<app>.*`) - the app-owned ones are where real findings live (e.g. an exported service with no permission guard).
- Over-broad permissions (esp. `SYSTEM_ALERT_WINDOW`, `READ_PHONE_STATE`, `WRITE_EXTERNAL_STORAGE` without `maxSdkVersion`).
- NotificationListenerService: it receives notifications from ALL apps (Android cannot filter per-package); filtering happens in code afterwards. Call out the privacy implication for Play policy.
- Debug logging left on in release (`[API REQ]`, `console.log` of payloads).
- Leftover dev code (e.g. `localhost|127.0.0.1` rewritten to `10.0.2.2` emulator loopback).
- Note what is FINE too (Firebase Android API keys are expected to be embedded; no server keys; release build type; Play App Signing).

## 7. Evidence discipline
- Never report a secret, endpoint, or flaw you did not read in the artifact. Quote the exact string or file:line.
- **Search dex with the DEX descriptor form (slashes), not the Java dotted form.** A library is `com/neovisionaries/ws/client/` in the dex string table, so searching `com.neovisionaries.ws.client` returns a false "MISS". Same trap for any package/class you look up by dotted name.
- **Dex string tables are stored in ALPHABETICAL order.** Two strings being adjacent in the table (e.g. `https://.facebook.com` next to an `elastic-cloud.com` host) is just alphabetical coincidence - NOT evidence they belong to the same SDK or code path. Never infer a relationship from string adjacency.
- Distinguish "not found" from "absent": a grep miss can mean minification or inlining.
- Verify a decompiler actually worked (line count, sample) before trusting its output.
- Handing the user a report: separate verified findings from inferences, and state tool limitations plainly.

## 7b. Cross-verify the endpoint list (cheap, catches invented APIs)
Read the Retrofit/OkHttp interface and assert every path literal really exists in the dex string table, then assert the count. Run this before reporting anything endpoint-shaped:
```
python3 - <<'PY'
import re, glob
api = open('out/classes4.dex/sources/<pkg>/data/network/client/AppApi.java').read()
paths = set(re.findall(r'@(?:GET|POST|PUT|DELETE)\("([^"]+)"\)', api))
dex = b''.join(open(f,'rb').read() for f in sorted(glob.glob('classes*.dex')))
missing = [p for p in paths if p.encode() not in dex]
print(f'endpoints {len(paths)}, not in dex {len(missing)}', missing[:10])
print('methods', len(re.findall(r'@(GET|POST|PUT|DELETE)\(', api)))
print('@Url dynamic', len(re.findall(r'@Url', api)))
PY
```
A Retrofit interface also recovers the auth scheme for free - `@Header("X-Api-Key")` on nearly every method, plus the login `@POST("sessions/{method}")` body, tells you exactly how a call authenticates. Method count by verb is a good sanity check against a hand-written table.

## 8. Reading a Retrofit interface (Kotlin sources, not paths)
@Method / @GET / @POST, `@Path` / `@Query` / `@QueryMap` / `@Body` / `@Part` / @Header(NetworkRepositoryImpl.HTTPHeaders.X_API_KEY), and `@Url` on the method means the path is NOT in the annotation - it comes from a remote config object. Group findings as: annotated paths (static), `@Url` methods (dynamic, name the config class that feeds them), and base URLs (from the Retrofit builder).

## 9. Config classes worth reading first
`core/config/` style packages are small, unobfuscated, and name every backend:
- a URL/endpoint config class - check whether values are `static` literals or overwritten by a remote-config `apply(ConfigModel, Context)`. Overwritable base URLs with no host allowlist = the whole app can be redirected by whoever controls that config channel.
- a crypto config class - `static` key literals plus any setter reveal what is protected and how weakly (RC4/ECB with an embedded key protects nothing against an attacker who has the APK).
- a network-security-config trust anchor - resolve each `res/raw/*` cert with `aapt dump xmltree app.apk res/xml/network_security_config.xml` + `aapt dump --values resources app.apk`, then `openssl x509 -noout -subject -issuer -dates` on the extracted file. An expired pin is a dead control, not a working one: say so, and note it means pinning provides no protection in that build.

## 10. Custom TLS / WebRTC hardening
A `data/dns/` class that resolves A records via a public DoH endpoint and then TCP-probes a port is bypassing local/ISP DNS for WebRTC ICE. A `sniHosts` list plus `SSLSocket.setServerNames` means the app pins SNI names independent of the URL host. Both are legitimate; report them as architecture, not as vulnerabilities.

## 11. Cheap re-verification without jadx
Before re-running the full multi-dex jadx pipeline (hours, OOM risk), re-verify an existing analysis with free checks against the dex blob and manifest: fingerprint (`aapt dump badging`, `apksigner verify --print-certs`), search every claimed host/URL/header/key literal in the concatenated dex, parse exported components numerically, and resolve pinned certs with `openssl x509 -dates`. This confirms or refutes most of a prior report in seconds and tells you whether a costly decompile is even needed.
