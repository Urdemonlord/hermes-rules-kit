---
name: domain-redirect-and-hostname-routing
description: Use when redirecting a domain or aliasing a hostname.
---

# Domain redirect & hostname routing

Class of task: "bisa redirect A ke B?", "kenapa domain ini nunjuk ke halaman
salah?", "pindahin domain ini ke server lo" — deciding whether a redirect is
possible, who owns the DNS, and which layer should perform it.

Trigger shapes seen in practice: a parking or "domain is expired" page, a
`DEPLOYMENT_NOT_FOUND` body, a typo'd hostname falling through a DNS wildcard, a
registrar whose hosting lapsed but whose domain is still owned, and users
asking to do it "lewat VPS/nginx" when the source DNS does not point there.

Distinct from `edge-proxied-asset-delivery` (that is the edge-to-origin path for
a downloadable file) and `nextjs-vercel-operations` (app-level redirects inside a
deployed Next.js app). This skill is about **hostname ownership and reachability**
before any redirect rule exists.

## Always-on rules

1. **Verify the target is alive BEFORE designing anything.** Fetch it, don't
   assume. HTTP 200 is not liveness — parked and error pages also return 200.
   Confirm the body is the real thing (`grep` for a title/expected marker). A
   redirect to a dead target is strictly worse than no redirect.
2. **Normalize the hostname the user typed.** CJK/dotless-ı/full-width/homoglyph
   characters are invisible in most fonts and change the domain entirely. Convert
   to punycode first (see references), then resolve. Never hand the unicode literal
   to a DNS/whois tool — those tools punycode it silently and then tell you
   "no match" about a domain you never actually queried.
3. **Ask who owns the source DNS before proposing nginx work.** "Do it on my VPS
   with nginx instead" is only satisfiable if the source hostname already resolves
   to that VPS. Check with `dig` first; if it resolves elsewhere, say plainly that
   registrar access is unavoidable rather than designing around it.
4. **A vhost is inert if DNS points elsewhere.** nginx matches the `Host:` header
   on a connection it actually received. Adding a server block for a hostname that
   resolves to a different IP changes nothing and produces no error.
5. **An explicit Cloudflare record beats the zone wildcard.** If a hostname returns
   the wildcard target's provider error page (`DEPLOYMENT_NOT_FOUND`, "deployment
   not found", a generic host placeholder, or a provider JSON error body such as
   Vercel's `{"error":{"message":"Token not found","statusCode":404}}`), the
   hostname has **no explicit record**
   and is falling through to the wildcard. That is fixed by adding a record, not by
   anything at the origin.
6. **Registry expiry ≠ hosting expiry.** The registrar's own web page is not
   evidence. Read the authoritative registry (whois at the registry host, or RDAP).
   Absence of `redemptionPeriod`/`pendingDelete` in the EPP status means the domain
   is still owned and can be renewed, transferred, or repointed — a hosting
   suspension only means the registrar stopped serving it.
7. **Put the redirect at the layer that owns the source traffic.** Source resolves
   to your host → nginx `301` (one source of truth, exact host match, no CDN
   config drift). Source is foreign DNS → registrar/hosting redirect or URL-forward
   feature. Cloudflare Redirect Rules only ever fire on hostnames that are
   **proxied in that zone**.
8. **Free hosting does not mean free ownership.** Moving to a free static host or
   worker platform removes the hosting bill but never the domain renewal. State that
   split explicitly; users asking for a redirect are often discovering this for the
   first time.
9. **Ask for the exact target string once, then stop guessing.** Do not probe
   invented variants (`.co.id`, `.net`, hyphenations) to be helpful — it is noise,
   it burns calls, and it can read as if a match was found. One clarify, verbatim.
10. **Lead with the verdict and its evidence.** Feasibility questions get: verdict,
    the 5-line DNS/whois block, then the options. Folding the user's answer back in
    as the plan beats re-asking what they already answered.
11. **Budget changes the answer — re-check constraints late.** When the user
    reveals a cost blocker, the earlier plan is dead: re-derive which options
    survive and say so, rather than continuing to detail work that can no longer
    happen.

## Procedure

```bash
# 1. Is the target alive and real?  (bodies, not just status codes)
curl -sS -m 12 -o /dev/null -w 'code=%{http_code} ip=%{remote_ip} redirect=%{redirect_url}\n' https://<target>/
curl -sS -m 12 https://<target>/ | grep -oiE '<title>.{0,80}' | head -2

# 2. Who owns the source, and where does it point?
dig +short A <source>; dig +short NS <source>; dig +short A www.<source>

# 3. Registry truth, not registrar marketing
whois -h whois.verisign-grs.com <source>       # or the TLD's registry host
curl -s https://rdap.verisign.com/com/v1/domain/<source> | python3 -m json.tool

# 4. Does the source already reach this box?  (the gate for any nginx plan)
curl -sS -m 10 -o /dev/null -w 'code=%{http_code}\n' \
     --resolve <source>:80:<VPS_IP> http://<source>/
```

Then branch: source already on this VPS → nginx `301` in a vhost (rule 7).
Source elsewhere → the work needs registrar/DNS access, and the plan must say who
holds it and what it costs (rules 3, 6, 8).

## The nginx redirect shape

```nginx
server {
    listen 80;
    server_name <source> www.<source>;
    return 301 https://<target>$request_uri;
}
server {
    listen 443 ssl http2;
    server_name <source> www.<source>;
    ssl_certificate     /etc/letsencrypt/live/<source>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<source>/privkey.pem;
    return 301 https://<target>$request_uri;
}
```

Preserve `$request_uri` or deep links die at the redirect. Certs are the sticking
point for a foreign host: a certificate cannot be issued for a hostname whose
DNS you do not control, which is why the redirect usually has to happen at the
registrar/hosting layer until DNS moves.

