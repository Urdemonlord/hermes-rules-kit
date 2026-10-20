# Transactional Email via Resend API — Password Reset Pattern

Full code for adding forgot-password / reset-password flow to a SvelteKit project using Resend (zero npm deps).

## Files

### `src/lib/server/email.ts`

```typescript
import { env } from '$env/dynamic/private'

const RESEND_API_KEY = env.RESEND_API_KEY || ''
const FROM_EMAIL = env.EMAIL_FROM || 'user@example.com'
const ORIGIN = env.ORIGIN || 'http://localhost:3301'

export async function sendPasswordResetEmail(email: string, token: string) {
  const resetUrl = `${ORIGIN}/reset-password?token=<redacted>`
  const subject = 'Reset Password - the client site'

  if (!RESEND_API_KEY) {
    console.log(`[email] RESEND_API_KEY not set. Reset link for ${email}: ${resetUrl}`)
    return true
  }

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${RESEND_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      from: FROM_EMAIL,
      to: [email],
      subject,
      html: `
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
          <h2 style="color: #2d2d2d;">Reset Password</h2>
          <p style="color: #666; line-height: 1.6;">
            Kamu meminta reset password untuk akun the client site.
          </p>
          <a href="${resetUrl}"
            style="display: inline-block; background: #2d2d2d; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin: 16px 0;">
            Reset Password
          </a>
          <p style="color: #999; font-size: 13px; margin-top: 24px;">
            Link ini kadaluarsa dalam 1 jam. Jika kamu tidak meminta ini, abaikan email ini.
          </p>
        </div>
      `
    })
  })

  if (!res.ok) {
    const body = await res.text()
    console.error('[email] Resend error:', res.status, body)
    return false
  }
  return true
}
```

### `src/routes/forgot-password/+page.server.ts`

```typescript
import { prisma } from '$lib/server/db'
import { sendPasswordResetEmail } from '$lib/server/email'
import { fail } from '@sveltejs/kit'
import { randomBytes } from 'crypto'
import type { Actions } from './$types'

export const actions: Actions = {
  default: async ({ request }) => {
    const form = await request.formData()
    const email = (form.get('email') as string)?.trim().toLowerCase()

    if (!email) return fail(400, { error: 'Email harus diisi' })

    // Always show success to prevent email enumeration
    const user = await prisma.user.findUnique({ where: { email } })

    if (user) {
      const token=<redacted>'hex')
      const expiresAt = new Date(Date.now() + 60 * 60 * 1000) // 1 hour

      await prisma.passwordResetToken.create({
        data: { email, token, expiresAt }
      })

      await sendPasswordResetEmail(email, token)
    }

    return { sent: true }
  }
}
```

### `src/routes/forgot-password/+page.svelte`

```svelte
<script lang="ts">
  import { enhance } from '$app/forms';
  let { form } = $props();
  let sent = $state(!!form?.sent);
</script>

<div class="mx-auto max-w-md px-4 py-16">
  <h1 class="font-display text-2xl font-bold mb-2">Lupa Password</h1>
  <p class="text-sm text-stone mb-8">Masukkan email kamu. Kami kirim link reset.</p>

  {#if form?.error}
    <div class="bg-red-50 text-red-700 px-4 py-3 rounded mb-4 text-sm">{form.error}</div>
  {/if}

  {#if sent}
    <div class="bg-green-50 text-green-700 px-4 py-6 rounded text-center">
      <p class="font-medium">Cek email kamu</p>
      <p class="text-sm mt-2">Jika email terdaftar, link reset sudah dikirim.</p>
    </div>
  {:else}
    <form method="POST" use:enhance>
      <input type="email" name="email" required class="w-full px-4 py-3 border rounded-lg" />
      <button type="submit" class="w-full bg-charcoal text-white py-3 rounded-lg">Kirim Link Reset</button>
    </form>
    <p class="text-center text-sm text-stone mt-6">
      <a href="/login" class="text-charcoal hover:underline">Kembali ke Login</a>
    </p>
  {/if}
</div>
```

### `src/routes/reset-password/+page.server.ts`

