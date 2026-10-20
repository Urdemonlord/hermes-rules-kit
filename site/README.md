# Site

One static page. No build step, no framework, no external requests (fonts and icons are system-level).

## Before it can take money

The page ships with checkout disabled. Open `index.html`, find `CHECKOUT` at the bottom, and paste the two payment links:

```js
const CHECKOUT = {
  pack: "https://...",     // Ops Pack, one-time
  session: "https://..."   // Setup session, 45 minutes
};
```

Until both are filled, the buttons scroll to the note instead of pretending to sell. That is deliberate: a dead button that looks live costs more trust than no button.

Payment links work fine from Xendit, Lemon Squeezy, or a GoBiz QRIS page. Nothing in the page depends on which one you pick.

## Serve it locally

```bash
cd site && python3 -m http.server 8000
# open http://127.0.0.1:8000
```

## Deploy

Static file, so anything works:

- **VPS + nginx**: copy the directory to `/var/www/rules-kit`, add a `root` server block, run `certbot`. Ask before touching an existing vhost on a shared host.
- **Vercel / Netlify / Cloudflare Pages**: point at the repo, set the output directory to `site`, no build command.
- **GitHub Pages**: enable Pages on `main` with `/site` as the source.

## What is intentionally missing

- No analytics, no cookie banner, nothing to consent to.
- No testimonials. There are none yet, and invented ones are the fastest way to lose a technical buyer.
- No countdown, no "only 3 spots left". The pricing section sells a file and a session, not scarcity.

## Copy rules used here

Claims are limited to what the repo can prove: 104 skills, 10 framework, 94 library, 5 presets, MIT, tested on Hermes v0.22.1, CI green. No benchmark numbers, no customer logos, no "battle-tested". The limits section exists because saying what it does not do is what makes the rest believable.
