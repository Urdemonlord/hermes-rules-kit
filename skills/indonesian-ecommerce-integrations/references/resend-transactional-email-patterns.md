# Resend Email Patterns for SvelteKit E-Commerce

## Architecture
Single `sendEmail()` helper → all email functions call it. Fire-and-forget pattern (don't block webhook/API response). Shared `brandHeader()` for consistent branding.

## Setup (email.ts)
```typescript
import { env } from '$env/dynamic/private'
import { formatPrice } from '$lib/utils/format'

const RESEND_API_KEY = env.RESEND_API_KEY || ''
const FROM_EMAIL = env.EMAIL_FROM || 'user@example.com'
const ORIGIN = env.ORIGIN || 'http://localhost:3000'

function brandHeader() {
  return `<div style="text-align: center; padding: 24px 0;">
    <h1 style="color: #2d2d2d; margin: 0; font-size: 24px;">BRAND NAME</h1>
    <p style="color: #999; font-size: 13px;">Tagline here</p>
  </div>`
}

async function sendEmail(to: string, subject: string, html: string): Promise<boolean> {
  if (!RESEND_API_KEY) {
    console.log(`[email] RESEND_API_KEY not set. Would send to ${to}: ${subject}`)
    return true  // Don't block — Resend is optional in dev
  }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${RESEND_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ from: FROM_EMAIL, to: [to], subject, html })
  })
  if (!res.ok) {
    console.error('[email] Resend error:', res.status, await res.text())
    return false
  }
  return true
}
```

## Email Types

### 1. Order Confirmation (trigger: Midtrans webhook settlement)
```typescript
export async function sendOrderConfirmationEmail(order: {
  id: string; shippingName: string; shippingEmail?: string | null
  shippingPhone: string; total: number
  items: Array<{ productName: string; quantity: number; price: number }>
}) {
  const email = order.shippingEmail
  if (!email) return false

  const itemsHtml = order.items.map(item =>
    `<tr><td>${item.productName} × ${item.quantity}</td><td>${formatPrice(item.price * item.quantity)}</td></tr>`
  ).join('')

  const html = `
    ${brandHeader()}
    <h2>Pesanan Dikonfirmasi 🎉</h2>
    <p>Halo ${order.shippingName}, pembayaran untuk pesanan <strong>#${order.id.slice(0, 8)}</strong> telah kami terima.</p>
    <table>${itemsHtml}<tr><td><strong>Total</strong></td><td><strong>${formatPrice(order.total)}</strong></td></tr></table>
    <a href="${ORIGIN}/order/${order.id}">Lihat Pesanan</a>
  `
  return sendEmail(email, 'Pesanan Dikonfirmasi', html)
}
```

### 2. Newsletter Welcome (trigger: POST /api/newsletter)
```typescript
export async function sendNewsletterWelcomeEmail(email: string) {
  const html = `
    ${brandHeader()}
    <h2>Selamat Bergabung! 🎉</h2>
    <p>Terima kasih sudah berlangganan. Kamu akan dapat info koleksi baru dan penawaran spesial.</p>
    <a href="${ORIGIN}/products">Lihat Koleksi</a>
  `
  return sendEmail(email, 'Selamat Bergabung', html)
}
```

## Call Pattern (fire-and-forget)
```typescript
// In Midtrans webhook, after updating order:
if (paymentStatus === 'paid') {
  sendOrderConfirmationEmail({...}).catch(e =>
    console.error('[webhook] Failed to send confirmation email:', e)
  )
}

// In newsletter API, after DB upsert:
sendNewsletterWelcomeEmail(email).catch(e =>
  console.error('[newsletter] Failed to send welcome email:', e)
)
```

## Key Rules
- **Don't block the webhook**: emails are fire-and-forget with `.catch()`
- **Extract email from order notes**: guest checkout stores email in `order.notes` — use regex `/[\w.-]+@[\w.-]+\.\w+/` to extract
- **Dev fallback**: if `RESEND_API_KEY` is not set, log instead of failing — critical for local development
- **BRAND consistency**: all emails use the same `brandHeader()` for instant recognition
- **Zero npm deps**: just `fetch()` to Resend REST API — no SDK needed