```typescript
import { prisma } from '$lib/server/db'
import { redirect, fail } from '@sveltejs/kit'
import { hashSync } from 'bcryptjs'
import { z } from 'zod/v4'
import type { Actions, PageServerLoad } from './$types'

const resetSchema = z.object({
  token: z.string().min(1),
  password: z.string().min(6)
})

export const load: PageServerLoad = async ({ url }) => {
  const token=<redacted>'token')
  if (!token) return { valid: false, token: '' }

  const record = await prisma.passwordResetToken.findUnique({ where: { token } })
  if (!record || record.used || record.expiresAt < new Date()) {
    return { valid: false, token: '' }
  }

  return { valid: true, token }
}

export const actions: Actions = {
  default: async ({ request }) => {
    const formData = await request.formData()
    const parsed = resetSchema.safeParse(Object.fromEntries(formData))
    if (!parsed.success) return fail(400, { error: 'Token atau password tidak valid' })

    const { token, password } = parsed.data

    const record = await prisma.passwordResetToken.findUnique({ where: { token } })
    if (!record || record.used || record.expiresAt < new Date()) {
      return fail(400, { error: 'Link tidak valid atau kadaluarsa' })
    }

    await prisma.$transaction(async (tx) => {
      await tx.user.update({ where: { email: record.email }, data: { passwordHash: hashSync(password, 10) } })
      await tx.passwordResetToken.update({ where: { id: record.id }, data: { used: true } })
    })

    return { success: true }
  }
}
```

### `src/routes/reset-password/+page.svelte`

```svelte
<script lang="ts">
  import { enhance } from '$app/forms';
  let { data, form } = $props();
</script>

<div class="mx-auto max-w-md px-4 py-16">
  <h1 class="font-display text-2xl font-bold mb-2">Reset Password</h1>

  {#if form?.error}
    <div class="bg-red-50 text-red-700 px-4 py-3 rounded mb-4 text-sm">{form.error}</div>
  {/if}

  {#if form?.success}
    <div class="bg-green-50 text-green-700 px-4 py-6 rounded text-center">
      <p class="font-medium">Password berhasil direset</p>
      <p class="text-sm mt-2"><a href="/login" class="underline">Login sekarang</a></p>
    </div>
  {:else if data.valid}
    <form method="POST" use:enhance>
      <input type="password" name="password" required minlength="6" class="w-full px-4 py-3 border rounded-lg" />
      <input type="hidden" name="token" value={data.token} />
      <button type="submit" class="w-full bg-charcoal text-white py-3 rounded-lg">Reset Password</button>
    </form>
  {:else}
    <div class="bg-red-50 text-red-700 px-4 py-6 rounded text-center">
      <p class="font-medium">Link tidak valid atau kadaluarsa</p>
      <p class="text-sm mt-2"><a href="/forgot-password" class="underline">Minta link baru</a></p>
    </div>
  {/if}
</div>
```

## Login page — add "Lupa password?" link

```svelte
<div class="text-right mt-1">
  <a href="/forgot-password" class="text-xs text-stone hover:text-charcoal">Lupa password?</a>
</div>
```

Place this right after the `<input type="password">` element.

## Pitfalls

### Domain verification

Resend requires **each subdomain** to be verified separately. Verifying `meowlabs.id` does NOT automatically allow sending from `user@example.com`. If you get:

```
403 - The client-site.meowlabs.id domain is not verified
```

Either:
- **Option A**: Add the subdomain at https://resend.com/domains and add its DNS records
- **Option B (faster)**: Use a verified parent domain as FROM (e.g. `user@example.com`)

### Shell env overrides .env

Docker Compose reads shell environment variables BEFORE the `.env` file. If `RESEND_API_KEY` is exported in `~/.bashrc` or `~/.profile`, it will override the `.env` value silently. Check with:

```bash
echo "Shell: ${RESEND_API_KEY:0:12}..."
grep RESEND_API_KEY .env | cut -d= -f2 | cut -c1-12
```

Fix by updating dotfiles with the new key, or unsetting the shell var before `docker compose up`.

### Toast UX for forgot password

For better UX, replace the static success/error page swap with a toast notification that slides up from the bottom, auto-dismisses after 5s, and keeps the form visible:

```svelte
<script>
  let showToast = $state(false);
  // ...after form submit:
  showToast = true;
  setTimeout(() => showToast = false, 5000);
</script>

{#if showToast}
  <button onclick={() => showToast = false}
    class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl px-5 py-4 shadow-lg animate-slide-up">
    <!-- icon + title + message + close -->
  </button>
{/if}
```
