# Diagnostic cookbook

Commands used to answer "can this redirect, and who has to act". Batch them in
one shell call; do not issue one `dig` per turn.

## Punycode / homoglyph normalization

```bash
# what the browser will actually ask DNS for (ICU/UTS-46, non-transitional)
node -e "const u=require('url');console.log(u.domainToASCII('host with dotless ı'))"
# python stdlib IDNA2003 / idna pkg
python3 -c "import idna;print(idna.encode('host',uts46=True).decode())"

# verify the normalized form is what actually resolves
dig +short A $(node -e "process.stdout.write(require('url').domainToASCII('x'))")
```

Dots worth knowing: `ı` U+0131 (dotless i) is **not** `i`; UTS-46 transitional
processing maps ß→ss but is removed from current IDNA, and browsers use
non-transitional — so a transitional-only punycode is a different domain than the
one users can reach.

## Registry truth (authoritative)

```bash
whois -h whois.verisign-grs.com example.com          # .com registry
curl -s https://rdap.verisign.com/com/v1/domain/example.com | python3 -m json.tool
```

Read: `eventDate` for registration/expiration/last-changed, the `status` array for
`redemptionPeriod` / `pendingDelete` / `clientHold`, and the nameserver list. A
registrar-hosted `whois` answer can lag or differ — prefer the registry host or
RDAP when the two disagree.

Registrar NS used for "suspended/expired" parking (`*.dns-expired.com`) and the
matching interstitial page tell you nothing about registry state; treat the page
text as marketing.

## Cloudflare zone record dump

```bash
curl -s -H "Authorization: Bearer $CF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=<zone>" | python3 -m json.tool

curl -s -H "Authorization: Bearer $CF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/<zone_id>/dns_records?per_page=100" \
  | python3 -c "import sys,json;[print(r['type'],r['name'],'->',r['content'],'proxied:',r['proxied']) for r in json.load(sys.stdin)['result']]"
```

`proxied: false` on a Vercel-style target means the client sees the provider's own
error page. An explicit record and the zone `*.zone.tld` wildcard resolving to the
**same** target means the hostname is falling through to the wildcard.

Write the inline `python3 -c` to a file when it needs nested quotes — shell
mangling of `"` inside the heredoc-less form is a reliable source of
`SyntaxError`/truncated curl output.

## Reaching origin behind a CDN

```bash
# bypass the CDN, talk to one IP with a chosen SNI/Host
curl -sS -m 10 --resolve <host>:443:<IP> https://<host>/ -k
curl -sS -m 10 -D - -o /dev/null --resolve <host>:80:<IP> http://<host>/
```

`--resolve` is the cheapest way to answer "would my server even receive this?"
without touching DNS. A real page here plus a different public answer means the
public path is a DNS/CDN problem, not an origin problem.

## What nginx actually loaded

```bash
sudo nginx -T > /tmp/nginxdump.txt 2>/tmp/nginxerr.txt
grep -E '^\s*server_name' /tmp/nginxdump.txt | sort -u
```

Most entries under `sites-enabled/` are symlinks, so a plain recursive grep of
that directory reports nothing while nginx happily serves them. `nginx -T` also
prints the config path each directive came from. Pre-existing
`protocol options redefined for 0.0.0.0:443` warnings come from other sites and do
not block a passing `nginx -t`.

## Is the app itself serving this host?

```bash
for h in <host> typo.<zone> zzz-unknown.<zone>; do
  printf '%-30s code=%s bytes=%s\n' "$h" \
    "$(curl -sS -m 8 -o /dev/null -w '%{http_code}' -H "Host: $h" http://127.0.0.1:<port>/)" \
    "$(curl -sS -m 8 -H "Host: $h" http://127.0.0.1:<port>/ | wc -c)"
done
```

Equal byte counts across hosts mean host-routing; a short body (24 bytes is a
common `{"error":"not found"}`) means the upstream rejects the name.

## Was there ever content there?

```bash
curl -s "https://archive.org/wayback/available?url=<host>"
```

`"archived_snapshots": {}` means never archived — useful for deciding whether a
redirect is worth configuring at all when the user is short on budget.