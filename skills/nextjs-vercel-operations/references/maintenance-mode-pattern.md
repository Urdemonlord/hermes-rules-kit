# Maintenance Mode Pattern (Next.js 14/16 + Vercel) — verified 2026-08

Verified on roblox-top-up-system (storefront.example, Next.js, commit 646c6bb). Env-toggleable, zero risk, API stays live.

## Files

### 1. `app/maintenance/page.tsx`
Branded page, dark theme to match existing neon layout. Adjust copy per site.

```tsx
import { Wrench } from "lucide-react";

export default function MaintenancePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <div className="mb-6 rounded-full bg-yellow-500/10 p-4">
        <Wrench className="h-10 w-10 text-yellow-400" />
      </div>
      <h1 className="mb-3 text-3xl font-bold md:text-4xl">Sedang Dalam Perbaikan</h1>
      <p className="mb-6 max-w-md text-[#8892B0]">
        [Site] sedang melakukan pemeliharaan untuk memberikan layanan yang lebih baik.
        Silakan kembali lagi dalam beberapa saat.
      </p>
      <div className="flex items-center gap-2 text-sm text-[#8892B0]">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-yellow-400" />
        Maintenance Mode Aktif
      </div>
    </div>
  );
}
```

### 2. `middleware.ts` (repo root)
**Must exempt static asset file extensions** — otherwise `/logos/logo-storefront.png` and every image/css/js returns 307 and the maintenance page renders with missing logo (real bug hit in session: user reported "kok logonya hilang").

```ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const STATIC_EXT = /\.(png|jpe?g|webp|svg|gif|ico|css|js|woff2?|ttf|eot|map|mp3|mp4)$/i;

export function middleware(request: NextRequest) {
  const maintenanceMode = process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true";
  if (!maintenanceMode) return NextResponse.next();

  const { pathname } = request.nextUrl;

  if (
    pathname === "/maintenance" ||
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/icon") ||
    STATIC_EXT.test(pathname)
  ) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/maintenance";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|robots.txt).*)"],
};
```

### 3. `.env.example`
```
# Set to "true" to enable maintenance mode (redirects all pages to /maintenance)
NEXT_PUBLIC_MAINTENANCE_MODE="false"
```

## Enable / disable (Vercel)
1. Dashboard → project → Settings → Environment Variables → `NEXT_PUBLIC_MAINTENANCE_MODE` = `true` (or `false`) on Production.
2. **Redeploy.** Env is inlined at build time — dashboard change alone does nothing.
3. Verify: `curl -sSL https://storefront.example/` → expect redirect to `/maintenance`.

## Test locally
```bash
NEXT_PUBLIC_MAINTENANCE_MODE=true npx next build   # MUST rebuild — inlining
NEXT_PUBLIC_MAINTENANCE_MODE=true npx next start -p 3105
# then in another shell:
curl -sSL -m 10 -o /dev/null -w "%{http_code} -> %{redirect_url}\n" http://localhost:3105/
curl -sSL -m 10 http://localhost:3105/maintenance | grep -o "Sedang Dalam Perbaikan"
```

## Gotchas (all hit in real session)
- **Stale build trap:** server started from a `=false` build ignores `=true` at start time → everything times out. Rebuild first.
- **curl hang trap:** `curl -I` or plain `curl` on a 307 route hangs (no body to read). Use `-L` to follow, or `curl -v` to see the `307 Temporary Redirect` line which proves middleware works.
- **API exemption is mandatory:** payment webhooks / cron routes must keep working during maintenance or orders silently die.
- Build log prints `ƒ Proxy (Middleware)` — confirm middleware is registered in the route list.
- Maintenance page should include the site logo (`import { NajLogo } from "@/components/naj-logo"`) — a bare wrench page looks broken to users.
- Verify assets post-deploy: `curl -o /dev/null -w "%{http_code}" https://www.storefront.example/logos/logo-storefront.png` must be 200, not 307.
