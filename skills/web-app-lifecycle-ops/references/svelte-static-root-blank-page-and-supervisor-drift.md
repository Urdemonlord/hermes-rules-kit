# Svelte static-root blank page + supervisor drift

Use when a public SPA hostname returns `200 OK` with HTML and assets, but the user sees a blank white page.

## Pattern
- Public domain is served by **nginx static root** (`root /var/www/...`) rather than the app dev/prod server.
- A separate PM2 / Next.js / Node process exists for a different surface or an old deployment and is easy to mistake as the owner.
- The real failure is frontend runtime breakage inside the built SPA, not nginx.

## Fast proof sequence
1. `curl -I https://host/` and `curl https://host/ | head` to confirm HTML shell loads.
2. Inspect nginx vhost and identify whether `/` is served by `root /var/www/...` or `proxy_pass`.
3. Fetch built asset URLs from the live HTML and confirm they return `200`.
4. Inspect the actual source repo that produced those assets before touching unrelated supervisors.
5. Run the frontend type/runtime checks locally (`npm run check`, `npm run build`).
6. If the site is a built SPA, publish the new `dist/` into the live static root, then verify with a browser screenshot against the public URL.

## Svelte-specific pitfall found
Custom store containers are not themselves stores.

Bad:
- `$eventStore.live`
- `$eventStore.history`

If `eventStore` is an object that exposes nested stores, subscribe to the nested store instead:

```ts
const liveStore = eventStore.live;
let live = $derived($liveStore);

const historyStore = eventStore.history;
let evts = $derived($historyStore);
```

## Another real bug class
If a toast/helper API expects positional args like `add(message, type)`, passing an object payload can fail type-checks and break the frontend event path.

## Deploy discipline
Before restarting PM2/systemd, verify which surface the public hostname actually uses:
- static root
- reverse-proxied app server
- separate API upstream

Do not treat an unrelated PM2 process as proof of ownership for the public page.

## Verification standard
Success means:
- local `npm run check` passes
- local build passes
- live HTML references the new asset hash
- public screenshot shows rendered UI, not just `200 OK`