## Alias hostname baru ke layanan yang sudah jalan di sini

Kasus tetangga dari redirect: hostname baru harus melayani **isi yang sama
persis** dengan vhost yang sudah ada (nama produk/app berubah, klien lama masih
memanggil hostname lama). Urutannya ketat, karena blok `443` menyebut path
sertifikat yang belum ada.

1. **Buktikan hostname mencapai kotak ini.** `dig +short <baru>` mengembalikan IP
   edge untuk hostname mana pun di zona itu — itu bukan bukti. Uji origin:
   `curl -H 'Host: <baru>' http://127.0.0.1/`. Origin menjawab (200/404 dari
   nginx) sementara URL publik mengembalikan body milik provider lain = hostname
   itu tidak punya record eksplisit dan jatuh ke wildcard zona, dan wildcard-nya
   bisa menunjuk ke provider hosting, bukan ke VPS ini. Perbaikan: tambah
   `A <baru> -> <IP_VPS>` proxied, lalu `dig` ulang.
2. **Web root dulu, satu sumber kebenaran:** `mv` direktori web root ke nama
   baru, lalu `ln -s <baru> <lama>`. Dua hostname menyajikan byte identik, dan
   rilis berikutnya tidak bisa membuat keduanya menyimpang.
3. **Vhost sementara port 80 saja** (`location ^~ /.well-known/acme-challenge/`
   + root), `nginx -t`, reload. Challenge ACME butuh itu, dan blok 443 belum
   boleh ditulis.
4. **Terbitkan sertifikat dengan webroot, bukan plugin nginx:**
   `certbot certonly --webroot -w <web_root> -d <baru> --non-interactive --agree-tos`.
   Plugin `--nginx` menyunting berkas vhost di belakang lo; `certonly` menjaga
   konfigurasi tetap milik lo dan memastikan `/etc/letsencrypt/live/<baru>/`
   sudah ada sebelum blok `443` ditulis.
5. **Vhost penuh = salinan vhost tetangga**, bukan tulis ulang dari nol:
   `sed 's/<lama>/<baru>/g' sites-available/<lama> | sudo tee sites-available/<baru>`,
   `nginx -t`, reload. Blok ACME di port 80 (tanpa redirect) wajib ikut —
   challenge yang dijawab 301 lewat Cloudflare berakhir 520 dan perpanjangan
   sertifikat gagal.
6. **Backup vhost ke `/etc/nginx/backups/`, jangan ke `sites-enabled/`** —
   direktori itu di-glob, `*.bak.*` di sana memicu `conflicting server name` dan
   nginx mengabaikan config yang hidup.
7. **Verifikasi matriks di KEDUA hostname** dengan set path yang sama (`/`,
   endpoint API, unduhan, `/dl/`), lalu bandingkan. Endpoint yang menjawab `400`
   karena input kosong tetap bukti proxy sampai ke service-nya — asal sama di
   kedua hostname.

Endpoint yang ditanam di klien (pemeriksa pembaruan, proxy, callback auth) hanya
boleh pindah **setelah** hostname baru melayani, dan hostname lama tetap hidup
selama masih ada klien terpasang yang memanggilnya.

## Verify as a matrix

`curl -I` on one URL proves routing only. Check the whole set:

```bash
for u in http://<source>/ http://www.<source>/ https://<source>/ https://www.<source>/ \
         https://<source>/deep/link?q=1; do
  curl -sS -m 10 -o /dev/null -w "%{http_code} -> %{redirect_url}\n" "$u"
done
# then follow one redirect end to end
curl -sSL -m 15 'https://<source>/deep/link?q=1' -o /tmp/final -w '%{url_effective} %{http_code}\n'
grep -oiE '<title>.{0,80}' /tmp/final     # must be the REAL target page
```

Also re-resolve after the change (`dig @1.1.1.1`) — an unchanged answer means the
edit never propagated and no amount of origin work will help.

## Pitfalls

- **whois auto-punycodes its argument.** Querying a unicode label and reading
  `No match for "XN--..."` proves nothing about the label you typed; punycode the
  string yourself and query that.
- **A parked page returns 200.** Registrar parking, "domain expired" interstitials,
  and `DEPLOYMENT_NOT_FOUND` are all HTTP 200. Judge liveness by body content.
- **`grep -rn` in `sites-enabled/` misses the live config.** Most entries are
  symlinks; use `sudo nginx -T` for the authoritative list of what nginx actually
  loaded, then grep that dump.
- **A wildcard can shadow what you think is routed.** Dump the zone's records and
  compare the hostname's target against the wildcard's — same provider IP for both
  means you are looking at the wildcard, not a dedicated host.
- **A backend can answer per-`Host` behind one vhost.** If the host is unknown to
  nginx but a real page still comes back, probe the upstream with
  `curl -H "Host: <host>" http://127.0.0.1:<port>/` — that separates "nginx never
  routed it" from "the app does serve it".
- **Redirect loops from splitting www/non-www.** Decide the canonical host once and
  make every path (http, https, www, apex) terminate at exactly one of them.
- **HTTPS redirect to a target whose cert does not cover it** is invisible at
  `curl -I` time and only surfaces as a browser interstitial.

## References

- `references/diagnostic-cookbook.md` — punycode normalization, registry/RDAP
  queries, Cloudflare zone record dumps, `--resolve` origin bypass, `nginx -T`,
  per-Host upstream probing, Wayback liveness. Batch these; one `dig` per turn
  wastes the user's time.

## What this does not cover

Deploying the site the redirect points at, static-file caching at the edge
(`edge-proxied-asset-delivery`), app-level redirect middleware
(`nextjs-vercel-operations`), and registrar-agnostic bulk domain management.